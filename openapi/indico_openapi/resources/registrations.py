# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from flask import request, session
from marshmallow import fields, post_dump
from werkzeug.exceptions import Forbidden

from indico.core.db import db
from indico.core.marshmallow import mm
from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.modules.events.registration import registration_settings
from indico.modules.events.registration.fields.base import RegistrationFormBillableItemsField
from indico.modules.events.registration.models.form_fields import RegistrationFormField
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.items import PersonalDataType, RegistrationFormSection
from indico.modules.events.registration.models.registrations import Registration, RegistrationState
from indico.modules.events.registration.models.tags import RegistrationTag
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase
from indico_openapi.schemas import RegistrationTagSchema


PERSONAL_FIELDS = ('first_name', 'last_name', 'email', 'affiliation', 'title', 'address', 'phone', 'country',
                   'position')
MANAGER_FIELDS = ('state', 'checked_in_dt', 'submitted_dt', 'is_paid', 'price', 'currency',
                  'formatted_price', 'tags')


def personal_data_field(name):
    return fields.Function(lambda reg: reg.get_personal_data().get(name, ''))


def published_fields(event, regform):
    """What the participant list publishes about a registration of ``regform``.

    Returns the names of the personal data columns and the ids of the fields,
    personal data included, shown for the form. A merged list shows the same
    personal data columns for every form; a list per form shows the fields the
    organisers picked for it, which may include custom ones.
    """
    active = {field.id: field for field in regform.active_fields}
    if registration_settings.get(event, 'merge_registration_forms'):
        names = set(registration_settings.get_participant_list_columns(event))
        ids = {field.id for field in active.values()
               if field.personal_data_type and field.personal_data_type.name in names}
        return names, ids
    ids = {field_id for field_id in registration_settings.get_participant_list_columns(event, regform)
           if field_id in active}
    names = {active[field_id].personal_data_type.name for field_id in ids if active[field_id].personal_data_type}
    return names, ids


class RegistrationChoiceSchema(DescribedFieldsMixin, mm.Schema):
    class Meta:
        descriptions = {
            'id': 'Identifier of the choice, a UUID. The stored answer of the field refers to it.',
            'caption': 'Text of the choice as the form shows it.',
            'price': 'Price of the choice, in the currency of the form.',
            'places_limit': 'Number of registrants who may pick the choice, or 0 when there is no limit.',
            'is_enabled': 'Whether the choice can still be picked.',
        }

    id = fields.String()
    caption = fields.String()
    price = fields.Float()
    places_limit = fields.Integer()
    is_enabled = fields.Boolean()


class ItemChoices(fields.List):
    """Serialize the choices of a field billed per item, which are the ones the organisers defined.

    A country field also lists choices, but they are the ISO countries and the
    answer carries the code, so there is nothing a reader would need them for.
    """

    def get_value(self, obj, attr, **kwargs):
        impl = obj.field_impl
        return impl.view_data['choices'] if isinstance(impl, RegistrationFormBillableItemsField) else None


class RegistrationFieldSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """One question of a registration form.

    The settings of a field depend on its type, so only the ones a reader needs
    to interpret the answers are served: the price and the choices. The rest
    say how the form is rendered and validated.
    """

    class Meta:
        model = RegistrationFormField
        fields = ('id', 'section_id', 'position', 'title', 'description', 'input_type', 'is_required',
                  'personal_data_type', 'price', 'choices', 'default_value', 'show_if_field_id', 'show_if_values',
                  'is_purged')
        descriptions = {
            'id': 'Numeric identifier of the field, unique across the whole instance.',
            'section_id': 'Identifier of the section holding the field.',
            'position': 'Place of the field in its section, starting at 1.',
            'title': 'Label of the field.',
            'description': 'Help text shown under the field, as Markdown.',
            'input_type': 'Kind of field, such as `text`, `single_choice`, `checkbox`, `date`, `file` or '
                          '`accommodation`.',
            'is_required': 'Whether the field has to be filled in to register.',
            'personal_data_type': 'Which personal data the field collects, such as `email` or `affiliation`, or '
                                  '`null` for a field the organisers added.',
            'price': 'Price of the field, in the currency of the form, or `null` when the field cannot be charged '
                     'for. A choice field is charged per choice instead.',
            'choices': 'Options of a single choice, multiple choice or accommodation field, each with its own '
                       'price, or `null` for any other kind.',
            'default_value': 'Value the form starts with. Its shape depends on `input_type`.',
            'show_if_field_id': 'Identifier of the field this one depends on, or `null` when it is always shown.',
            'show_if_values': 'Values of that field for which this one is shown.',
            'is_purged': 'Whether the answers to the field were deleted once its retention period expired.',
        }

    section_id = fields.Integer(attribute='parent_id')
    personal_data_type = fields.Enum(PersonalDataType, allow_none=True)
    price = fields.Float(attribute='field_impl.view_data.price', allow_none=True)
    choices = ItemChoices(fields.Nested(RegistrationChoiceSchema), allow_none=True)
    default_value = fields.Raw(attribute='field_impl.ui_default_value', allow_none=True)
    show_if_field_id = fields.Integer(attribute='show_if_id', allow_none=True)
    show_if_values = fields.Raw(allow_none=True)

    @post_dump
    def _fill_missing_price(self, data, **kwargs):
        # the key does not exist in the settings of a field that cannot be charged for
        data.setdefault('price', None)
        return data


