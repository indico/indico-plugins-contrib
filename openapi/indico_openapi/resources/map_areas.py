# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from flask import request

from indico.modules.rb.controllers import RHRoomBookingBase
from indico.modules.rb.models.map_areas import MapArea
from indico.modules.rb.schemas import MapAreaSchema as CoreMapAreaSchema
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase


class MapAreaSchema(DescribedFieldsMixin, CoreMapAreaSchema):
    """Rectangle of the map the room booking interface can zoom to."""

    class Meta(CoreMapAreaSchema.Meta):
        descriptions = {
            'id': 'Numeric identifier of the area, unique across the whole instance.',
            'name': 'Name of the area, such as `Main site`.',
            'is_default': 'Whether the map opens on this area. At most one area is the default one.',
            'top_left_latitude': 'Latitude of the north-west corner.',
            'top_left_longitude': 'Longitude of the north-west corner.',
            'bottom_right_latitude': 'Latitude of the south-east corner.',
            'bottom_right_longitude': 'Longitude of the south-east corner.',
        }


class MapAreaMixin:
    """Query shared by the map area endpoints.

    Map areas describe the map every user of the room booking system sees, so
    anybody allowed in gets all of them.
    """

    def _area_query(self):
        return MapArea.query.order_by(MapArea.name, MapArea.id)


@json_errors
class RHMapArea(MapAreaMixin, RHRoomBookingBase):
    def _process_args(self):
        self.area = self._area_query().filter(MapArea.id == request.view_args['area_id']).first_or_404()

    def _process_GET(self):
        return MapAreaSchema().jsonify(self.area)


@json_errors
class RHMapAreaList(MapAreaMixin, RHListBase, RHRoomBookingBase):
    schema = MapAreaSchema

    def _query(self):
        return self._area_query()

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(rule='/map-areas', name='map_areas', rh=RHMapAreaList, schema=MapAreaSchema, many=True,
             summary='List the areas of the room map', tag='Rooms'),
    Endpoint(rule='/map-areas/<int:area_id>', name='map_area', rh=RHMapArea, schema=MapAreaSchema,
             summary='Details of one area of the room map', tag='Rooms'),
]
