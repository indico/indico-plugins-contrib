# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from flask import request

from indico.core.db import db
from indico.core.marshmallow import mm
from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.modules.events.sessions.models.types import SessionType
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase


class SessionTypeSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """Kind of session an event distinguishes, such as a plenary or a poster session."""

    class Meta:
        model = SessionType
        fields = ('id', 'event_id', 'name', 'code', 'is_poster')
        descriptions = {
            'id': 'Numeric identifier of the session type, unique across the whole instance.',
            'event_id': 'Identifier of the event defining the type.',
            'name': 'Name of the type, such as `Plenary`.',
            'code': 'Programme code assigned to the type.',
            'is_poster': 'Whether the sessions of this type are poster sessions.',
        }


class SessionTypeMixin:
    def _type_query(self):
        return SessionType.query.with_parent(self.event).order_by(db.func.lower(SessionType.name), SessionType.id)


@json_errors
class RHSessionType(SessionTypeMixin, RHProtectedEventBase):
    def _process_args(self):
        RHProtectedEventBase._process_args(self)
        self.session_type = self._type_query().filter(SessionType.id == request.view_args['type_id']).first_or_404()

    def _process_GET(self):
        return SessionTypeSchema().jsonify(self.session_type)


@json_errors
class RHSessionTypeList(SessionTypeMixin, RHListBase, RHProtectedEventBase):
    schema = SessionTypeSchema

    def _query(self):
        return self._type_query()

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(rule='/events/<int:event_id>/session-types', name='session_types', rh=RHSessionTypeList,
             schema=SessionTypeSchema, many=True, summary='List the session types of an event', tag='Sessions'),
    Endpoint(rule='/events/<int:event_id>/session-types/<int:type_id>', name='session_type', rh=RHSessionType,
             schema=SessionTypeSchema, summary='Session type details', tag='Sessions'),
]
