# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from marshmallow import fields

from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.modules.events.schemas import EventDetailsSchema
from indico.web.rh import json_errors

from indico_openapi.resources.base import Endpoint


class EventSchema(EventDetailsSchema):
    class Meta(EventDetailsSchema.Meta):
        fields = ('id', 'title', 'description', 'start_dt', 'end_dt', 'timezone', 'type', 'url',
                  'category_id', 'category_title', 'category_chain', 'location', 'room', 'room_full_name',
                  'address', 'keywords', 'organizer', 'language', 'created_dt', 'is_protected')

    type = fields.String(attribute='type_.legacy_name')
    url = fields.String(attribute='external_url')
    category_title = fields.String(attribute='category.title')
    location = fields.String(attribute='venue_name')
    room = fields.Function(lambda event: event.get_room_name(full=False))
    room_full_name = fields.String(attribute='room_name')
    organizer = fields.String(attribute='organizer_info')
    language = fields.Function(lambda event: event.default_locale or None)
    is_protected = fields.Function(lambda event: event.effective_protection_mode != ProtectionMode.public)


@json_errors
class RHEvent(RHProtectedEventBase):
    def _process_GET(self):
        return EventSchema().jsonify(self.event)


ENDPOINTS = [
    Endpoint(rule='/events/<int:event_id>', name='event', rh=RHEvent, schema=EventSchema,
             summary='Event details', tag='Events'),
]
