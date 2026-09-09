# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from flask import request, session
from marshmallow import fields
from werkzeug.exceptions import Forbidden

from indico.core.marshmallow import mm
from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.modules.events.notes.models.notes import EventNote
from indico.modules.events.notes.schemas import EventNoteSchema
from indico.web.flask.util import url_for
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase


class NoteRevisionSchema(DescribedFieldsMixin, EventNoteSchema):
    class Meta(EventNoteSchema.Meta):
        descriptions = {
            'id': 'Numeric identifier of the revision.',
            'created_dt': 'Moment the revision was written, in UTC.',
            'source': 'Content as typed by its author, in the format given by `render_mode`.',
            'html': 'Content rendered as HTML, with unsafe markup stripped out.',
            'render_mode': 'Format of `source`: `html` or `markdown`.',
            'note_author': 'Full name of the user who wrote the revision.',
        }


class NoteSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    class Meta:
        model = EventNote
        fields = ('id', 'link_type', 'event_id', 'session_id', 'contribution_id', 'subcontribution_id',
                  'url', 'current_revision')
        descriptions = {
            'id': 'Numeric identifier of the note, unique across the whole instance.',
            'link_type': 'Kind of object the note is written on: `event`, `session`, `contribution` or '
                         '`subcontribution`.',
            'event_id': 'Identifier of the event the note lives in.',
            'session_id': 'Identifier of the session the note is written on, or `null`.',
            'contribution_id': 'Identifier of the contribution the note is written on, or `null`.',
            'subcontribution_id': 'Identifier of the subcontribution the note is written on, or `null`.',
            'url': 'Absolute URL of the note page.',
            'current_revision': 'Latest revision of the note, which is the one being displayed.',
        }

    url = fields.Function(lambda note: url_for('event_notes.view', note, _external=True))
    current_revision = fields.Nested(NoteRevisionSchema)


@json_errors
class RHNote(RHProtectedEventBase):
    def _process_args(self):
        RHProtectedEventBase._process_args(self)
        self.note = (EventNote.query
                     .filter(EventNote.id == request.view_args['note_id'],
                             EventNote.event_id == self.event.id,
                             ~EventNote.is_deleted)
                     .first_or_404())

    def _check_access(self):
        RHProtectedEventBase._check_access(self)
        if not self.note.object.can_access(session.user):
            raise Forbidden

    def _process_GET(self):
        return NoteSchema().jsonify(self.note)


@json_errors
class RHNoteList(RHListBase, RHProtectedEventBase):
    schema = NoteSchema

    def _query(self):
        return (EventNote.query
                .filter(EventNote.event_id == self.event.id, ~EventNote.is_deleted)
                .order_by(EventNote.id))

    def _can_access(self, obj):
        return obj.object.can_access(session.user)


ENDPOINTS = [
    Endpoint(rule='/events/<int:event_id>/notes', name='notes', rh=RHNoteList, schema=NoteSchema, many=True,
             summary='List the notes of an event and of everything inside it', tag='Notes'),
    Endpoint(rule='/events/<int:event_id>/notes/<int:note_id>', name='note', rh=RHNote, schema=NoteSchema,
             summary='Note details', tag='Notes'),
]
