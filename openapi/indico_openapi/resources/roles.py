# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from operator import itemgetter

from flask import request, session
from marshmallow import fields, post_dump
from sqlalchemy.orm import joinedload
from werkzeug.exceptions import Forbidden

from indico.core.marshmallow import mm
from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.modules.events.models.roles import EventRole
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase
from indico_openapi.schemas import MemberSchema


class EventRoleSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """Role an event defines to grant permissions to a group of people.

    Core has no schema covering the whole role: the management interface serves
    the members without the id, and the protection interface the id without the
    members.
    """

    class Meta:
        model = EventRole
        fields = ('id', 'name', 'code', 'color', 'members')
        descriptions = {
            'id': 'Numeric identifier of the role, unique across the whole instance.',
            'name': 'Name of the role, such as `Programme Committee`.',
            'code': 'Short uppercase code of the role, unique within the event, such as `PC`.',
            'color': 'Colour the role is shown in, as a six digit hex triplet without the leading `#`.',
            'members': 'Users holding the role, sorted by identifier.',
        }

    members = fields.List(fields.Nested(MemberSchema))

    @post_dump
    def _sort_members(self, data, **kwargs):
        # the relationship is a set, so without this the order changes from one request to the next
        data['members'].sort(key=itemgetter('id'))
        return data


class RoleMixin:
    """Access checks shared by the event role endpoints.

    A role carries the email address of everybody holding it, which is what makes
    it manager only: that is the audience the management interface serves the
    members to. Anybody else only gets to see a role through the ACL of the
    object it grants access to, as a name and a code.
    """

    def _check_access(self):
        RHProtectedEventBase._check_access(self)
        if not self.event.can_manage(session.user):
            raise Forbidden

    def _role_query(self):
        return (EventRole.query.with_parent(self.event)
                .options(joinedload('members'))
                .order_by(EventRole.code))


@json_errors
class RHEventRole(RoleMixin, RHProtectedEventBase):
    def _process_args(self):
        RHProtectedEventBase._process_args(self)
        self.role = self._role_query().filter(EventRole.id == request.view_args['role_id']).first_or_404()

    def _process_GET(self):
        return EventRoleSchema().jsonify(self.role)


@json_errors
class RHEventRoleList(RoleMixin, RHListBase, RHProtectedEventBase):
    schema = EventRoleSchema

    def _query(self):
        return self._role_query()

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(rule='/events/<int:event_id>/roles', name='roles', rh=RHEventRoleList, schema=EventRoleSchema, many=True,
             summary='List the roles of an event', tag='Roles'),
    Endpoint(rule='/events/<int:event_id>/roles/<int:role_id>', name='role', rh=RHEventRole, schema=EventRoleSchema,
             summary='Details of one role of an event', tag='Roles'),
]
