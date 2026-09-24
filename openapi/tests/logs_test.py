# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from datetime import UTC, datetime

import pytest
from parity import rename_keys

from indico.modules.logs.models.entries import EventLogRealm, LogKind


@pytest.fixture
def create_log_entry(db, dummy_event, dummy_user):
    def _create(summary, realm=EventLogRealm.management, logged_dt=None, user=dummy_user, **kwargs):
        entry = dummy_event.log(realm, LogKind.change, 'Test', summary, user=user, **kwargs)
        if logged_dt is not None:
            entry.logged_dt = logged_dt
        db.session.flush()
        return entry

    return _create


@pytest.fixture
def dummy_log_entry(create_log_entry):
    return create_log_entry(
        'Event settings changed',
        logged_dt=datetime(2026, 9, 1, 8, 0, tzinfo=UTC),
        data={'Title': ['Old title', 'New title', 'text']},
    )


@pytest.fixture
def grant(db, dummy_event, dummy_user):
    def _grant(**kwargs):
        # granting a permission is logged too, and that entry would show up in every list below
        with dummy_event.logging_disabled:
            dummy_event.update_principal(dummy_user, **kwargs)
        db.session.flush()

    return _grant


@pytest.fixture
def event_manager(grant):
    grant(full_access=True)


@pytest.fixture
def registration_manager(grant):
    grant(permissions={'registration'})


@pytest.mark.usefixtures('event_manager')
def test_log_entry_details(dummy_event, dummy_log_entry, dummy_user, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/logs/{dummy_log_entry.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_log_entry.id
    assert resp.json['realm'] == 'management'
    assert resp.json['kind'] == 'change'
    assert resp.json['module'] == 'Test'
    assert resp.json['type'] == 'simple'
    assert resp.json['summary'] == 'Event settings changed'
    assert resp.json['logged_dt'] == '2026-09-01T08:00:00+00:00'
    assert resp.json['data'] == {'Title': ['Old title', 'New title', 'text']}
    assert resp.json['meta'] == {}
    assert resp.json['user']['full_name'] == dummy_user.full_name


@pytest.mark.usefixtures('event_manager')
def test_log_entry_without_user(dummy_event, create_log_entry, token_headers, test_client):
    entry = create_log_entry('Reminder sent', user=None)
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/logs/{entry.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['user'] == {'full_name': None, 'avatar_url': None}


@pytest.mark.usefixtures('event_manager')
def test_log_list_is_newest_first(dummy_event, create_log_entry, token_headers, test_client):
    older = create_log_entry('Older', logged_dt=datetime(2026, 9, 1, 8, 0, tzinfo=UTC))
    newer = create_log_entry('Newer', logged_dt=datetime(2026, 9, 2, 8, 0, tzinfo=UTC))
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/logs', headers=token_headers)
    assert resp.status_code == 200
    assert [entry['id'] for entry in resp.json['results']] == [newer.id, older.id]


@pytest.mark.usefixtures('event_manager')
def test_log_list_filters_by_realm(dummy_event, dummy_log_entry, create_log_entry, token_headers, test_client):
    entry = create_log_entry('Participant added', realm=EventLogRealm.participants)
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/logs?realm=participants', headers=token_headers)
    assert resp.status_code == 200
    assert [listed['id'] for listed in resp.json['results']] == [entry.id]


@pytest.mark.usefixtures('event_manager')
def test_log_list_filters_by_text(dummy_event, dummy_log_entry, create_log_entry, token_headers, test_client):
    entry = create_log_entry('Registration of Gudrun withdrawn')
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/logs?q=gudrun', headers=token_headers)
    assert resp.status_code == 200
    assert [listed['id'] for listed in resp.json['results']] == [entry.id]


@pytest.mark.usefixtures('event_manager')
def test_log_list_filters_by_registration(
    dummy_event, dummy_log_entry, create_log_entry, dummy_reg, token_headers, test_client
):
    entry = create_log_entry(
        'Registration modified', realm=EventLogRealm.participants, meta={'registration_id': dummy_reg.id}
    )
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/logs?registration_id={dummy_reg.id}', headers=token_headers
    )
    assert resp.status_code == 200
    assert [listed['id'] for listed in resp.json['results']] == [entry.id]


def test_logs_are_manager_only(dummy_event, dummy_log_entry, outsider_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/logs/{dummy_log_entry.id}', headers=outsider_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/logs', headers=outsider_headers)
    assert resp.status_code == 403


@pytest.mark.usefixtures('registration_manager')
def test_registration_logs_need_the_registration_filter(
    dummy_event, dummy_log_entry, create_log_entry, dummy_reg, token_headers, test_client
):
    entry = create_log_entry(
        'Registration modified', realm=EventLogRealm.participants, meta={'registration_id': dummy_reg.id}
    )
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/logs', headers=token_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/logs?registration_id={dummy_reg.id}', headers=token_headers
    )
    assert resp.status_code == 200
    assert [listed['id'] for listed in resp.json['results']] == [entry.id]
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/logs/{entry.id}', headers=token_headers)
    assert resp.status_code == 200
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/logs/{dummy_log_entry.id}', headers=token_headers)
    assert resp.status_code == 403


@pytest.mark.usefixtures('event_manager')
def test_log_entry_of_another_event_is_not_found(dummy_log_entry, create_event, token_headers, test_client):
    other = create_event()
    resp = test_client.get(f'/api/v1/events/{other.id}/logs/{dummy_log_entry.id}', headers=token_headers)
    assert resp.status_code == 404


LOG_FIELDS = ('id', 'type', 'realm', 'kind', 'module', 'meta')
ALL_REALMS = '&'.join(f'filters={realm.name}' for realm in EventLogRealm)


def log_keys(tzinfo):
    def _in_event_tz(value):
        return datetime.fromisoformat(value).astimezone(tzinfo).isoformat()

    return {
        'summary': ('description', None),
        'data': ('payload', None),
        'logged_dt': ('time', _in_event_tz),
        'user': ('user', rename_keys({'full_name': 'fullName', 'avatar_url': 'avatarURL'})),
    }


@pytest.fixture
def log_mapping(dummy_event):
    return log_keys(dummy_event.tzinfo)


@pytest.fixture
def current_entries(dummy_event, indico_api):
    def _fetch():
        return indico_api(f'/event/{dummy_event.id}/manage/logs/api/logs?{ALL_REALMS}')['entries']

    return _fetch


@pytest.mark.usefixtures('event_manager')
def test_log_entry_matches_current_api(
    dummy_event, dummy_log_entry, token_headers, test_client, current_entries, same_json, log_mapping
):
    current = next(entry for entry in current_entries() if entry['id'] == dummy_log_entry.id)
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/logs/{dummy_log_entry.id}', headers=token_headers).json
    same_json(new, current, same=LOG_FIELDS, renamed=log_mapping)


@pytest.mark.usefixtures('event_manager')
def test_log_list_matches_current_api(
    dummy_event,
    dummy_log_entry,
    create_log_entry,
    token_headers,
    test_client,
    current_entries,
    same_json_list,
    log_mapping,
):
    create_log_entry('Reminder sent', realm=EventLogRealm.participants, user=None)
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/logs', headers=token_headers).json['results']
    same_json_list(new, current_entries(), same=LOG_FIELDS, renamed=log_mapping)
