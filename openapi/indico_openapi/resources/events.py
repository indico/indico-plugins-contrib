# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from marshmallow import fields

from indico.core.db import db
from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.core.marshmallow import mm
from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.modules.events.models.events import Event
from indico.modules.events.schemas import EventDetailsSchema
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, ListArgs, RHListBase
from indico_openapi.schemas import ExternalReferenceSchema


class EventLabelSchema(DescribedFieldsMixin, mm.Schema):
    """The label of an event, read from the event itself since the message given with it lives there."""

    class Meta:
        descriptions = {
            'id': 'Numeric identifier of the label, shared by every event carrying it.',
            'title': 'Text of the label, such as `Cancelled` or `Postponed`.',
            'color': 'Colour the label is shown in, as a colour name such as `red`.',
            'is_event_not_happening': 'Whether the label means the event will not take place as announced.',
            'message': 'Explanation the managers of the event attached to the label, or an empty string.',
        }

    id = fields.Integer(attribute='label.id')
    title = fields.String(attribute='label.title')
    color = fields.String(attribute='label.color')
    is_event_not_happening = fields.Boolean(attribute='label.is_event_not_happening')
    message = fields.String(attribute='label_message')


class Label(fields.Nested):
    def get_value(self, obj, attr, **kwargs):
        return obj if obj.label else None


class ContactSchema(DescribedFieldsMixin, mm.Schema):
    """How to reach the organisers, read from the event itself since it is stored as settings of it."""

    class Meta:
        descriptions = {
            'title': 'Heading of the contact box on the event page, `Contact` unless the managers changed it.',
            'emails': 'Email addresses to reach the organisers at.',
            'phones': 'Phone numbers to reach the organisers at.',
        }

    title = fields.String(attribute='contact_title')
    emails = fields.List(fields.String(), attribute='contact_emails')
    phones = fields.List(fields.String(), attribute='contact_phones')


class Contact(fields.Nested):
    def get_value(self, obj, attr, **kwargs):
        return obj


class EventSchema(DescribedFieldsMixin, EventDetailsSchema):
    class Meta(EventDetailsSchema.Meta):
        fields = ('id', 'title', 'description', 'start_dt', 'end_dt', 'timezone', 'type', 'url',
                  'category_id', 'category_title', 'category_chain', 'location', 'room', 'room_full_name',
                  'address', 'keywords', 'organizer', 'language', 'created_dt', 'is_protected', 'references',
                  'label', 'contact')
        descriptions = {
            'id': 'Numeric identifier of the event, unique across the whole instance.',
            'title': 'Title of the event.',
            'description': 'Description of the event, as HTML.',
            'start_dt': 'Start of the event, in UTC.',
            'end_dt': 'End of the event, in UTC.',
            'timezone': 'Timezone the event is displayed in, as an IANA name such as `Europe/Zurich`.',
            'type': 'Kind of event: `simple_event` (lecture), `meeting` or `conference`.',
            'url': 'Absolute URL of the event page.',
            'category_id': 'Identifier of the category holding the event.',
            'category_title': 'Title of the category holding the event.',
            'category_chain': 'Titles of every category from the root down to the one holding the event.',
            'location': 'Name of the venue, such as `CERN`.',
            'room': 'Short name of the room, such as `500/1-001`.',
            'room_full_name': 'Room including its friendly name, such as `500/1-001 - Main Auditorium`.',
            'address': 'Postal address of the venue.',
            'keywords': 'Keywords assigned to the event.',
            'organizer': 'Free-text organizer of the event, as entered by its managers.',
            'language': 'Locale the event is forced to be displayed in, or `null` to follow the user.',
            'created_dt': 'Moment the event was created, in UTC.',
            'is_protected': 'Whether reading the event requires permissions beyond being logged in.',
            'references': 'Identifiers of the event in other systems, such as a DOI.',
            'label': 'Label the managers put on the event, such as `Cancelled`, or `null` when there is none.',
            'contact': 'How to reach the organisers, as shown on the event page.',
        }

    type = fields.String(attribute='type_.legacy_name')
    url = fields.String(attribute='external_url')
    category_title = fields.String(attribute='category.title')
    location = fields.String(attribute='venue_name')
    room = fields.Function(lambda event: event.get_room_name(full=False))
    room_full_name = fields.String(attribute='room_name')
    organizer = fields.String(attribute='organizer_info')
    language = fields.Function(lambda event: event.default_locale or None)
    is_protected = fields.Function(lambda event: event.effective_protection_mode != ProtectionMode.public)
    references = fields.List(fields.Nested(ExternalReferenceSchema))
    label = Label(EventLabelSchema, allow_none=True)
    contact = Contact(ContactSchema)


class EventListArgs(ListArgs):
    category_id = fields.Integer(load_default=None,
                                 metadata={'description': 'Only list events visible in this category or below it.'})
    start_after = fields.DateTime(load_default=None,
                                  metadata={'description': 'Only list events starting at or after this moment.'})
    start_before = fields.DateTime(load_default=None,
                                   metadata={'description': 'Only list events starting at or before this moment.'})


@json_errors
class RHEvent(RHProtectedEventBase):
    def _process_GET(self):
        return EventSchema().jsonify(self.event)


@json_errors
class RHEventList(RHListBase):
    args_schema = EventListArgs
    schema = EventSchema

    def _query(self, category_id, start_after, start_before):
        query = (Event.query.filter(~Event.is_deleted)
                 .options(db.joinedload('acl_entries'), db.selectinload('references'), db.selectinload('label')))
        if category_id is not None:
            query = query.filter(Event.is_visible_in(category_id))
        if start_after is not None:
            query = query.filter(Event.start_dt >= start_after)
        if start_before is not None:
            query = query.filter(Event.start_dt <= start_before)
        return query.order_by(Event.start_dt.desc(), Event.id)


ENDPOINTS = [
    Endpoint(rule='/events', name='events', rh=RHEventList, schema=EventSchema, many=True,
             summary='List the events the caller can see', tag='Events'),
    Endpoint(rule='/events/<int:event_id>', name='event', rh=RHEvent, schema=EventSchema,
             summary='Details of one event, with its dates and category', tag='Events'),
]
