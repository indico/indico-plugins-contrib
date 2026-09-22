# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from flask import request
from marshmallow import fields

from indico.core.marshmallow import mm
from indico.modules.categories.controllers.base import RHManageCategoryBase
from indico.modules.categories.models.event_move_request import EventMoveRequest, MoveRequestState
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, ListArgs, RHListBase
from indico_openapi.schemas import UserReferenceSchema


class MoveRequestSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """Request to move an event into a category that moderates what it holds."""

    class Meta:
        model = EventMoveRequest
        fields = ('id', 'category_id', 'event_id', 'state', 'requestor', 'requestor_comment', 'moderator',
                  'moderator_comment', 'requested_dt')
        descriptions = {
            'id': 'Numeric identifier of the request, unique across the whole instance.',
            'category_id': 'Identifier of the category the event would be moved into.',
            'event_id': 'Identifier of the event to move.',
            'state': 'Whether the request has been answered: `pending`, `accepted`, `rejected` or `withdrawn`.',
            'requestor': 'User who asked for the move.',
            'requestor_comment': 'Message the requestor wrote to support the request, empty when they wrote none.',
            'moderator': 'Category manager who answered the request, or `null` while it is unanswered.',
            'moderator_comment': 'Message the moderator wrote with their answer, empty when they wrote none.',
            'requested_dt': 'When the move was asked for.',
        }

    state = fields.Enum(MoveRequestState)
    requestor = fields.Nested(UserReferenceSchema)
    moderator = fields.Nested(UserReferenceSchema, allow_none=True)


class MoveRequestListArgs(ListArgs):
    state = fields.Enum(MoveRequestState, load_default=None,
                        metadata={'description': 'Only list the requests in this state.'})


class MoveRequestMixin:
    """Query shared by the move request endpoints.

    The category moderators are the audience of a request, so the endpoints are
    manager only like the moderation page they back. Unlike that page, which only
    has to show what is left to answer, every request is served, answered or not.
    """

    def _request_query(self):
        return (EventMoveRequest.query.with_parent(self.category)
                .order_by(EventMoveRequest.requested_dt, EventMoveRequest.id))


@json_errors
class RHMoveRequest(MoveRequestMixin, RHManageCategoryBase):
    def _process_args(self):
        RHManageCategoryBase._process_args(self)
        self.move_request = (self._request_query()
                             .filter(EventMoveRequest.id == request.view_args['request_id']).first_or_404())

    def _process_GET(self):
        return MoveRequestSchema().jsonify(self.move_request)


@json_errors
class RHMoveRequestList(MoveRequestMixin, RHListBase, RHManageCategoryBase):
    args_schema = MoveRequestListArgs
    schema = MoveRequestSchema

    def _query(self, state):
        query = self._request_query()
        if state is not None:
            query = query.filter(EventMoveRequest.state == state)
        return query

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(rule='/categories/<int:category_id>/move-requests', name='move_requests', rh=RHMoveRequestList,
             schema=MoveRequestSchema, many=True, summary='List the event move requests of a category',
             tag='Categories'),
    Endpoint(rule='/categories/<int:category_id>/move-requests/<int:request_id>', name='move_request',
             rh=RHMoveRequest, schema=MoveRequestSchema, summary='Event move request details', tag='Categories'),
]