class ActiveFields(fields.List):
    def get_value(self, obj, attr, **kwargs):
        return [field for field in obj.fields if field.is_enabled and not field.is_deleted]


class RegistrationSectionSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    class Meta:
        model = RegistrationFormSection
        fields = ('id', 'registration_form_id', 'position', 'title', 'description', 'is_manager_only',
                  'is_personal_data', 'fields')
        descriptions = {
            'id': 'Numeric identifier of the section, unique across the whole instance.',
            'registration_form_id': 'Identifier of the form the section belongs to.',
            'position': 'Place of the section in the form, starting at 1.',
            'title': 'Title of the section.',
            'description': 'Text shown under the title, as Markdown.',
            'is_manager_only': 'Whether only the managers see and fill in the section.',
            'is_personal_data': 'Whether this is the section every form starts with, asking who the registrant is.',
            'fields': 'Fields of the section, in the order the form shows them. Disabled fields and text blocks '
                      'are left out.',
        }

    is_personal_data = fields.Boolean(attribute='own_data.is_personal_data')
    fields = ActiveFields(fields.Nested(RegistrationFieldSchema))


class RegistrationAnswerSchema(DescribedFieldsMixin, mm.Schema):
    class Meta:
        descriptions = {
            'id': 'Identifier of the field the answer is to.',
            'title': 'Label of the field.',
            'input_type': 'Kind of field, which says what shape `data` and `value` take.',
            'data': 'The answer as stored: the identifier of a choice, an ISO date, a boolean, a number, an object '
                    'for an affiliation or accommodation. A file is represented by its name. `null` once purged.',
            'value': 'The answer as the registration summary shows it: the caption of a choice, a formatted date, '
                     '`Yes` or `No`, a list of captions for a multiple choice. `null` once purged.',
            'price': 'What the answer added to the fee, as a decimal string in the currency of the form.',
        }

    id = fields.Integer()
    title = fields.String()
    input_type = fields.String()
    data = fields.Raw(allow_none=True)
    value = fields.Raw(allow_none=True)
    price = fields.Decimal(as_string=True)


class RegistrationAnswerSectionSchema(DescribedFieldsMixin, mm.Schema):
    class Meta:
        descriptions = {
            'id': 'Identifier of the section.',
            'title': 'Title of the section.',
            'fields': 'The answered fields of the section, in the order the form shows them.',
        }

    id = fields.Integer()
    title = fields.String()
    fields = fields.List(fields.Nested(RegistrationAnswerSchema))


def _answer(data):
    field = data.field_data.field
    if field.is_purged:
        stored = shown = None
    else:
        stored = data.filename if field.field_impl.is_file_field else data.data
        shown = data.friendly_data
    return {'id': field.id, 'title': field.title, 'input_type': field.input_type, 'data': stored, 'value': shown,
            'price': data.price}


def registration_answers(registration, can_manage, is_own, published_ids):
    """The answers of a registration, grouped by section, as the caller may see them.

    Managers and the registrant get what the registration summary shows: every
    answered section, minus the manager-only and deleted ones for the registrant,
    and every answered field its conditions allow. Anybody else gets the fields
    the participant list publishes for the form.
    """
    data_by_field = registration.data_by_field
    sections = []
    for section in registration.registration_form.sections:
        if can_manage or is_own:
            if not section.is_visible_in_summary(can_manage):
                continue
            answered = [field for field in section.children
                        if field.is_field and field.id in data_by_field and registration.is_field_shown(field)
                        and (can_manage or not field.is_deleted)]
        else:
            answered = [field for field in section.children
                        if field.is_field and field.id in data_by_field and field.id in published_ids]
        if answered:
            sections.append({'id': section.id, 'title': section.title,
                             'fields': [_answer(data_by_field[field.id]) for field in answered]})
    return sections


