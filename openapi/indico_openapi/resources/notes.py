# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from flask import request, session
from marshmallow import fields
from werkzeug.exceptions import Forbidden

from indico.core.db.sqlalchemy.descriptions import RenderMode
from indico.core.marshmallow import mm
from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.modules.events.notes.models.notes import EventNote, EventNoteRevision
from indico.web.flask.util import url_for
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase


class NoteSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    class Meta:
        model = EventNote
        fields = ('url', 'html', 'modified_dt', 'author_id')
        descriptions = {
            'url': 'Absolute URL of the note page.',
            'html': 'Content of the note, as HTML.',
            'modified_dt': 'Moment the note was last modified, in UTC.',
            'author_id': 'Identifier of the user who wrote the content being displayed.',
        }

    url = fields.Function(lambda note: url_for('event_notes.view', note, _external=True))
    html = fields.String()
    modified_dt = fields.DateTime(attribute='current_revision.created_dt')
    author_id = fields.Integer(attribute='current_revision.user_id')


class NoteRevisionSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """One version of the content of a note."""

    class Meta:
        model = EventNoteRevision
        fields = ('id', 'created_dt', 'user_id', 'render_mode', 'source', 'html')
        descriptions = {
            'id': 'Numeric identifier of the revision, unique across the whole instance.',
            'created_dt': 'Moment the revision was written, in UTC.',
            'user_id': 'Identifier of the user who wrote it.',
            'render_mode': 'How `source` is written: `html` or `markdown`.',
            'source': 'Content of the revision as the author wrote it.',
            'html': 'Content of the revision rendered as HTML.',
        }

    render_mode = fields.Enum(RenderMode)


class NoteMixin:
    """Lookup shared by the endpoints of a single note."""

    def _find_note(self):
        return (EventNote.query
                .filter(EventNote.id == request.view_args['note_id'],
                        EventNote.event_id == self.event.id,
                        ~EventNote.is_deleted)
                .first_or_404())


class NoteRevisionMixin(NoteMixin):
    """Lookup and access checks shared by the note revision endpoints.

    A note is served to whoever can read the object it hangs off, while its
    older revisions hold content that object no longer shows, so they are
    served to the people managing it and to nobody else.
    """

    def _process_args(self):
        RHProtectedEventBase._process_args(self)
        self.note = self._find_note()

    def _check_access(self):
        RHProtectedEventBase._check_access(self)
        if not self.note.object.can_manage(session.user):
            raise Forbidden

    def _revision_query(self):
        return (EventNoteRevision.query
                .filter(EventNoteRevision.note_id == self.note.id)
                .order_by(EventNoteRevision.created_dt.desc(), EventNoteRevision.id.desc()))


@json_errors
class RHNote(NoteMixin, RHProtectedEventBase):
    def _process_args(self):
        RHProtectedEventBase._process_args(self)
        self.note = self._find_note()

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


@json_errors
class RHNoteRevision(NoteRevisionMixin, RHProtectedEventBase):
    def _process_args(self):
        NoteRevisionMixin._process_args(self)
        self.revision = (self._revision_query()
                         .filter(EventNoteRevision.id == request.view_args['revision_id']).first_or_404())

    def _process_GET(self):
        return NoteRevisionSchema().jsonify(self.revision)


@json_errors
class RHNoteRevisionList(NoteRevisionMixin, RHListBase, RHProtectedEventBase):
    schema = NoteRevisionSchema

    def _query(self):
        return self._revision_query()

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(rule='/events/<int:event_id>/notes', name='notes', rh=RHNoteList, schema=NoteSchema, many=True,
             summary='List the notes of an event and of everything inside it', tag='Notes'),
    Endpoint(rule='/events/<int:event_id>/notes/<int:note_id>', name='note', rh=RHNote, schema=NoteSchema,
             summary='Details of one note of an event', tag='Notes'),
    Endpoint(rule='/events/<int:event_id>/notes/<int:note_id>/revisions', name='note_revisions',
             rh=RHNoteRevisionList, schema=NoteRevisionSchema, many=True,
             summary='List the successive versions of a note', tag='Notes'),
    Endpoint(rule='/events/<int:event_id>/notes/<int:note_id>/revisions/<int:revision_id>', name='note_revision',
             rh=RHNoteRevision, schema=NoteRevisionSchema, summary='Details of one version of a note', tag='Notes'),
]
