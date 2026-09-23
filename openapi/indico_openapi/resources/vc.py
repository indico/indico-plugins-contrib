# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from flask import request, session
from marshmallow import fields

from indico.core.db import db
from indico.core.marshmallow import mm
from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.modules.vc.models.vc_rooms import VCRoom, VCRoomEventAssociation, VCRoomLinkType, VCRoomStatus
from indico.modules.vc.util import get_vc_plugins
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase


class VCRoomSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """Videoconference attached to an event, a contribution or a session block.

    Core has no schema for one because every videoconference is rendered by the
    plugin providing it. The answer of that plugin is left out: it is shaped by
    each plugin rather than by Indico, and it holds the credentials to join,
    which the interface only ever renders into a button.
    """

    class Meta:
        model = VCRoomEventAssociation
        fields = ('id', 'event_id', 'videoconference_room_id', 'type', 'name', 'status', 'link_type',
                  'contribution_id', 'session_block_id', 'show')
        descriptions = {
            'id': 'Numeric identifier of the link between the event and the videoconference, unique across the '
                  'whole instance. The same videoconference linked twice gives two of these.',
            'event_id': 'Identifier of the event the videoconference is attached to.',
            'videoconference_room_id': 'Identifier of the videoconference itself, which several events may share.',
            'type': 'Name of the videoconference plugin the room lives in, such as `zoom`.',
            'name': 'Name of the videoconference room.',
            'status': 'Whether the room still exists in the service: `created`, or `deleted` once the service '
                      'dropped it. Only managers see a deleted one.',
            'link_type': 'What the videoconference is attached to: `event`, `contribution` or `block`.',
            'contribution_id': 'Identifier of the contribution the videoconference is attached to, or `null` when '
                               'it is attached to something else.',
            'session_block_id': 'Identifier of the session block the videoconference is attached to, or `null` '
                                'when it is attached to something else.',
            'show': 'Whether the videoconference is shown on the event page. Only managers see a hidden one.',
        }

    videoconference_room_id = fields.Integer(attribute='vc_room_id')
    type = fields.String(attribute='vc_room.type')
    name = fields.String(attribute='vc_room.name')
    status = fields.Enum(VCRoomStatus, attribute='vc_room.status')
    link_type = fields.Enum(VCRoomLinkType)


class VCRoomMixin:
    """Access checks shared by the videoconference endpoints.

    Anybody who can see the event gets the videoconferences its page lists, and
    its managers also get the ones the page hides: the ones marked as hidden and
    the ones the service no longer has, which are the two the management page
    keeps showing.

    A videoconference whose plugin is not installed is served to nobody, the way
    the interface drops it from both pages, since the plugin that knows what it
    is and how to reach it is the one that is gone.
    """

    def _process_args(self):
        RHProtectedEventBase._process_args(self)
        self.can_manage = self.event.can_manage(session.user)

    def _vc_room_query(self):
        query = (VCRoomEventAssociation.query
                 .filter(VCRoomEventAssociation.event_id == self.event.id)
                 .join(VCRoomEventAssociation.vc_room)
                 .filter(VCRoom.type.in_(get_vc_plugins()))
                 .order_by(db.func.lower(VCRoom.name), VCRoomEventAssociation.id))
        if not self.can_manage:
            query = query.filter(VCRoomEventAssociation.show, VCRoom.status != VCRoomStatus.deleted)
        return query


@json_errors
class RHVCRoom(VCRoomMixin, RHProtectedEventBase):
    def _process_args(self):
        VCRoomMixin._process_args(self)
        self.vc_room = (self._vc_room_query()
                        .filter(VCRoomEventAssociation.id == request.view_args['vc_room_id']).first_or_404())

    def _process_GET(self):
        return VCRoomSchema().jsonify(self.vc_room)


@json_errors
class RHVCRoomList(VCRoomMixin, RHListBase, RHProtectedEventBase):
    schema = VCRoomSchema

    def _query(self):
        return self._vc_room_query()

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(rule='/events/<int:event_id>/videoconference-rooms', name='vc_rooms', rh=RHVCRoomList,
             schema=VCRoomSchema, many=True, summary='List the videoconferences of an event', tag='Videoconferences'),
    Endpoint(rule='/events/<int:event_id>/videoconference-rooms/<int:vc_room_id>', name='vc_room', rh=RHVCRoom,
             schema=VCRoomSchema, summary='Details of one videoconference of an event', tag='Videoconferences'),
]
