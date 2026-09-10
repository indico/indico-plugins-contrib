# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from flask import request
from marshmallow import fields, post_dump

from indico.modules.rb.controllers import RHRoomBookingBase
from indico.modules.rb.models.locations import Location
from indico.modules.rb.models.rooms import Room
from indico.modules.rb.schemas import LocationsSchema as CoreLocationSchema
from indico.util.string import natural_sort_key
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase
from indico_openapi.resources.rooms import RoomReferenceSchema


class LocationSchema(DescribedFieldsMixin, CoreLocationSchema):
    class Meta(CoreLocationSchema.Meta):
        fields = ('id', 'name')
        descriptions = {
            'id': 'Numeric identifier of the location, unique across the whole instance.',
            'name': 'Name of the location, such as `CERN`.',
            'rooms': 'Rooms of the location, deleted ones excluded.',
        }


class LocationDetailsSchema(LocationSchema):
    class Meta(LocationSchema.Meta):
        fields = ('id', 'name', 'rooms')

    rooms = fields.Nested(RoomReferenceSchema, many=True)

    @post_dump
    def _sort_rooms(self, data, **kwargs):
        data['rooms'].sort(key=lambda room: natural_sort_key(room['full_name']))
        return data


class LocationMixin:
    """Access checks shared by the location endpoints.

    Locations are never access-restricted, so anybody allowed into the room
    booking system sees all of them. A location is only served while it holds
    at least one room that is not deleted, so an empty one is as good as gone.
    """

    def _location_query(self):
        return (Location.query
                .filter(~Location.is_deleted,
                        Room.query.filter(Room.location_id == Location.id, ~Room.is_deleted).exists())
                .order_by(Location.name, Location.id))


@json_errors
class RHLocation(LocationMixin, RHRoomBookingBase):
    def _process_args(self):
        self.location = (self._location_query()
                         .filter(Location.id == request.view_args['location_id']).first_or_404())

    def _process_GET(self):
        return LocationDetailsSchema().jsonify(self.location)


@json_errors
class RHLocationList(LocationMixin, RHListBase, RHRoomBookingBase):
    schema = LocationSchema

    def _query(self):
        return self._location_query()

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(rule='/locations', name='locations', rh=RHLocationList, schema=LocationSchema, many=True,
             summary='List the locations rooms belong to', tag='Locations'),
    Endpoint(rule='/locations/<int:location_id>', name='location', rh=RHLocation, schema=LocationDetailsSchema,
             summary='Location details', tag='Locations'),
]
