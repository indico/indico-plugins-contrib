# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from flask import request, session
from werkzeug.exceptions import Forbidden

from indico.core.marshmallow import mm
from indico.modules.rb.controllers import RHRoomBookingBase
from indico.modules.rb.models.reservation_edit_logs import ReservationEditLog
from indico.modules.rb.models.reservations import Reservation
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase


class ReservationEditLogSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """One entry of the history of a booking."""

    class Meta:
        model = ReservationEditLog
        fields = ('id', 'reservation_id', 'timestamp', 'user_name', 'info')
        descriptions = {
            'id': 'Numeric identifier of the entry, unique across the whole instance.',
            'reservation_id': 'Identifier of the booking the entry belongs to.',
            'timestamp': 'When the change was made.',
            'user_name': 'Full name of whoever made the change, as it was when the entry was written.',
            'info': 'Lines describing the change, such as `Booking accepted`.',
        }


@json_errors
class RHReservationEditLogList(RHListBase, RHRoomBookingBase):
    """History of one booking.

    The history names the people involved in the booking, so it follows the
    same rule as the booking details: it is kept from users who are not part of
    the booking when the instance hides those details.
    """

    schema = ReservationEditLogSchema

    def _process_args(self):
        self.reservation = Reservation.get_or_404(request.view_args['reservation_id'])

    def _check_access(self):
        RHRoomBookingBase._check_access(self)
        if not self.reservation.can_see_details(session.user):
            raise Forbidden

    def _query(self):
        return (ReservationEditLog.query
                .filter(ReservationEditLog.reservation_id == self.reservation.id)
                .order_by(ReservationEditLog.timestamp, ReservationEditLog.id))

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(rule='/reservations/<int:reservation_id>/edit-logs', name='reservation_edit_logs',
             rh=RHReservationEditLogList, schema=ReservationEditLogSchema, many=True,
             summary='List the history of a room booking', tag='Reservations'),
]