class AnsweredSections(fields.List):
    def get_value(self, obj, attr, **kwargs):
        user = self.context['user']
        is_own = bool(user and obj.user == user)
        published_ids = self.context['published_fields'](obj.registration_form)[1]
        return registration_answers(obj, self.context['can_manage'], is_own, published_ids)


class RegistrationFormSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    class Meta:
        model = RegistrationForm
        fields = ('id', 'event_id', 'title', 'introduction', 'start_dt', 'end_dt', 'is_open',
                  'registration_count')
        descriptions = {
            'id': 'Numeric identifier of the registration form, unique across the whole instance.',
            'event_id': 'Identifier of the event the form belongs to.',
            'title': 'Title of the form.',
            'introduction': 'Text shown above the form, as plain text.',
            'start_dt': 'Moment registrations open, in UTC, or `null` while the form is not scheduled.',
            'end_dt': 'Moment registrations close, in UTC, or `null` when they never do.',
            'is_open': 'Whether registrations are being accepted right now.',
            'registration_count': 'Number of places taken. Only present for managers and for forms publishing '
                                  'their registration count.',
        }

    is_open = fields.Boolean()
    registration_count = fields.Integer(attribute='existing_registrations_count')

    @post_dump(pass_original=True)
    def _hide_restricted_data(self, data, regform, **kwargs):
        if not self.context['can_manage'] and not regform.publish_registration_count:
            del data['registration_count']
        return data


class RegistrationSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    class Meta:
        model = Registration
        fields = ('id', 'event_id', 'registration_form_id', 'full_name', *PERSONAL_FIELDS,
                  'checked_in', *MANAGER_FIELDS)
        descriptions = {
            'id': 'Numeric identifier of the registration, unique across the whole instance.',
            'event_id': 'Identifier of the event the person registered for.',
            'registration_form_id': 'Identifier of the form the person registered through.',
            'full_name': 'Full name of the registrant, in the name format the caller prefers.',
            'first_name': 'First name of the registrant.',
            'last_name': 'Last name of the registrant.',
            'email': 'Email address of the registrant.',
            'affiliation': 'Organisation the registrant belongs to, or an empty string when the form '
                           'does not ask for it.',
            'title': 'Personal title, such as `Dr` or `Prof`.',
            'address': 'Postal address of the registrant.',
            'phone': 'Phone number of the registrant.',
            'country': 'Country of the registrant.',
            'position': 'Position the registrant holds in their organisation.',
            'checked_in': 'Whether the registrant has checked in. Only present for managers and for events '
                          'publishing the check-in status.',
            'state': 'Where the registration stands: `complete`, `pending`, `rejected`, `withdrawn` or `unpaid`.',
            'checked_in_dt': 'Moment the registrant checked in, in UTC, or `null` if they have not.',
            'submitted_dt': 'Moment the registration was submitted, in UTC.',
            'is_paid': 'Whether the registration fee has been paid.',
            'price': 'Total fee of the registration, as a decimal string.',
            'currency': 'ISO 4217 code of the currency the price is expressed in, such as `EUR`.',
            'formatted_price': 'Total fee rendered with its currency, such as `10.00 EUR`.',
            'tags': 'Tags the organisers attached to the registration.',
        }

    full_name = fields.String(attribute='display_full_name')
    affiliation = personal_data_field('affiliation')
    title = personal_data_field('title')
    address = personal_data_field('address')
    phone = personal_data_field('phone')
    country = personal_data_field('country')
    position = personal_data_field('position')
    state = fields.Enum(RegistrationState)
    is_paid = fields.Boolean()
    price = fields.Decimal(as_string=True)
    formatted_price = fields.Function(lambda reg: reg.render_price())
    tags = fields.Nested(RegistrationTagSchema, many=True)

    @post_dump(pass_original=True)
    def _hide_restricted_data(self, data, registration, **kwargs):
        user = self.context['user']
        if self.context['can_manage'] or (user and registration.user == user):
            return data
        published = self.context['published_fields'](registration.registration_form)[0]
        for name in PERSONAL_FIELDS:
            if name not in published:
                del data[name]
        if not {'first_name', 'last_name'} <= published:
            del data['full_name']
        for name in MANAGER_FIELDS:
            del data[name]
        if not registration.registration_form.publish_checkin_enabled:
            del data['checked_in']
        return data


