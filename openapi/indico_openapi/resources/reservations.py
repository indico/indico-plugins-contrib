# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from operator import itemgetter

from flask import request, session
from marshmallow import fields, post_dump

from indico.modules.rb.controllers import RHRoomBookingBase
from indico.modules.rb.models.reservations import Reservation, ReservationState
from indico.modules.rb.schemas import ReservationOccurrenceSchema as CoreReservationOccurrenceSchema
from indico.modules.rb.schemas import ReservationSchema as CoreReservationSchema
from indico.util.marshmallow import NaiveDateTime
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, ListArgs, RHListBase


class ReservationOccurrenceSchema(DescribedFieldsMixin, CoreReservationOccurrenceSchema):
    class Meta(CoreReservationOccurrenceSchema.Meta):
        fields = ('start_dt', 'end_dt', 'state', 'is_valid', 'rejection_reason')
        descriptions = {
            'start_dt': 'Start of the occurrence, in the timezone of the Indico instance.',
            'end_dt': 'End of the occurrence, in the timezone of the Indico instance.',
            'state': 'Where the occurrence stands: `valid`, `cancelled` or `rejected`.',
            'is_valid': 'Whether the occurrence still takes place.',
            'rejection_reason': 'Why the occurrence was rejected, or `null` when it was not.',
        }


class ReservationSchema(DescribedFieldsMixin, CoreReservationSchema):
    class Meta(CoreReservationSchema.Meta):
        fields = ('id', 'room_id', 'location_name', 'start_dt', 'end_dt', 'created_dt', 'booking_reason',
                  'booked_for_name', 'contact_email', 'state', 'is_accepted', 'is_pending', 'is_cancelled',
                  'is_rejected', 'rejection_reason', 'is_repeating', 'repeat_frequency', 'repeat_interval',
                  'recurrence_weekdays', 'external_details_url')
        descriptions = {
            'id': 'Numeric identifier of the booking, unique across the whole instance.',
            'room_id': 'Identifier of the booked room.',
            'location_name': 'Name of the location the booked room belongs to, such as `CERN`.',
            'start_dt': 'Start of the booking, in the timezone of the Indico instance.',
            'end_dt': 'End of the booking, in the timezone of the Indico instance.',
            'created_dt': 'Moment the booking was made, in the timezone of the Indico instance.',
            'booking_reason': 'Why the room was booked, as entered by the person who booked it.',
            'booked_for_name': 'Full name of the person the room was booked for. `null` when the instance hides '
                               'booking details from users who are not involved in the booking.',
            'contact_email': 'Email address of the person the room was booked for. Hidden under the same rule as '
                             '`booked_for_name`.',
            'state': 'Where the booking stands: `pending`, `accepted`, `cancelled` or `rejected`.',
            'is_accepted': 'Whether the booking has been accepted.',
            'is_pending': 'Whether the booking is still waiting for a manager to accept it.',
            'is_cancelled': 'Whether the booking was cancelled by the person who made it.',
            'is_rejected': 'Whether the booking was rejected by a manager of the room.',
            'rejection_reason': 'Why the booking was rejected, or `null` when it was not.',
            'is_repeating': 'Whether the booking happens more than once.',
            'repeat_frequency': 'How often the booking repeats: `NEVER`, `DAY`, `WEEK` or `MONTH`.',
            'repeat_interval': 'Number of frequency units between two occurrences, such as `2` for every other week.',
            'recurrence_weekdays': 'Weekdays a weekly booking happens on, such as `["mon", "thu"]`, or `null`.',
            'external_details_url': 'Absolute URL of the booking page.',
        }

    state = fields.Enum(ReservationState)

    @post_dump(pass_original=True)
    def _hide_sensitive_data(self, data, booking, **kwargs):
        # overrides the core hook, which reads the user from the cookie session and thus
        # treats every token-authenticated request as anonymous
        if not booking.can_see_details(session.user):
            data['booked_for_name'] = None
            data['contact_email'] = None
        return data


class ReservationDetailsSchema(ReservationSchema):
    class Meta(ReservationSchema.Meta):
        fields = (*ReservationSchema.Meta.fields, 'occurrences')
        descriptions = {
            **ReservationSchema.Meta.descriptions,
            'occurrences': 'Every time the room is taken by this booking, cancelled and rejected ones included.',
        }

    occurrences = fields.Nested(ReservationOccurrenceSchema, many=True)

    @post_dump
    def _sort_occurrences(self, data, **kwargs):
        data['occurrences'].sort(key=itemgetter('start_dt'))
        return data


class ReservationListArgs(ListArgs):
    room_id = fields.Integer(load_default=None,
                             metadata={'description': 'Only list the bookings of this room.'})
    start_after = NaiveDateTime(load_default=None,
                                metadata={'description': 'Only list bookings starting at or after this moment, in '
                                                         'the timezone of the Indico instance.'})
    start_before = NaiveDateTime(load_default=None,
                                 metadata={'description': 'Only list bookings starting at or before this moment, in '
                                                          'the timezone of the Indico instance.'})


class ReservationMixin:
    """Access checks shared by the booking endpoints.

    Anybody allowed into the room booking system sees that a room is taken,
    which is what the booking calendar shows. Who took it is hidden when the
    instance is configured to keep booking details private, and the notes the
    room managers wrote are reserved for them.
    """

    def _reservation_query(self):
        return Reservation.query.order_by(Reservation.start_dt.desc(), Reservation.id)


@json_errors
class RHReservation(ReservationMixin, RHRoomBookingBase):
    def _process_args(self):
        self.reservation = (self._reservation_query()
                            .filter(Reservation.id == request.view_args['reservation_id']).first_or_404())

    def _process_GET(self):
        return ReservationDetailsSchema().jsonify(self.reservation)


@json_errors
class RHReservationList(ReservationMixin, RHListBase, RHRoomBookingBase):
    args_schema = ReservationListArgs
    schema = ReservationSchema

    def _query(self, room_id, start_after, start_before):
        query = self._reservation_query()
        if room_id is not None:
            query = query.filter(Reservation.room_id == room_id)
        if start_after is not None:
            query = query.filter(Reservation.start_dt >= start_after)
        if start_before is not None:
            query = query.filter(Reservation.start_dt <= start_before)
        return query

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(rule='/reservations', name='reservations', rh=RHReservationList, schema=ReservationSchema, many=True,
             summary='List room bookings', tag='Reservations'),
    Endpoint(rule='/reservations/<int:reservation_id>', name='reservation', rh=RHReservation,
             schema=ReservationDetailsSchema, summary='Room booking details', tag='Reservations'),
]
