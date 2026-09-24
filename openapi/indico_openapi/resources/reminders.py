# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 Unconventional
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from operator import itemgetter

from flask import request, session
from marshmallow import fields, post_dump
from sqlalchemy.orm import joinedload
from werkzeug.exceptions import Forbidden

from indico.core.db.sqlalchemy.descriptions import RenderMode
from indico.core.marshmallow import mm
from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.reminders.models.reminders import EventReminder, ReminderType
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase
from indico_openapi.schemas import MemberSchema, RegistrationTagSchema


class ReminderFormSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    class Meta:
        model = RegistrationForm
        fields = ('id', 'title')
        descriptions = {
            'id': 'Numeric identifier of the registration form.',
            'title': 'Title of the form.',
        }


class ReminderSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """Email an event sends to its participants at a scheduled moment."""

    class Meta:
        model = EventReminder
        fields = (
            'id',
            'reminder_type',
            'creator',
            'created_dt',
            'scheduled_dt',
            'event_start_delta',
            'event_end_delta',
            'is_sent',
            'recipients',
            'send_to_participants',
            'forms',
            'tags',
            'all_tags',
            'send_to_speakers',
            'reply_to_address',
            'subject',
            'message',
            'render_mode',
            'include_summary',
            'include_description',
            'attach_ical',
        )
        descriptions = {
            'id': 'Numeric identifier of the reminder, unique across the whole instance.',
            'reminder_type': 'Whether the email is written from scratch (`custom`) or built by Indico around a '
            'note (`standard`).',
            'creator': 'User who created the reminder.',
            'created_dt': 'Moment the reminder was created, in UTC.',
            'scheduled_dt': 'Moment the reminder is due, in UTC. It is recomputed whenever the event is moved and '
            'the reminder is relative to its dates.',
            'event_start_delta': 'Number of seconds before the event starts, or `null` when the reminder is not '
            'scheduled relative to the start.',
            'event_end_delta': 'Number of seconds after the event ends, or `null` when the reminder is not '
            'scheduled relative to the end.',
            'is_sent': 'Whether the reminder has already been sent.',
            'recipients': 'Email addresses the reminder is sent to, on top of the participants and speakers it '
            'may also target.',
            'send_to_participants': 'Whether every registrant of the event is also a recipient.',
            'forms': 'Registration forms the participants are taken from, or an empty list when every form counts.',
            'tags': 'Registration tags a participant must carry to be a recipient, or an empty list when every '
            'participant counts.',
            'all_tags': 'Whether a participant must carry every listed tag rather than at least one of them.',
            'send_to_speakers': 'Whether every speaker and chairperson of the event is also a recipient.',
            'reply_to_address': 'Email address the reminder is sent from and answered to.',
            'subject': 'Subject of the email. Only set by a custom reminder, since a standard one is titled '
            'after the event.',
            'message': 'Body of a custom reminder, or the note a standard one includes, in the format '
            '`render_mode` gives.',
            'render_mode': 'Format the message is written in: `html` or `plain_text`.',
            'include_summary': 'Whether the email carries the schedule of the event.',
            'include_description': 'Whether the email carries the description of the event.',
            'attach_ical': 'Whether the email carries the event as an iCalendar attachment.',
        }

    reminder_type = fields.Enum(ReminderType)
    render_mode = fields.Enum(RenderMode)
    creator = fields.Nested(MemberSchema)
    recipients = fields.List(fields.String())
    forms = fields.List(fields.Nested(ReminderFormSchema))
    tags = fields.List(fields.Nested(RegistrationTagSchema))
    message = fields.String()

    @post_dump
    def _sort_filters(self, data, **kwargs):
        # both relationships are sets, so without this the order changes from one request to the next
        data['forms'].sort(key=itemgetter('id'))
        data['tags'].sort(key=itemgetter('id'))
        return data


class ReminderMixin:
    """Access checks shared by the reminder endpoints.

    A reminder is a management setting holding the recipient list and the
    message of an email, and the only interface serving it is the management
    area of the event, so these endpoints are restricted to its managers.
    """

    def _check_access(self):
        RHProtectedEventBase._check_access(self)
        if not self.event.can_manage(session.user):
            raise Forbidden

    def _reminder_query(self):
        return (
            EventReminder.query
            .with_parent(self.event)
            .options(joinedload(EventReminder.forms), joinedload(EventReminder.tags))
            .order_by(EventReminder.scheduled_dt.desc())
        )


@json_errors
class RHReminder(ReminderMixin, RHProtectedEventBase):
    def _process_args(self):
        RHProtectedEventBase._process_args(self)
        self.reminder = (
            self._reminder_query().filter(EventReminder.id == request.view_args['reminder_id']).first_or_404()
        )

    def _process_GET(self):
        return ReminderSchema().jsonify(self.reminder)


@json_errors
class RHReminderList(ReminderMixin, RHListBase, RHProtectedEventBase):
    schema = ReminderSchema

    def _query(self):
        return self._reminder_query()

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(
        rule='/events/<int:event_id>/reminders',
        name='reminders',
        rh=RHReminderList,
        schema=ReminderSchema,
        many=True,
        summary='List the reminders of an event',
        tag='Reminders',
    ),
    Endpoint(
        rule='/events/<int:event_id>/reminders/<int:reminder_id>',
        name='reminder',
        rh=RHReminder,
        schema=ReminderSchema,
        summary='Details of one reminder of an event',
        tag='Reminders',
    ),
]
