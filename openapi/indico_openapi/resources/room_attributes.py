# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from flask import request, session
from marshmallow import fields

from indico.core.marshmallow import mm
from indico.modules.rb.controllers import RHRoomBookingBase
from indico.modules.rb.models.room_attributes import RoomAttribute, RoomAttributeAssociation
from indico.modules.rb.models.rooms import Room
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase


class RoomAttributeValueSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """Value a room carries for one of the attributes the administrators defined."""

    class Meta:
        model = RoomAttributeAssociation
        fields = ('attribute_id', 'name', 'title', 'value', 'is_hidden')
        descriptions = {
            'attribute_id': 'Numeric identifier of the attribute, unique across the whole instance.',
            'name': 'Name of the attribute, unique across the whole instance, such as `manager-group`.',
            'title': 'Name of the attribute as it is displayed.',
            'value': 'Value stored for this room, in the shape the administrators use for the attribute.',
            'is_hidden': 'Whether the attribute is only shown to the managers of the room.',
        }

    name = fields.String(attribute='attribute.name')
    title = fields.String(attribute='attribute.title')
    is_hidden = fields.Boolean(attribute='attribute.is_hidden')


@json_errors
class RHRoomAttributeList(RHListBase, RHRoomBookingBase):
    """Attribute values of one room.

    A hidden attribute is what the administrators keep out of the room details,
    so it is served to the managers of the room and to nobody else.
    """

    schema = RoomAttributeValueSchema

    def _process_args(self):
        self.room = Room.query.filter(Room.id == request.view_args['room_id'], ~Room.is_deleted).first_or_404()

    def _query(self):
        return (RoomAttributeAssociation.query
                .filter(RoomAttributeAssociation.room_id == self.room.id)
                .join(RoomAttribute)
                .order_by(RoomAttribute.name, RoomAttribute.id))

    def _can_access(self, obj):
        return not obj.attribute.is_hidden or self.room.can_manage(session.user)


ENDPOINTS = [
    Endpoint(rule='/rooms/<int:room_id>/attributes', name='room_attributes', rh=RHRoomAttributeList,
             schema=RoomAttributeValueSchema, many=True, summary='List the attribute values of a room', tag='Rooms'),
]
