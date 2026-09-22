# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from flask import request
from marshmallow import fields

from indico.modules.rb.controllers import RHRoomBookingBase
from indico.modules.rb.models.equipment import EquipmentType
from indico.modules.rb.models.room_features import RoomFeature
from indico.modules.rb.schemas import EquipmentTypeSchema as CoreEquipmentTypeSchema
from indico.modules.rb.schemas import RoomFeatureSchema as CoreRoomFeatureSchema
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase


class RoomFeatureSchema(DescribedFieldsMixin, CoreRoomFeatureSchema):
    """Kind of equipment a room can be searched by, such as videoconference."""

    class Meta(CoreRoomFeatureSchema.Meta):
        descriptions = {
            'id': 'Numeric identifier of the feature, unique across the whole instance.',
            'name': 'Name of the feature as used in the room search, such as `vc`.',
            'title': 'Name of the feature as displayed, such as `Videoconference`.',
            'icon': 'Name of the icon shown next to the feature, or an empty string when there is none.',
        }


class EquipmentTypeSchema(DescribedFieldsMixin, CoreEquipmentTypeSchema):
    """Piece of equipment a room can have, such as a webcam."""

    class Meta(CoreEquipmentTypeSchema.Meta):
        descriptions = {
            'id': 'Numeric identifier of the equipment type, unique across the whole instance.',
            'name': 'Name of the equipment type, such as `Webcam`.',
            'features': 'Features this equipment provides, which is what a room search filters by.',
            'used': 'Whether at least one room that still exists has this equipment.',
        }

    features = fields.Nested(RoomFeatureSchema, many=True)
    used = fields.Function(lambda equipment: any(not room.is_deleted for room in equipment.rooms))


class EquipmentTypeMixin:
    """Query shared by the equipment type endpoints.

    The equipment catalogue describes the room search every user of the room
    booking system gets, so anybody allowed in sees all of it.
    """

    def _equipment_query(self):
        return EquipmentType.query.order_by(EquipmentType.name, EquipmentType.id)


class RoomFeatureMixin:
    """Query shared by the room feature endpoints.

    Only the administration area lists the features on their own, while every
    user of the room booking system already gets them next to the equipment
    they belong to.
    """

    def _feature_query(self):
        return RoomFeature.query.order_by(RoomFeature.title, RoomFeature.id)


@json_errors
class RHEquipmentType(EquipmentTypeMixin, RHRoomBookingBase):
    def _process_args(self):
        self.equipment = (self._equipment_query()
                          .filter(EquipmentType.id == request.view_args['equipment_type_id']).first_or_404())

    def _process_GET(self):
        return EquipmentTypeSchema().jsonify(self.equipment)


@json_errors
class RHEquipmentTypeList(EquipmentTypeMixin, RHListBase, RHRoomBookingBase):
    schema = EquipmentTypeSchema

    def _query(self):
        return self._equipment_query()

    def _can_access(self, obj):
        return True


@json_errors
class RHRoomFeature(RoomFeatureMixin, RHRoomBookingBase):
    def _process_args(self):
        self.feature = (self._feature_query()
                        .filter(RoomFeature.id == request.view_args['feature_id']).first_or_404())

    def _process_GET(self):
        return RoomFeatureSchema().jsonify(self.feature)


@json_errors
class RHRoomFeatureList(RoomFeatureMixin, RHListBase, RHRoomBookingBase):
    schema = RoomFeatureSchema

    def _query(self):
        return self._feature_query()

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(rule='/equipment-types', name='equipment_types', rh=RHEquipmentTypeList, schema=EquipmentTypeSchema,
             many=True, summary='List the equipment a room can have', tag='Rooms'),
    Endpoint(rule='/equipment-types/<int:equipment_type_id>', name='equipment_type', rh=RHEquipmentType,
             schema=EquipmentTypeSchema, summary='Equipment type details', tag='Rooms'),
    Endpoint(rule='/room-features', name='room_features', rh=RHRoomFeatureList, schema=RoomFeatureSchema, many=True,
             summary='List the features a room can be searched by', tag='Rooms'),
    Endpoint(rule='/room-features/<int:feature_id>', name='room_feature', rh=RHRoomFeature, schema=RoomFeatureSchema,
             summary='Room feature details', tag='Rooms'),
]
