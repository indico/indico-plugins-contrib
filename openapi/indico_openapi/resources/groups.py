# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from operator import itemgetter

from flask import request
from marshmallow import fields, post_dump
from sqlalchemy.orm import joinedload
from werkzeug.exceptions import Forbidden

from indico.core.config import config
from indico.core.db import db
from indico.core.marshmallow import mm
from indico.modules.admin import RHAdminBase
from indico.modules.groups.models.groups import LocalGroup
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase
from indico_openapi.schemas import MemberSchema


class LocalGroupSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """Group of users defined in Indico itself.

    Groups coming from an external identity provider are not served: Indico only
    keeps their name and asks the provider every time it needs the members.
    """

    class Meta:
        model = LocalGroup
        fields = ('id', 'name', 'identifier', 'members')
        descriptions = {
            'id': 'Numeric identifier of the group, unique across the whole instance.',
            'name': 'Name of the group, unique across the whole instance regardless of case.',
            'identifier': 'Identifier of the group as used by Indico ACLs, such as `Group::42`.',
            'members': 'Users belonging to the group, sorted by identifier.',
        }

    identifier = fields.String(attribute='proxy.identifier')
    members = fields.List(fields.Nested(MemberSchema))

    @post_dump
    def _sort_members(self, data, **kwargs):
        # the relationship is a set, so without this the order changes from one request to the next
        data['members'].sort(key=itemgetter('id'))
        return data


class GroupMixin:
    """Access checks shared by the group endpoints.

    A group carries the email address of every member, and the only interface
    serving a group together with its members is the administration area. So
    these endpoints are restricted to administrators, and they honour the same
    setting that hides local groups from it.
    """

    def _check_access(self):
        RHAdminBase._check_access(self)
        if not config.LOCAL_GROUPS:
            raise Forbidden('Local groups are disabled.')

    def _group_query(self):
        return (LocalGroup.query
                .options(joinedload(LocalGroup.members))
                .order_by(db.func.lower(LocalGroup.name)))


@json_errors
class RHLocalGroup(GroupMixin, RHAdminBase):
    def _process_args(self):
        self.group = self._group_query().filter(LocalGroup.id == request.view_args['group_id']).first_or_404()

    def _process_GET(self):
        return LocalGroupSchema().jsonify(self.group)


@json_errors
class RHLocalGroupList(GroupMixin, RHListBase, RHAdminBase):
    schema = LocalGroupSchema

    def _query(self):
        return self._group_query()

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(rule='/groups', name='groups', rh=RHLocalGroupList, schema=LocalGroupSchema, many=True,
             summary='List the local groups', tag='Groups'),
    Endpoint(rule='/groups/<int:group_id>', name='group', rh=RHLocalGroup, schema=LocalGroupSchema,
             summary='Local group details', tag='Groups'),
]
