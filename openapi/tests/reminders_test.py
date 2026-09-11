# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from datetime import UTC, datetime, timedelta

import pytest

from indico.modules.events.registration.models.tags import RegistrationTag
from indico.modules.events.reminders.models.reminders import EventReminder, ReminderType


@pytest.fixture
def create_reminder(db, dummy_event, dummy_user):
    def _create(scheduled_dt, **kwargs):
        kwargs.setdefault('reminder_type', ReminderType.standard)
        kwargs.setdefault('subject', 'Reminder subject')
        kwargs.setdefault('message', 'See you there')
        kwargs.setdefault('recipients', ['someone@example.test'])
        kwargs.setdefault('reply_to_address', 'organiser@example.test')
        reminder = EventReminder(event=dummy_event, creator=dummy_user, scheduled_dt=scheduled_dt, **kwargs)
        db.session.add(reminder)
        db.session.flush()
        return reminder

    return _create


@pytest.fixture
def dummy_reminder(create_reminder):
    return create_reminder(datetime(2026, 9, 1, 8, 0, tzinfo=UTC))


@pytest.mark.usefixtures('event_manager')
def test_reminder_details(dummy_event, dummy_reminder, dummy_user, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/reminders/{dummy_reminder.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_reminder.id
    assert resp.json['reminder_type'] == 'standard'
    assert resp.json['subject'] == 'Reminder subject'
    assert resp.json['message'] == 'See you there'
    assert resp.json['render_mode'] == 'html'
    assert resp.json['recipients'] == ['someone@example.test']
    assert resp.json['scheduled_dt'] == '2026-09-01T08:00:00+00:00'
    assert resp.json['event_start_delta'] is None
    assert resp.json['is_sent'] is False
    assert resp.json['creator']['id'] == dummy_user.id


@pytest.mark.usefixtures('event_manager')
def test_reminder_serves_its_offset(dummy_event, create_reminder, token_headers, test_client):
    reminder = create_reminder(datetime(2026, 9, 1, 8, 0, tzinfo=UTC), event_start_delta=timedelta(hours=3))
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/reminders/{reminder.id}', headers=token_headers)
    assert resp.json['event_start_delta'] == 10800
    assert resp.json['event_end_delta'] is None


@pytest.mark.usefixtures('event_manager')
def test_reminder_serves_its_participant_filters(db, dummy_event, dummy_regform, create_regform, create_reminder,
                                                 token_headers, test_client):
    other_form = create_regform(dummy_event, 'Another form')
    tag = RegistrationTag(event=dummy_event, title='VIP', color='blue')
    db.session.add(tag)
    db.session.flush()
    reminder = create_reminder(datetime(2026, 9, 1, 8, 0, tzinfo=UTC), send_to_participants=True,
                               all_tags=True, forms={other_form, dummy_regform}, tags={tag})
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/reminders/{reminder.id}', headers=token_headers)
    assert resp.json['send_to_participants'] is True
    assert resp.json['all_tags'] is True
    assert [form['id'] for form in resp.json['forms']] == sorted([dummy_regform.id, other_form.id])
    assert [t['title'] for t in resp.json['tags']] == ['VIP']


@pytest.mark.usefixtures('event_manager')
def test_reminder_list_is_ordered_by_schedule(dummy_event, dummy_reminder, create_reminder, token_headers,
                                              test_client):
    later = create_reminder(datetime(2026, 9, 2, 8, 0, tzinfo=UTC))
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/reminders', headers=token_headers)
    assert resp.status_code == 200
    assert [r['id'] for r in resp.json['results']] == [later.id, dummy_reminder.id]


def test_reminders_are_manager_only(dummy_event, dummy_reminder, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/reminders/{dummy_reminder.id}', headers=token_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/reminders', headers=token_headers)
    assert resp.status_code == 403


def test_reminder_of_another_event_is_not_found(db, dummy_reminder, create_event, dummy_user, token_headers,
                                                test_client):
    other = create_event()
    other.update_principal(dummy_user, full_access=True)
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{other.id}/reminders/{dummy_reminder.id}', headers=token_headers)
    assert resp.status_code == 404
