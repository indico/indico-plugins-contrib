# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from flask import request, session
from marshmallow import fields

from indico.core.db.sqlalchemy.links import LinkType
from indico.core.marshmallow import mm
from indico.modules.events.sessions.models.blocks import SessionBlock
from indico.modules.rb.controllers import RHRoomBookingBase
from indico.modules.rb.models.reservation_occurrences import (
    ReservationOccurrence,
    ReservationOccurrenceLink,
    ReservationOccurrenceState,
)
from indico.modules.rb.models.reservations import Reservation
from indico.util.marshmallow import NaiveDateTime
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase


class ReservationLinkSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """Event, contribution or session block one occurrence of a booking was made for."""

    class Meta:
        model = ReservationOccurrenceLink
        fields = (
            'id',
            'type',
            'event_id',
            'contribution_id',
            'session_block_id',
            'title',
            'occurrence_start_dt',
            'occurrence_state',
        )
        descriptions = {
            'id': 'Numeric identifier of the link, unique across the whole instance.',
            'type': 'What the occurrence was booked for: `event`, `contribution` or `session_block`.',
            'event_id': 'Identifier of the event, set whatever the type is.',
            'contribution_id': 'Identifier of the contribution, or `null` for the other types.',
            'session_block_id': 'Identifier of the session block, or `null` for the other types.',
            'title': 'Title of the linked object, or `null` when it is not readable by the requesting user.',
            'occurrence_start_dt': 'Start of the booked occurrence, in the timezone of the Indico instance.',
            'occurrence_state': 'Where the occurrence stands: `valid`, `cancelled` or `rejected`.',
        }

    type = fields.Enum(LinkType, attribute='link_type')
    title = fields.Function(lambda link: _title(link.object) if link.object.can_access(session.user) else None)
    occurrence_start_dt = NaiveDateTime(attribute='reservation_occurrence.start_dt')
    occurrence_state = fields.Enum(ReservationOccurrenceState, attribute='reservation_occurrence.state')


def _title(obj):
    # a session block is titled after its session when it has no title of its own
    return obj.full_title if isinstance(obj, SessionBlock) else obj.title


@json_errors
class RHReservationLinkList(RHListBase, RHRoomBookingBase):
    """Objects one booking was made for.

    Which event takes a room is what the booking calendar shows, so the links
    are served to anybody allowed into the room booking system. The title of an
    object the user may not read is left out, the way the booking interface
    leaves out the whole object.
    """

    schema = ReservationLinkSchema

    def _process_args(self):
        self.reservation = Reservation.get_or_404(request.view_args['reservation_id'])

    def _query(self):
        return (
            ReservationOccurrenceLink.query
            .join(ReservationOccurrence, ReservationOccurrence.link_id == ReservationOccurrenceLink.id)
            .filter(ReservationOccurrence.reservation_id == self.reservation.id)
            .order_by(ReservationOccurrence.start_dt, ReservationOccurrenceLink.id)
        )

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(
        rule='/reservations/<int:reservation_id>/links',
        name='reservation_links',
        rh=RHReservationLinkList,
        schema=ReservationLinkSchema,
        many=True,
        summary='List the objects a room booking was made for',
        tag='Reservations',
    ),
]