class RegistrationDetailsSchema(RegistrationSchema):
    class Meta(RegistrationSchema.Meta):
        fields = (*RegistrationSchema.Meta.fields, 'sections')
        descriptions = {
            **RegistrationSchema.Meta.descriptions,
            'sections': 'The answers given, grouped by section of the form. Only the fields the caller may see '
                        'are listed, so a section nobody answered or the caller may not read is left out.',
        }

    sections = AnsweredSections(fields.Nested(RegistrationAnswerSectionSchema))


class RegistrationMixin:
    """Access checks shared by the registration endpoints.

    Registration managers see every form and every registration. Everybody else
    sees the forms the event advertises, their own registrations, and the
    registrations the event publishes to them, which depends on whether they are
    a participant themselves and on the consent each registrant gave.
    """

    EVENT_FEATURE = 'registration'

    def _process_args(self):
        RHProtectedEventBase._process_args(self)
        self.can_manage = self.event.can_manage(session.user, permission='registration')
        self.is_participant = self.event.is_user_registered(session.user)
        self._published_fields = {}

    def _published_fields_of(self, regform):
        if regform.id not in self._published_fields:
            self._published_fields[regform.id] = published_fields(self.event, regform)
        return self._published_fields[regform.id]

    def _regform_query(self):
        return (RegistrationForm.query.with_parent(self.event)
                .filter(~RegistrationForm.is_deleted)
                .order_by(db.func.lower(RegistrationForm.title), RegistrationForm.id))

    def _registration_query(self):
        return (Registration.query.with_parent(self.event)
                .filter(~Registration.is_deleted,
                        RegistrationForm.query.filter(RegistrationForm.id == Registration.registration_form_id,
                                                      ~RegistrationForm.is_deleted).exists())
                .order_by(Registration.friendly_id))

    def _can_see_regform(self, regform):
        if self.can_manage:
            return True
        if regform.private:
            return bool(session.user and regform.get_registration(user=session.user))
        return regform.is_scheduled

    def _can_see_registration(self, registration):
        if self.can_manage or (session.user and registration.user == session.user):
            return True
        return registration.is_publishable(self.is_participant)

    def _can_see_section(self, section):
        return self.can_manage or not section.is_manager_only

    def _regform_schema(self, **kwargs):
        return RegistrationFormSchema(context={'can_manage': self.can_manage}, **kwargs)

    def _registration_schema(self, schema=RegistrationSchema, **kwargs):
        return schema(context={'can_manage': self.can_manage, 'user': session.user,
                               'published_fields': self._published_fields_of},
                      **kwargs)


@json_errors
class RHRegistrationForm(RegistrationMixin, RHProtectedEventBase):
    def _process_args(self):
        RegistrationMixin._process_args(self)
        self.regform = (self._regform_query()
                        .filter(RegistrationForm.id == request.view_args['regform_id']).first_or_404())

    def _check_access(self):
        RHProtectedEventBase._check_access(self)
        if not self._can_see_regform(self.regform):
            raise Forbidden

    def _process_GET(self):
        return self._regform_schema().jsonify(self.regform)


@json_errors
class RHRegistrationFormList(RegistrationMixin, RHListBase, RHProtectedEventBase):
    schema = RegistrationFormSchema

    def _query(self):
        return self._regform_query()

    def _can_access(self, obj):
        return self._can_see_regform(obj)

    def _dump_schema(self):
        return self._regform_schema(many=True)


class RegistrationFormSectionMixin(RegistrationMixin):
    def _process_args(self):
        RegistrationMixin._process_args(self)
        self.regform = (self._regform_query()
                        .filter(RegistrationForm.id == request.view_args['regform_id']).first_or_404())

    def _check_access(self):
        RHProtectedEventBase._check_access(self)
        if not self._can_see_regform(self.regform):
            raise Forbidden

    def _section_query(self):
        return (RegistrationFormSection.query
                .filter(RegistrationFormSection.registration_form_id == self.regform.id,
                        RegistrationFormSection.is_enabled, ~RegistrationFormSection.is_deleted)
                .order_by(RegistrationFormSection.position))


