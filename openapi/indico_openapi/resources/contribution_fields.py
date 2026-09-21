# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from flask import request, session
from werkzeug.exceptions import Forbidden

from indico.modules.events.contributions.models.fields import ContributionField, ContributionFieldVisibility
from indico.modules.events.contributions.schemas import ContributionFieldSchema as CoreContributionFieldSchema
from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase


class ContributionFieldSchema(DescribedFieldsMixin, CoreContributionFieldSchema):
    """Custom field the event asks for on every contribution and abstract.

    The values are served with each contribution; this is the definition that
    says what they mean.
    """

    class Meta(CoreContributionFieldSchema.Meta):
        fields = ('id', 'event_id', 'position', 'title', 'description', 'is_required', 'is_active',
                  'is_user_editable', 'visibility', 'field_type', 'field_data')
        descriptions = {
            'id': 'Numeric identifier of the field, unique across the whole instance.',
            'event_id': 'Identifier of the event defining the field.',
            'position': 'Place of the field among the others, starting at 1.',
            'title': 'Label of the field.',
            'description': 'Help text shown under the field, as Markdown.',
            'is_required': 'Whether the field has to be filled in.',
            'is_active': 'Whether the field is still asked for. Only managers see inactive fields.',
            'is_user_editable': 'Whether abstract submitters may fill the field in themselves.',
            'visibility': 'Who may read the values: `public`, `managers_and_submitters` or `managers_only`.',
            'field_type': 'Kind of field, such as `text`, `single_choice` or `multiselect`.',
            'field_data': 'Settings of the field, whose keys depend on `field_type`: the options of a choice field, '
                          'the length limits of a text field.',
        }


class ContributionFieldMixin:
    """Access checks shared by the custom field endpoints.

    Managers get every field. Everybody else gets the active fields whose values
    are public, which are the ones whose values they can read on a contribution.
    """

    def _process_args(self):
        RHProtectedEventBase._process_args(self)
        self.can_manage = self.event.can_manage(session.user, permission='contributions')

    def _field_query(self):
        return ContributionField.query.with_parent(self.event).order_by(ContributionField.position)

    def _can_see_field(self, field):
        return self.can_manage or (field.is_active and field.visibility == ContributionFieldVisibility.public)


@json_errors
class RHContributionField(ContributionFieldMixin, RHProtectedEventBase):
    def _process_args(self):
        ContributionFieldMixin._process_args(self)
        self.field = (self._field_query()
                      .filter(ContributionField.id == request.view_args['field_id']).first_or_404())

    def _check_access(self):
        RHProtectedEventBase._check_access(self)
        if not self._can_see_field(self.field):
            raise Forbidden

    def _process_GET(self):
        return ContributionFieldSchema().jsonify(self.field)


@json_errors
class RHContributionFieldList(ContributionFieldMixin, RHListBase, RHProtectedEventBase):
    schema = ContributionFieldSchema

    def _query(self):
        return self._field_query()

    def _can_access(self, obj):
        return self._can_see_field(obj)


ENDPOINTS = [
    Endpoint(rule='/events/<int:event_id>/contribution-fields', name='contribution_fields',
             rh=RHContributionFieldList, schema=ContributionFieldSchema, many=True,
             summary='List the custom contribution fields of an event', tag='Contributions'),
    Endpoint(rule='/events/<int:event_id>/contribution-fields/<int:field_id>', name='contribution_field',
             rh=RHContributionField, schema=ContributionFieldSchema, summary='Custom contribution field details',
             tag='Contributions'),
]
