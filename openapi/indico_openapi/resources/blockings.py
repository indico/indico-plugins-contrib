# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from flask import request
from marshmallow import fields

from indico.modules.rb.controllers import RHRoomBookingBase
from indico.modules.rb.models.blocked_rooms import BlockedRoom
from indico.modules.rb.models.blockings import Blocking
from indico.modules.rb.schemas import BlockedRoomSchema as CoreBlockedRoomSchema
from indico.modules.rb.schemas import BlockingSchema as CoreBlockingSchema
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, ListArgs, RHListBase
from indico_openapi.resources.rooms import RoomReferenceSchema


class BlockedRoomSchema(DescribedFieldsMixin, CoreBlockedRoomSchema):
    class Meta(CoreBlockedRoomSchema.Meta):
        descriptions = {
            'room': 'Room the blocking applies to.',
            'state': 'Where the block of this room stands: `pending`, `accepted` or `rejected`.',
            'rejection_reason': 'Why the block was rejected, or `null` when it was not rejected.',
            'rejected_by': 'Full name of the room manager who rejected the block, or `null` when it was not rejected.',
        }

    room = fields.Nested(RoomReferenceSchema)


class BlockingSchema(DescribedFieldsMixin, CoreBlockingSchema):
    class Meta(CoreBlockingSchema.Meta):
        fields = ('id', 'start_date', 'end_date', 'reason', 'created_by', 'allowed', 'blocked_rooms')
        descriptions = {
            'id': 'Numeric identifier of the blocking, unique across the whole instance.',
            'start_date': 'First day the blocking applies to.',
            'end_date': 'Last day the blocking applies to.',
            'reason': 'Why the rooms were blocked, as entered by the person who blocked them.',
            'created_by': 'Full name of the person who created the blocking.',
            'allowed': 'Identifiers of the users and groups that may still book the rooms while the blocking is '
                       'active, such as `["User:42"]`.',
            'blocked_rooms': 'Rooms the blocking applies to, along with the answer of their managers.',
        }

    blocked_rooms = fields.Nested(BlockedRoomSchema, many=True)


class BlockingListArgs(ListArgs):
    room_id = fields.Integer(load_default=None,
                             metadata={'description': 'Only list the blockings that apply to this room.'})


class BlockingMixin:
    """Access checks shared by the blocking endpoints.

    A blocking is not access-restricted: anybody allowed into the room booking
    system sees which rooms are blocked and who may still book them, which is
    what the blocking list of the room booking interface shows.
    """

    def _blocking_query(self):
        return Blocking.query.order_by(Blocking.start_date.desc(), Blocking.id)


@json_errors
class RHBlocking(BlockingMixin, RHRoomBookingBase):
    def _process_args(self):
        self.blocking = (self._blocking_query()
                         .filter(Blocking.id == request.view_args['blocking_id']).first_or_404())

    def _process_GET(self):
        return BlockingSchema().jsonify(self.blocking)


@json_errors
class RHBlockingList(BlockingMixin, RHListBase, RHRoomBookingBase):
    args_schema = BlockingListArgs
    schema = BlockingSchema

    def _query(self, room_id):
        query = self._blocking_query()
        if room_id is not None:
            query = query.filter(Blocking.blocked_rooms.any(BlockedRoom.room_id == room_id))
        return query

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(rule='/blockings', name='blockings', rh=RHBlockingList, schema=BlockingSchema, many=True,
             summary='List the blockings that keep rooms from being booked', tag='Blockings'),
    Endpoint(rule='/blockings/<int:blocking_id>', name='blocking', rh=RHBlocking, schema=BlockingSchema,
             summary='Blocking details', tag='Blockings'),
]
