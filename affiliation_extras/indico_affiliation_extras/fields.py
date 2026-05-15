# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from marshmallow import ValidationError, fields

from indico.core import signals
from indico.core.db import db
from indico.core.marshmallow import mm
from indico.modules.events.registration.custom import CustomRegistrationListItem, RegistrationListColumn
from indico.modules.events.registration.fields.affiliation import AffiliationValueSchema
from indico.modules.events.registration.fields.base import RegistrationFormFieldBase
from indico.modules.events.registration.models.registrations import RegistrationData
from indico.modules.users.models.affiliations import Affiliation
from indico.util.i18n import _
from indico.util.signals import values_from_signal

from indico_affiliation_extras.util import (
    get_representation_affiliation_list,
    get_representation_affiliation_lists,
    get_representation_affiliations,
)


REPRESENTATION_AFFILIATION_PRELOAD_LIMIT = 20
_AFFILIATION_PRELOAD_FIELDS = ('id', 'name', 'street', 'postcode', 'city', 'country_code', 'meta')


class RepresentationValueSchema(mm.Schema):
    representation_id = fields.Integer(required=True, allow_none=True, data_key='representationId')
    representation_name = fields.String(load_default='', data_key='representationName')
    affiliation = fields.Nested(AffiliationValueSchema, required=True)


class RepresentationField(RegistrationFormFieldBase):
    name = 'ext__representation'
    mm_field_class = fields.Nested
    mm_field_args = (RepresentationValueSchema,)
    not_empty_if_required = False

    @property
    def default_value(self):
        return {
            'representation_id': None,
            'representation_name': '',
            'affiliation': {'id': None, 'text': ''},
        }

    @property
    def view_data(self):
        from indico.modules.users.schemas import AffiliationSchema

        representation_types = []
        for item in get_representation_affiliation_lists(self.form_item.registration_form.event, enabled_only=True):
            data = {'id': item.id, 'name': item.name}
            affiliations = get_representation_affiliations(item)
            if len(affiliations) <= REPRESENTATION_AFFILIATION_PRELOAD_LIMIT:
                data['affiliations'] = AffiliationSchema(many=True, only=_AFFILIATION_PRELOAD_FIELDS).dump(affiliations)
            representation_types.append(data)
        return super().view_data | {'representation_types': representation_types}

    def get_validators(self, existing_registration):
        def _validate_representation(value):
            representation_id = value['representation_id']
            affiliation = value['affiliation']
            affiliation_text = affiliation['text']
            affiliation_id = affiliation['id']
            if self.form_item.is_required and representation_id is None:
                raise ValidationError('Please select a representation type')
            if representation_id is None and affiliation_id is not None:
                raise ValidationError('Please select a representation type')
            if affiliation_id is None:
                if affiliation_text or representation_id is not None or self.form_item.is_required:
                    raise ValidationError('Please select an affiliation from the list')

        return _validate_representation

    def process_form_data(self, registration, value, old_data=None, billable_items_locked=False):
        event = self.form_item.registration_form.event
        representation_id = value['representation_id']
        affiliation_list = get_representation_affiliation_list(event, representation_id)
        if representation_id is not None and affiliation_list is None:
            raise ValidationError('Invalid representation type')

        affiliation = value['affiliation']
        if affiliation['id'] is not None:
            context = {
                'event': event,
                'registration_form': self.form_item.registration_form,
                'registration': registration,
                'field': self.form_item,
                'affiliation_list': affiliation_list,
            }
            filters = values_from_signal(
                signals.affiliations.get_affiliation_filters.send(self, context=context),
                as_list=True,
                multi_value_types=list,
            )
            query = Affiliation.query.filter_by(id=affiliation['id'], is_deleted=False)
            if filters:
                query = query.filter(*filters)
            if not (matched_affiliation := query.one_or_none()):
                raise ValidationError('Invalid affiliation')
            affiliation['text'] = matched_affiliation.name

        value['representation_name'] = affiliation_list.name if affiliation_list else ''
        value['affiliation'] = affiliation
        return RegistrationFormFieldBase.process_form_data(self, registration, value, old_data, billable_items_locked)

    def get_friendly_data(self, registration_data, for_humans=False, for_search=False):
        representation_name = registration_data.data.get('representation_name', '')
        affiliation_name = registration_data.data.get('affiliation', {}).get('text', '')
        if representation_name and affiliation_name:
            return f'{representation_name} - {affiliation_name}'
        return representation_name or affiliation_name

    def create_sql_filter(self, data_list):
        representation_name = db.func.coalesce(RegistrationData.data['representation_name'].astext, '')
        affiliation_name = db.func.coalesce(RegistrationData.data['affiliation']['text'].astext, '')
        return db.or_(
            representation_name.in_(data_list),
            affiliation_name.in_(data_list),
            db.func.concat(representation_name, ' - ', affiliation_name).in_(data_list),
        )


class RepresentationRegistrationListItem(CustomRegistrationListItem):
    field_id = None
    value_name = None

    def _get_value(self, registration_data):
        data = registration_data.data or {}
        if self.value_name == 'representation_type':
            return data.get('representation_name', '')
        elif self.value_name == 'affiliation':
            return data.get('affiliation', {}).get('text', '')
        else:
            raise ValueError(f'Unexpected representation list item: {self.value_name}')

    def load_data(self, registrations):
        rv = {}
        for registration in registrations:
            registration_data = registration.data_by_field.get(self.field_id)
            if registration_data is None:
                continue
            value = self._get_value(registration_data)
            if value:
                rv[registration] = RegistrationListColumn(value, value)
        return rv


def iter_representation_reglist_items(regform):
    for field in regform.form_items:
        if (
            not field.is_field or
            field.is_deleted or
            (field.parent is not None and field.parent.is_deleted) or
            field.input_type != RepresentationField.name
        ):
            continue

        yield type(
            f'RepresentationTypeRegistrationListItem{field.id}',
            (RepresentationRegistrationListItem,),
            {
                'field_id': field.id,
                'name': f'affiliation_extras_representation_{field.id}_type',
                'title': _('{field}: Type').format(field=field.title),
                'value_name': 'representation_type',
            },
        )
        yield type(
            f'RepresentationAffiliationRegistrationListItem{field.id}',
            (RepresentationRegistrationListItem,),
            {
                'field_id': field.id,
                'name': f'affiliation_extras_representation_{field.id}_affiliation',
                'title': _('{field}: Affiliation').format(field=field.title),
                'value_name': 'affiliation',
            },
        )
