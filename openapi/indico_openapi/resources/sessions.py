# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from flask import request, session
from marshmallow import fields
from werkzeug.exceptions import Forbidden

from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.core.marshmallow import mm
from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.modules.events.sessions.models.sessions import Session
from indico.modules.events.sessions.models.types import SessionType
from indico.modules.events.sessions.schemas import BasicSessionSchema, SessionBlockSchema
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase


class SessionTypeSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    class Meta:
        model = SessionType
        fields = ('id', 'name', 'code', 'is_poster')
        descriptions = {
            'id': 'Numeric identifier of the session type.',
            'name': 'Name of the type, such as `Plenary`.',
            'code': 'Programme code assigned to the type.',
            'is_poster': 'Whether sessions of this type are poster sessions.',
        }


class BlockSchema(DescribedFieldsMixin, SessionBlockSchema):
    class Meta(SessionBlockSchema.Meta):
        descriptions = {
            'id': 'Numeric identifier of the session block.',
            'title': 'Title of the block, empty when it takes the title of its session.',
            'code': 'Programme code assigned to the block.',
            'start_dt': 'Start of the block, in UTC, or `null` if it is not scheduled.',
            'end_dt': 'End of the block, in UTC, or `null` if it is not scheduled.',
            'duration': 'Length of the block, in seconds.',
            'room_name': 'Name of the room, such as `500/1-001`.',
            'room_name_verbose': 'Room including its friendly name, such as `500/1-001 - Main Auditorium`.',
        }


class SessionSchema(DescribedFieldsMixin, BasicSessionSchema):
    class Meta(BasicSessionSchema.Meta):
        fields = ('id', 'title', 'friendly_id', 'code', 'description', 'type', 'default_contribution_duration',
                  'text_color', 'background_color', 'venue_name', 'room_name', 'address', 'inherit_location',
                  'is_protected', 'blocks')
        descriptions = {
            'id': 'Numeric identifier of the session, unique across the whole instance.',
            'title': 'Title of the session.',
            'friendly_id': 'Number shown to users, unique within the event.',
            'code': 'Programme code assigned to the session.',
            'description': 'Description of the session, as HTML.',
            'type': 'Session type defined by the event, if any.',
            'default_contribution_duration': 'Length new contributions of this session get by default, in seconds.',
            'text_color': 'Colour of the text in the timetable, as `#rrggbb`.',
            'background_color': 'Colour of the background in the timetable, as `#rrggbb`.',
            'venue_name': 'Name of the venue, such as `CERN`.',
            'room_name': 'Name of the room, such as `500/1-001`.',
            'address': 'Postal address of the venue.',
            'inherit_location': 'Whether the location is taken from the event holding the session.',
            'is_protected': 'Whether reading the session requires permissions beyond those of the event.',
            'blocks': 'Blocks the session is scheduled in.',
        }

    type = fields.Nested(SessionTypeSchema)
    text_color = fields.Function(lambda sess: f'#{sess.colors.text}')
    background_color = fields.Function(lambda sess: f'#{sess.colors.background}')
    is_protected = fields.Function(lambda sess: sess.effective_protection_mode != ProtectionMode.public)
    blocks = fields.List(fields.Nested(BlockSchema))


@json_errors
class RHSession(RHProtectedEventBase):
    def _process_args(self):
        RHProtectedEventBase._process_args(self)
        self.sess = (Session.query.with_parent(self.event)
                     .filter_by(id=request.view_args['session_id'], is_deleted=False)
                     .first_or_404())

    def _check_access(self):
        RHProtectedEventBase._check_access(self)
        if not self.sess.can_access(session.user):
            raise Forbidden

    def _process_GET(self):
        return SessionSchema().jsonify(self.sess)


@json_errors
class RHSessionList(RHListBase, RHProtectedEventBase):
    schema = SessionSchema

    def _query(self):
        return (Session.query.with_parent(self.event)
                .filter(~Session.is_deleted)
                .order_by(Session.friendly_id))


ENDPOINTS = [
    Endpoint(rule='/events/<int:event_id>/sessions', name='sessions', rh=RHSessionList, schema=SessionSchema,
             many=True, summary='List the sessions of an event', tag='Sessions'),
    Endpoint(rule='/events/<int:event_id>/sessions/<int:session_id>', name='session', rh=RHSession,
             schema=SessionSchema, summary='Session details', tag='Sessions'),
]
