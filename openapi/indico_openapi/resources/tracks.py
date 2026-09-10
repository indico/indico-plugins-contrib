# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from flask import request
from marshmallow import fields

from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.modules.events.tracks.models.tracks import Track
from indico.modules.events.tracks.schemas import TrackGroupSchema
from indico.modules.events.tracks.schemas import TrackSchema as CoreTrackSchema
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase


class TrackGroupReferenceSchema(DescribedFieldsMixin, TrackGroupSchema):
    class Meta(TrackGroupSchema.Meta):
        fields = ('id', 'title')
        descriptions = {
            'id': 'Numeric identifier of the track group.',
            'title': 'Title of the track group.',
        }


class TrackSchema(DescribedFieldsMixin, CoreTrackSchema):
    class Meta(CoreTrackSchema.Meta):
        fields = (*CoreTrackSchema.Meta.fields, 'track_group', 'default_session_id')
        descriptions = {
            'id': 'Numeric identifier of the track, unique across the whole instance.',
            'title': 'Title of the track.',
            'code': 'Programme code assigned to the track.',
            'description': 'Description of the track, as Markdown.',
            'position': 'Place of the track in the programme, starting at 1.',
            'track_group_id': 'Identifier of the group holding the track, or `null` when it belongs to none.',
            'track_group': 'Group holding the track, or `null` when it belongs to none.',
            'default_session_id': 'Session new contributions of this track are assigned to by default.',
        }

    track_group = fields.Nested(TrackGroupReferenceSchema)


@json_errors
class RHTrack(RHProtectedEventBase):
    def _process_args(self):
        RHProtectedEventBase._process_args(self)
        self.track = (Track.query.with_parent(self.event)
                      .filter_by(id=request.view_args['track_id'])
                      .first_or_404())

    def _process_GET(self):
        return TrackSchema().jsonify(self.track)


@json_errors
class RHTrackList(RHListBase, RHProtectedEventBase):
    schema = TrackSchema

    def _query(self):
        return Track.query.with_parent(self.event).order_by(Track.position)

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(rule='/events/<int:event_id>/tracks', name='tracks', rh=RHTrackList, schema=TrackSchema, many=True,
             summary='List the tracks of an event', tag='Tracks'),
    Endpoint(rule='/events/<int:event_id>/tracks/<int:track_id>', name='track', rh=RHTrack, schema=TrackSchema,
             summary='Track details', tag='Tracks'),
]
