# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from flask import request, session
from marshmallow import fields
from werkzeug.exceptions import Forbidden, NotFound

from indico.core.marshmallow import mm
from indico.modules.events.contributions import contribution_settings
from indico.modules.events.contributions.util import has_contributions_with_user_as_submitter
from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.modules.events.timetable.models.breaks import Break
from indico.modules.events.timetable.models.entries import TimetableEntry, TimetableEntryType
from indico.util.i18n import _
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase
from indico_openapi.resources.contributions import SessionBlockReferenceSchema


class BreakSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    class Meta:
        model = Break
        fields = ('id', 'title', 'description', 'duration', 'text_color', 'background_color', 'venue_name',
                  'room_name', 'address', 'inherit_location')
        descriptions = {
            'id': 'Numeric identifier of the break, unique across the whole instance.',
            'title': 'Title of the break.',
            'description': 'Description of the break, as Markdown.',
            'duration': 'Length of the break, in seconds.',
            'text_color': 'Colour of the text in the timetable, as `#rrggbb`.',
            'background_color': 'Colour of the background in the timetable, as `#rrggbb`.',
            'venue_name': 'Name of the venue, such as `CERN`.',
            'room_name': 'Name of the room, such as `500/1-001`.',
            'address': 'Postal address of the venue.',
            'inherit_location': 'Whether the location is taken from the session block or event holding the break.',
        }

    text_color = fields.Function(lambda break_: f'#{break_.colors.text}')
    background_color = fields.Function(lambda break_: f'#{break_.colors.background}')


class ContributionReferenceSchema(DescribedFieldsMixin, mm.Schema):
    class Meta:
        descriptions = {
            'id': 'Numeric identifier of the contribution, unique across the whole instance.',
            'friendly_id': 'Number shown to users, unique within the event.',
            'title': 'Title of the contribution.',
            'code': 'Programme code assigned to the contribution.',
        }

    id = fields.Integer()
    friendly_id = fields.Integer()
    title = fields.String()
    code = fields.String()


class TimetableEntrySchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    class Meta:
        model = TimetableEntry
        fields = ('id', 'type', 'event_id', 'parent_id', 'start_dt', 'end_dt', 'duration', 'session_block',
                  'contribution', 'break_')
        descriptions = {
            'id': 'Numeric identifier of the timetable entry, unique across the whole instance.',
            'type': 'What the entry holds: `session_block`, `contribution` or `break`.',
            'event_id': 'Identifier of the event the entry belongs to.',
            'parent_id': 'Identifier of the session block entry holding this one, or `null` for a top-level entry.',
            'start_dt': 'Start of the entry, in UTC.',
            'end_dt': 'End of the entry, in UTC.',
            'duration': 'Length of the entry, in seconds.',
            'session_block': 'Session block scheduled by the entry, or `null` for another type.',
            'contribution': 'Contribution scheduled by the entry, or `null` for another type. Its details are '
                            'available under `/events/{event_id}/contributions/{id}`.',
            'break_': 'Break scheduled by the entry, or `null` for another type. Breaks exist only in the '
                      'timetable, so they have no endpoint of their own.',
        }

    type = fields.Function(lambda entry: entry.type.name.lower())
    start_dt = fields.DateTime()
    end_dt = fields.DateTime()
    duration = fields.TimeDelta()
    session_block = fields.Nested(SessionBlockReferenceSchema)
    contribution = fields.Nested(ContributionReferenceSchema)
    break_ = fields.Nested(BreakSchema, data_key='break')


class TimetableMixin:
    """Access checks shared by the timetable endpoints.

    An entry is visible when its object is, except for a session block, which
    also shows up when any of its contributions is readable. Contributions stay
    out of the timetable while the event has not published them.
    """

    def _contributions_published(self):
        return (contribution_settings.get(self.event, 'published') or
                self.event.can_manage(session.user, permission='contributions') or
                has_contributions_with_user_as_submitter(self.event, session.user))

    def _entry_query(self):
        return (TimetableEntry.query.with_parent(self.event)
                .order_by(TimetableEntry.start_dt, TimetableEntry.id))

    def _is_visible(self, entry):
        if entry.type == TimetableEntryType.CONTRIBUTION and not self._contributions_published():
            return False
        return entry.can_view(session.user)


@json_errors
class RHTimetableEntry(TimetableMixin, RHProtectedEventBase):
    def _process_args(self):
        RHProtectedEventBase._process_args(self)
        self.entry = self._entry_query().filter(TimetableEntry.id == request.view_args['entry_id']).first_or_404()

    def _check_access(self):
        RHProtectedEventBase._check_access(self)
        if self.entry.type == TimetableEntryType.CONTRIBUTION and not self._contributions_published():
            raise NotFound(_('The contributions of this event have not been published yet.'))
        if not self.entry.can_view(session.user):
            raise Forbidden

    def _process_GET(self):
        return TimetableEntrySchema().jsonify(self.entry)


@json_errors
class RHTimetable(TimetableMixin, RHListBase, RHProtectedEventBase):
    schema = TimetableEntrySchema

    def _query(self):
        return self._entry_query()

    def _can_access(self, obj):
        return self._is_visible(obj)


ENDPOINTS = [
    Endpoint(rule='/events/<int:event_id>/timetable', name='timetable', rh=RHTimetable, schema=TimetableEntrySchema,
             many=True, summary='List the timetable entries of an event', tag='Timetable'),
    Endpoint(rule='/events/<int:event_id>/timetable/<int:entry_id>', name='timetable_entry', rh=RHTimetableEntry,
             schema=TimetableEntrySchema, summary='Timetable entry details', tag='Timetable'),
]
