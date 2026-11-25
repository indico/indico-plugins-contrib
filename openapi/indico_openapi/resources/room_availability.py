# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 Unconventional
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from flask import request

from indico.core.marshmallow import mm
from indico.modules.rb.controllers import RHRoomBookingBase
from indico.modules.rb.models.room_bookable_hours import BookableHours
from indico.modules.rb.models.room_nonbookable_periods import NonBookablePeriod
from indico.modules.rb.models.rooms import Room
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase


class BookableHoursSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """Hours of the day a room can be booked for, outside of which it is taken."""

    class Meta:
        model = BookableHours
        fields = ('id', 'room_id', 'start_time', 'end_time', 'weekday')
        descriptions = {
            'id': 'Numeric identifier of the entry, unique across the whole instance.',
            'room_id': 'Identifier of the room the hours belong to.',
            'start_time': 'Time of the day bookings may start at, in the timezone of the Indico instance.',
            'end_time': 'Time of the day bookings must end by, in the timezone of the Indico instance.',
            'weekday': 'Day the hours apply to, such as `mon`, or `null` when they apply to every day.',
        }


class NonBookablePeriodSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """Period a room cannot be booked for, such as a shutdown."""

    class Meta:
        model = NonBookablePeriod
        fields = ('room_id', 'start_dt', 'end_dt')
        descriptions = {
            'room_id': 'Identifier of the room the period belongs to.',
            'start_dt': 'Start of the period, in the timezone of the Indico instance.',
            'end_dt': 'End of the period, in the timezone of the Indico instance.',
        }


class RoomAvailabilityMixin:
    """Room lookup shared by the availability endpoints.

    When a room can be booked is what the booking calendar is built on, so
    anybody allowed into the room booking system gets it.
    """

    def _process_args(self):
        self.room = Room.query.filter(Room.id == request.view_args['room_id'], ~Room.is_deleted).first_or_404()

    def _can_access(self, obj):
        return True


@json_errors
class RHBookableHoursList(RoomAvailabilityMixin, RHListBase, RHRoomBookingBase):
    schema = BookableHoursSchema

    def _query(self):
        return BookableHours.query.filter(BookableHours.room_id == self.room.id).order_by(
            BookableHours.start_time, BookableHours.end_time, BookableHours.id
        )


@json_errors
class RHNonBookablePeriodList(RoomAvailabilityMixin, RHListBase, RHRoomBookingBase):
    schema = NonBookablePeriodSchema

    def _query(self):
        return NonBookablePeriod.query.filter(NonBookablePeriod.room_id == self.room.id).order_by(
            NonBookablePeriod.start_dt, NonBookablePeriod.end_dt
        )


ENDPOINTS = [
    Endpoint(
        rule='/rooms/<int:room_id>/bookable-hours',
        name='room_bookable_hours',
        rh=RHBookableHoursList,
        schema=BookableHoursSchema,
        many=True,
        summary='List the hours a room can be booked for',
        tag='Rooms',
    ),
    Endpoint(
        rule='/rooms/<int:room_id>/nonbookable-periods',
        name='room_nonbookable_periods',
        rh=RHNonBookablePeriodList,
        schema=NonBookablePeriodSchema,
        many=True,
        summary='List the periods a room cannot be booked for',
        tag='Rooms',
    ),
]
