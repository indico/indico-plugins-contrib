# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from flask import request, session
from marshmallow import fields

from indico.core.marshmallow import mm
from indico.modules.events.contributions.models.subcontributions import SubContribution
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase
from indico_openapi.resources.contributions import RHContribution
from indico_openapi.schemas import SubContributionPersonSchema


class SubContributionSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    class Meta:
        model = SubContribution
        fields = ('id', 'title', 'friendly_id', 'code', 'duration', 'persons')
        descriptions = {
            'id': 'Numeric identifier of the subcontribution, unique across the whole instance.',
            'title': 'Title of the subcontribution.',
            'friendly_id': 'Number shown to users, unique within the parent contribution.',
            'code': 'Programme code assigned to the subcontribution.',
            'duration': 'Length of the subcontribution, in seconds.',
            'persons': 'Speakers of the subcontribution. Email is only present for users who can '
                       'manage the contribution.',
        }

    persons = fields.List(fields.Nested(SubContributionPersonSchema), attribute='person_links')


class SubContributionMixin:
    """Subcontributions are read through their contribution, which gates the access."""

    def _subcontribution_schema(self, **kwargs):
        can_manage = self.event.can_manage(session.user, permission='contributions')
        return SubContributionSchema(context={'hide_restricted_data': not can_manage}, **kwargs)


@json_errors
class RHSubContribution(SubContributionMixin, RHContribution):
    def _process_args(self):
        RHContribution._process_args(self)
        self.subcontrib = (SubContribution.query.with_parent(self.contrib)
                           .filter_by(id=request.view_args['subcontrib_id'], is_deleted=False)
                           .first_or_404())

    def _process_GET(self):
        return self._subcontribution_schema().jsonify(self.subcontrib)


@json_errors
class RHSubContributionList(SubContributionMixin, RHListBase, RHContribution):
    schema = SubContributionSchema

    def _query(self):
        return (SubContribution.query.with_parent(self.contrib)
                .filter(~SubContribution.is_deleted)
                .order_by(SubContribution.position))

    def _dump_schema(self):
        return self._subcontribution_schema(many=True)


ENDPOINTS = [
    Endpoint(rule='/events/<int:event_id>/contributions/<int:contrib_id>/subcontributions',
             name='subcontributions', rh=RHSubContributionList, schema=SubContributionSchema, many=True,
             summary='List the subcontributions of a contribution', tag='Contributions'),
    Endpoint(rule='/events/<int:event_id>/contributions/<int:contrib_id>/subcontributions/<int:subcontrib_id>',
             name='subcontribution', rh=RHSubContribution, schema=SubContributionSchema,
             summary='Subcontribution details', tag='Contributions'),
]
