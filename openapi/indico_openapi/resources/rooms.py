# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from flask import request
from marshmallow import fields

from indico.modules.rb.controllers import RHRoomBookingBase
from indico.modules.rb.models.rooms import Room
from indico.modules.rb.schemas import RoomSchema as CoreRoomSchema
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, ListArgs, RHListBase


class RoomSchema(DescribedFieldsMixin, CoreRoomSchema):
    class Meta(CoreRoomSchema.Meta):
        fields = ('id', 'name', 'full_name', 'verbose_name', 'location_id', 'location_name', 'site', 'building',
                  'floor', 'number', 'division', 'capacity', 'surface_area', 'latitude', 'longitude', 'telephone',
                  'key_location', 'comments', 'owner_name', 'available_equipment', 'is_public', 'is_reservable',
                  'reservations_need_confirmation', 'max_advance_days', 'has_photo', 'map_url')
        descriptions = {
            'id': 'Numeric identifier of the room, unique across the whole instance.',
            'name': 'Name of the room, either its verbose name or `building/floor-number`.',
            'full_name': 'Name of the room including its verbose name, such as `500/1-001 - Main Auditorium`.',
            'verbose_name': 'Friendly name of the room, or `null` when it only has a number.',
            'location_id': 'Identifier of the location the room belongs to.',
            'location_name': 'Name of the location the room belongs to, such as `CERN`.',
            'site': 'Site of the location the room is in.',
            'building': 'Building the room is in.',
            'floor': 'Floor the room is on.',
            'number': 'Number of the room on its floor.',
            'division': 'Division the room belongs to.',
            'capacity': 'Number of people the room holds.',
            'surface_area': 'Surface of the room, in square metres.',
            'latitude': 'Latitude of the room, as a decimal string.',
            'longitude': 'Longitude of the room, as a decimal string.',
            'telephone': 'Phone number of the room.',
            'key_location': 'Where to get the key of the room.',
            'comments': 'Free-text notes the room managers wrote about the room.',
            'owner_name': 'Full name of the person responsible for the room.',
            'available_equipment': 'Names of the equipment available in the room, such as `Video conference`.',
            'is_public': 'Whether anybody can book the room without a manager approving it.',
            'is_reservable': 'Whether the room can be booked at all.',
            'reservations_need_confirmation': 'Whether a booking has to be accepted by a manager of the room.',
            'max_advance_days': 'How many days in advance the room can be booked, or `null` when unlimited.',
            'has_photo': 'Whether the room has a photo, served under the room booking interface.',
            'map_url': 'Absolute URL of the room on an external map, or `null` when there is none.',
        }

    available_equipment = fields.Function(lambda room: sorted(eq.name for eq in room.available_equipment))


class RoomReferenceSchema(DescribedFieldsMixin, CoreRoomSchema):
    class Meta(CoreRoomSchema.Meta):
        fields = ('id', 'name', 'full_name')
        descriptions = RoomSchema.Meta.descriptions


class RoomListArgs(ListArgs):
    location_id = fields.Integer(load_default=None,
                                 metadata={'description': 'Only list the rooms of this location.'})


class RoomMixin:
    """Access checks shared by the room endpoints.

    Rooms are never access-restricted, so anybody allowed into the room
    booking system sees all of them. Deleted rooms are never returned.
    """

    def _room_query(self):
        return Room.query.filter(~Room.is_deleted).order_by(Room.building, Room.floor, Room.number, Room.id)


@json_errors
class RHRoom(RoomMixin, RHRoomBookingBase):
    def _process_args(self):
        self.room = self._room_query().filter(Room.id == request.view_args['room_id']).first_or_404()

    def _process_GET(self):
        return RoomSchema().jsonify(self.room)


@json_errors
class RHRoomList(RoomMixin, RHListBase, RHRoomBookingBase):
    args_schema = RoomListArgs
    schema = RoomSchema

    def _query(self, location_id):
        query = self._room_query()
        if location_id is not None:
            query = query.filter(Room.location_id == location_id)
        return query

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(rule='/rooms', name='rooms', rh=RHRoomList, schema=RoomSchema, many=True,
             summary='List the rooms that can be booked', tag='Rooms'),
    Endpoint(rule='/rooms/<int:room_id>', name='room', rh=RHRoom, schema=RoomSchema,
             summary='Room details', tag='Rooms'),
]
