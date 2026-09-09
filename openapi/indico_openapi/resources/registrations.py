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
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.registrations import (
    Registration,
    RegistrationState,
    RegistrationVisibility,
)
from indico.modules.events.registration.schemas import RegistrationTagSchema as CoreRegistrationTagSchema
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase


PERSONAL_FIELDS = ('first_name', 'last_name', 'email', 'affiliation', 'title', 'address', 'phone', 'country',
                   'position')
MANAGER_FIELDS = ('state', 'checked_in_dt', 'submitted_dt', 'is_paid', 'price', 'currency', 'formatted_price',
                  'tags', 'visibility')


class RegistrationTagSchema(DescribedFieldsMixin, CoreRegistrationTagSchema):
    class Meta(CoreRegistrationTagSchema.Meta):
        descriptions = {
            'id': 'Numeric identifier of the tag, unique across the whole instance.',
            'title': 'Name of the tag.',
            'color': 'Colour the tag is shown in, as a colour name such as `blue`.',
        }


def personal_data_field(name):
    return fields.Function(lambda reg: reg.get_personal_data().get(name))


class RegistrationFormSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    class Meta:
        model = RegistrationForm
        fields = ('id', 'event_id', 'title', 'introduction', 'contact_info', 'start_dt', 'end_dt',
                  'modification_end_dt', 'is_open', 'is_scheduled', 'is_participation', 'require_login', 'require_user',
                  'moderation_enabled', 'registration_limit', 'registration_count', 'base_price', 'currency')
        descriptions = {
            'id': 'Numeric identifier of the registration form, unique across the whole instance.',
            'event_id': 'Identifier of the event the form belongs to.',
            'title': 'Title of the form.',
            'introduction': 'Text shown above the form, as plain text.',
            'contact_info': 'How to reach the organisers about this registration.',
            'start_dt': 'Moment registrations open, in UTC, or `null` while the form is not scheduled.',
            'end_dt': 'Moment registrations close, in UTC, or `null` when they never do.',
            'modification_end_dt': 'Moment registrants stop being able to change their answers, in UTC.',
            'is_open': 'Whether registrations are being accepted right now.',
            'is_scheduled': 'Whether the form has an opening date, which is what makes it show up in the event.',
            'is_participation': 'Whether this is the participants form of a meeting or lecture.',
            'require_login': 'Whether registering requires being logged in.',
            'require_user': 'Whether each registration has to be tied to an Indico account.',
            'moderation_enabled': 'Whether a manager has to approve each registration.',
            'registration_limit': 'Maximum number of registrations accepted, or `null` when there is no limit.',
            'registration_count': 'Number of active registrations. Only present when the event publishes it or the '
                                  'requesting user can manage registrations.',
            'base_price': 'Fee everybody pays on top of the fees of the fields they pick, as a decimal string.',
            'currency': 'ISO 4217 code of the currency prices are expressed in, such as `EUR`.',
        }

    is_open = fields.Boolean()
    is_scheduled = fields.Boolean()
    registration_count = fields.Integer(attribute='active_registration_count')
    base_price = fields.Decimal(as_string=True)

    @post_dump(pass_original=True)
    def _hide_restricted_data(self, data, regform, **kwargs):
        if not (self.context['can_manage'] or regform.publish_registration_count):
            del data['registration_count']
        return data


class RegistrationSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    class Meta:
        model = Registration
        fields = ('id', 'friendly_id', 'event_id', 'registration_form_id', 'full_name', *PERSONAL_FIELDS,
                  'checked_in', *MANAGER_FIELDS)
        descriptions = {
            'id': 'Numeric identifier of the registration, unique across the whole instance.',
            'friendly_id': 'Number shown to users, unique within the event.',
            'event_id': 'Identifier of the event the person registered for.',
            'registration_form_id': 'Identifier of the form the person registered through.',
            'full_name': 'Full name of the registrant, in display order.',
            'first_name': 'First name of the registrant.',
            'last_name': 'Last name of the registrant.',
            'email': 'Email address of the registrant.',
            'affiliation': 'Organisation the registrant belongs to.',
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
            'visibility': 'Who the registration is shown to: `nobody`, `participants` or `all`.',
        }

    full_name = fields.String()
    affiliation = personal_data_field('affiliation')
    title = personal_data_field('title')
    address = personal_data_field('address')
    phone = personal_data_field('phone')
    country = personal_data_field('country')
    position = personal_data_field('position')
    state = fields.Enum(RegistrationState)
    visibility = fields.Enum(RegistrationVisibility)
    is_paid = fields.Boolean()
    price = fields.Decimal(as_string=True)
    formatted_price = fields.Function(lambda reg: reg.render_price())
    tags = fields.Nested(RegistrationTagSchema, many=True)

    @post_dump(pass_original=True)
    def _hide_restricted_data(self, data, registration, **kwargs):
        user = self.context['user']
        if self.context['can_manage'] or (user and registration.user == user):
            return data
        published = self.context['published_columns']
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


class RegistrationMixin:
    """Access checks shared by the registration endpoints.

    Registration managers see every form and every registration. Everybody else
    sees the forms the event advertises, their own registrations, and the
    registrations the event publishes to them, which depends on whether they are
    a participant themselves and on the consent each registrant gave.
    """

    def _process_args(self):
        RHProtectedEventBase._process_args(self)
        self.can_manage = self.event.can_manage(session.user, permission='registration')
        self.is_participant = self.event.is_user_registered(session.user)

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

    def _regform_schema(self, **kwargs):
        return RegistrationFormSchema(context={'can_manage': self.can_manage}, **kwargs)

    def _registration_schema(self, **kwargs):
        return RegistrationSchema(context={'can_manage': self.can_manage, 'user': session.user,
                                           'published_columns': set(registration_settings.get_participant_list_columns(
                                               self.event))},
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
        return self._registration_schema().jsonify(self.registration)


@json_errors
class RHRegistrationList(RegistrationMixin, RHListBase, RHProtectedEventBase):
    schema = RegistrationSchema

    def _query(self):
        return self._registration_query()

    def _can_access(self, obj):
        return self._can_see_registration(obj)

    def _dump_schema(self):
        return self._registration_schema(many=True)


ENDPOINTS = [
    Endpoint(rule='/events/<int:event_id>/registration-forms', name='regforms', rh=RHRegistrationFormList,
             schema=RegistrationFormSchema, many=True, summary='List the registration forms of an event',
             tag='Registrations'),
    Endpoint(rule='/events/<int:event_id>/registration-forms/<int:regform_id>', name='regform', rh=RHRegistrationForm,
             schema=RegistrationFormSchema, summary='Registration form details', tag='Registrations'),
    Endpoint(rule='/events/<int:event_id>/registrations', name='registrations', rh=RHRegistrationList,
             schema=RegistrationSchema, many=True, summary='List the registrations of an event', tag='Registrations'),
    Endpoint(rule='/events/<int:event_id>/registrations/<int:registration_id>', name='registration', rh=RHRegistration,
             schema=RegistrationSchema, summary='Registration details', tag='Registrations'),
]