@json_errors
class RHRegistrationFormSection(RegistrationFormSectionMixin, RHProtectedEventBase):
    def _process_args(self):
        RegistrationFormSectionMixin._process_args(self)
        self.section = (self._section_query()
                        .filter(RegistrationFormSection.id == request.view_args['section_id']).first_or_404())

    def _check_access(self):
        RegistrationFormSectionMixin._check_access(self)
        if not self._can_see_section(self.section):
            raise Forbidden

    def _process_GET(self):
        return RegistrationSectionSchema().jsonify(self.section)


@json_errors
class RHRegistrationFormSectionList(RegistrationFormSectionMixin, RHListBase, RHProtectedEventBase):
    schema = RegistrationSectionSchema

    def _query(self):
        return self._section_query()

    def _can_access(self, obj):
        return self._can_see_section(obj)


@json_errors
class RHRegistration(RegistrationMixin, RHProtectedEventBase):
    def _process_args(self):
        RegistrationMixin._process_args(self)
        self.registration = (self._registration_query()
                             .filter(Registration.id == request.view_args['registration_id']).first_or_404())

    def _check_access(self):
        RHProtectedEventBase._check_access(self)
        if not self._can_see_registration(self.registration):
            raise Forbidden

    def _process_GET(self):
        return self._registration_schema(RegistrationDetailsSchema).jsonify(self.registration)


@json_errors
class RHRegistrationList(RegistrationMixin, RHListBase, RHProtectedEventBase):
    schema = RegistrationSchema

    def _query(self):
        return self._registration_query()

    def _can_access(self, obj):
        return self._can_see_registration(obj)

    def _dump_schema(self):
        return self._registration_schema(many=True)


class RegistrationTagMixin(RegistrationMixin):
    """Access checks shared by the registration tag endpoints.

    The tags of a registration are only served to the organisers, and so is the
    catalogue they are taken from.
    """

    def _check_access(self):
        RHProtectedEventBase._check_access(self)
        if not self.can_manage:
            raise Forbidden

    def _tag_query(self):
        return (RegistrationTag.query.with_parent(self.event)
                .order_by(db.func.lower(RegistrationTag.title), RegistrationTag.id))


@json_errors
class RHRegistrationTag(RegistrationTagMixin, RHProtectedEventBase):
    def _process_args(self):
        RegistrationTagMixin._process_args(self)
        self.tag = self._tag_query().filter(RegistrationTag.id == request.view_args['tag_id']).first_or_404()

    def _process_GET(self):
        return RegistrationTagSchema().jsonify(self.tag)


@json_errors
class RHRegistrationTagList(RegistrationTagMixin, RHListBase, RHProtectedEventBase):
    schema = RegistrationTagSchema

    def _query(self):
        return self._tag_query()

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(rule='/events/<int:event_id>/registration-forms', name='regforms', rh=RHRegistrationFormList,
             schema=RegistrationFormSchema, many=True, summary='List the registration forms of an event',
             tag='Registrations'),
    Endpoint(rule='/events/<int:event_id>/registration-forms/<int:regform_id>', name='regform', rh=RHRegistrationForm,
             schema=RegistrationFormSchema, summary='Registration form details', tag='Registrations'),
    Endpoint(rule='/events/<int:event_id>/registration-forms/<int:regform_id>/sections', name='regform_sections',
             rh=RHRegistrationFormSectionList, schema=RegistrationSectionSchema, many=True,
             summary='List the sections of a registration form, with their fields', tag='Registrations'),
    Endpoint(rule='/events/<int:event_id>/registration-forms/<int:regform_id>/sections/<int:section_id>',
             name='regform_section', rh=RHRegistrationFormSection, schema=RegistrationSectionSchema,
             summary='Registration form section details', tag='Registrations'),
    Endpoint(rule='/events/<int:event_id>/registrations', name='registrations', rh=RHRegistrationList,
             schema=RegistrationSchema, many=True, summary='List the registrations of an event', tag='Registrations'),
    Endpoint(rule='/events/<int:event_id>/registrations/<int:registration_id>', name='registration', rh=RHRegistration,
             schema=RegistrationDetailsSchema, summary='Registration details, with the answers given',
             tag='Registrations'),
    Endpoint(rule='/events/<int:event_id>/registration-tags', name='registration_tags', rh=RHRegistrationTagList,
             schema=RegistrationTagSchema, many=True, summary='List the tags an event marks its registrations with',
             tag='Registrations'),
    Endpoint(rule='/events/<int:event_id>/registration-tags/<int:tag_id>', name='registration_tag',
             rh=RHRegistrationTag, schema=RegistrationTagSchema, summary='Registration tag details',
             tag='Registrations'),
]
