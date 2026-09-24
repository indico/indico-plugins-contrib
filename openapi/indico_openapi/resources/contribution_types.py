# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from flask import request

from indico.core.db import db
from indico.modules.events.contributions.models.types import ContributionType
from indico.modules.events.contributions.schemas import ContributionTypeSchema as CoreContributionTypeSchema
from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase


class ContributionTypeSchema(DescribedFieldsMixin, CoreContributionTypeSchema):
    """Kind of contribution an event distinguishes, such as a talk or a poster.

    The types themselves are not restricted: any contribution shows its own.
    Private ones only differ in that abstract submitters cannot propose them.
    """

    class Meta(CoreContributionTypeSchema.Meta):
        fields = ('id', 'event_id', 'name', 'description', 'is_private')
        descriptions = {
            'id': 'Numeric identifier of the contribution type, unique across the whole instance.',
            'event_id': 'Identifier of the event defining the type.',
            'name': 'Name of the type, such as `Poster` or `Oral`.',
            'description': 'Description of the type, as Markdown.',
            'is_private': 'Whether only the managers may assign the type; abstract submitters cannot propose it.',
        }


class ContributionTypeMixin:
    def _type_query(self):
        return ContributionType.query.with_parent(self.event).order_by(
            db.func.lower(ContributionType.name), ContributionType.id
        )


@json_errors
class RHContributionType(ContributionTypeMixin, RHProtectedEventBase):
    def _process_args(self):
        RHProtectedEventBase._process_args(self)
        self.contrib_type = (
            self._type_query().filter(ContributionType.id == request.view_args['type_id']).first_or_404()
        )

    def _process_GET(self):
        return ContributionTypeSchema().jsonify(self.contrib_type)


@json_errors
class RHContributionTypeList(ContributionTypeMixin, RHListBase, RHProtectedEventBase):
    schema = ContributionTypeSchema

    def _query(self):
        return self._type_query()

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(
        rule='/events/<int:event_id>/contribution-types',
        name='contribution_types',
        rh=RHContributionTypeList,
        schema=ContributionTypeSchema,
        many=True,
        summary='List the contribution types of an event',
        tag='Contributions',
    ),
    Endpoint(
        rule='/events/<int:event_id>/contribution-types/<int:type_id>',
        name='contribution_type',
        rh=RHContributionType,
        schema=ContributionTypeSchema,
        summary='Details of one contribution type of an event',
        tag='Contributions',
    ),
]
