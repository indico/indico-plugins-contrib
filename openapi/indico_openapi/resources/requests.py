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
from indico.modules.events.management.controllers import RHManageEventBase
from indico.modules.events.requests import get_request_definitions
from indico.modules.events.requests.models.requests import Request, RequestState
from indico.modules.events.requests.util import is_request_manager
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, ListArgs, RHListBase
from indico_openapi.schemas import MemberSchema


class ServiceRequestSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """Service an event asked the instance to provide, such as a webcast.

    Core has no schema for requests because each request type renders its own
    form, so this one is defined here.
    """

    class Meta:
        model = Request
        fields = ('id', 'event_id', 'type', 'state', 'data', 'comment', 'created_by', 'created_dt', 'processed_by',
                  'processed_dt')
        descriptions = {
            'id': 'Numeric identifier of the request, unique across the whole instance.',
            'event_id': 'Identifier of the event the service was asked for.',
            'type': 'Name of the request type, such as `webcast`. Request types are provided by plugins.',
            'state': 'Where the request stands: `pending`, `accepted`, `rejected` or `withdrawn`.',
            'data': 'Values the event manager filled in when asking for the service. The fields are defined by '
                    'the plugin providing the request type, so they differ from one type to another.',
            'comment': 'Explanation the service gave when accepting or rejecting the request, or `null` when '
                       'there is none.',
            'created_by': 'User who asked for the service.',
            'created_dt': 'Moment the request was sent, in UTC.',
            'processed_by': 'User who accepted or rejected the request, or `null` while it is pending.',
            'processed_dt': 'Moment the request was accepted or rejected, in UTC, or `null` while it is pending.',
        }

    state = fields.Enum(RequestState)
    data = fields.Raw()
    created_by = fields.Nested(MemberSchema, attribute='created_by_user')
    processed_by = fields.Nested(MemberSchema, attribute='processed_by_user')


class ServiceRequestListArgs(ListArgs):
    request_type = fields.String(data_key='type', load_default=None,
                                 metadata={'description': 'Only list the requests of this type, such as `webcast`.'})
    state = fields.Enum(RequestState, load_default=None,
                        metadata={'description': 'Only list the requests in this state.'})


class ServiceRequestMixin:
    """Access checks shared by the service request endpoints.

    A request is served to the managers of the event and to the people running
    the service that was asked for, which is the audience the request pages
    serve as well: managing a request type is enough to reach the requests of
    that type in any event, and of no other type.

    A request whose type no longer has a definition loaded is served to nobody,
    since the plugin defining what it holds is the one that is gone.
    """

    def _process_args(self):
        RHManageEventBase._process_args(self)
        self.can_manage_event = self.event.can_manage(session.user)

    def _check_access(self):
        if not self.can_manage_event and not is_request_manager(session.user):
            RHManageEventBase._check_access(self)

    def _can_see(self, req):
        return self.can_manage_event or req.definition.can_be_managed(session.user)

    def _request_query(self):
        return (Request.query.with_parent(self.event)
                .filter(Request.type.in_(get_request_definitions()))
                .order_by(Request.created_dt.desc(), Request.id.desc()))


@json_errors
class RHServiceRequest(ServiceRequestMixin, RHManageEventBase):
    def _process_args(self):
        ServiceRequestMixin._process_args(self)
        self.request = (self._request_query()
                        .filter(Request.id == request.view_args['request_id']).first_or_404())

    def _check_access(self):
        ServiceRequestMixin._check_access(self)
        if not self._can_see(self.request):
            raise Forbidden

    def _process_GET(self):
        return ServiceRequestSchema().jsonify(self.request)


@json_errors
class RHServiceRequestList(ServiceRequestMixin, RHListBase, RHManageEventBase):
    args_schema = ServiceRequestListArgs
    schema = ServiceRequestSchema

    def _query(self, request_type, state):
        query = self._request_query()
        if request_type is not None:
            query = query.filter(Request.type == request_type)
        if state is not None:
            query = query.filter(Request.state == state)
        return query

    def _can_access(self, obj):
        return self._can_see(obj)


ENDPOINTS = [
    Endpoint(rule='/events/<int:event_id>/requests', name='requests', rh=RHServiceRequestList,
             schema=ServiceRequestSchema, many=True, summary='List the services an event asked for',
             tag='Service requests'),
    Endpoint(rule='/events/<int:event_id>/requests/<int:request_id>', name='request', rh=RHServiceRequest,
             schema=ServiceRequestSchema, summary='Details of one service an event asked for', tag='Service requests'),
]
