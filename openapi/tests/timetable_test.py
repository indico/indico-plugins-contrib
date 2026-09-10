# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from datetime import datetime, timedelta

import pytest

from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.modules.events.contributions import contribution_settings
from indico.modules.events.timetable.models.breaks import Break
from indico.util.date_time import now_utc


@pytest.fixture
def dummy_break(db, dummy_event, create_timetable_entry):
    break_ = Break(title='Coffee', duration=timedelta(minutes=15))
    db.session.add(break_)
    db.session.flush()
    create_timetable_entry(dummy_event, break_, now_utc())
    return break_


def test_timetable_list(dummy_event, dummy_break, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/timetable', headers=token_headers)
    assert resp.status_code == 200
    entry = resp.json['results'][0]
    assert entry['id'] == dummy_break.timetable_entry.id
    assert entry['type'] == 'break'
    assert entry['parent_id'] is None
    assert entry['duration'] == dummy_break.duration.total_seconds()
    assert entry['title'] == 'Coffee'
    assert entry['break']['background_color'] == f'#{dummy_break.colors.background}'
    assert entry['contribution_id'] is None
    assert entry['session_block_id'] is None


def test_timetable_entry_details(dummy_event, dummy_contribution, create_timetable_entry, token_headers, test_client):
    entry = create_timetable_entry(dummy_event, dummy_contribution, now_utc())
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/timetable/{entry.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == entry.id
    assert resp.json['type'] == 'contribution'
    assert resp.json['contribution_id'] == dummy_contribution.id
    assert resp.json['title'] == dummy_contribution.title


def test_timetable_lists_nested_entries(dummy_event, dummy_session_block, dummy_contribution,
                                        create_timetable_entry, token_headers, test_client):
    block_entry = dummy_session_block.timetable_entry
    child = create_timetable_entry(dummy_event, dummy_contribution, now_utc(), parent=block_entry)
    dummy_contribution.session = dummy_session_block.session
    dummy_contribution.session_block = dummy_session_block
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/timetable', headers=token_headers)
    assert resp.status_code == 200
    entries = {e['id']: e for e in resp.json['results']}
    assert set(entries) == {block_entry.id, child.id}
    assert entries[block_entry.id]['parent_id'] is None
    assert entries[block_entry.id]['session_block_id'] == dummy_session_block.id
    assert entries[child.id]['parent_id'] == block_entry.id


def test_timetable_hides_protected_entries(db, dummy_event, dummy_session, dummy_session_block, dummy_break,
                                           outsider_headers, test_client):
    dummy_session.protection_mode = ProtectionMode.protected
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/timetable', headers=outsider_headers)
    assert resp.status_code == 200
    assert [e['id'] for e in resp.json['results']] == [dummy_break.timetable_entry.id]


def test_timetable_entry_denied_without_access(db, dummy_event, dummy_session, dummy_session_block,
                                               outsider_headers, test_client):
    dummy_session.protection_mode = ProtectionMode.protected
    db.session.flush()
    entry = dummy_session_block.timetable_entry
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/timetable/{entry.id}', headers=outsider_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json


def test_timetable_hides_unpublished_contributions(db, dummy_event, dummy_contribution, dummy_break,
                                                   create_timetable_entry, outsider_headers, test_client):
    contrib_entry = create_timetable_entry(dummy_event, dummy_contribution, now_utc())
    contribution_settings.set(dummy_event, 'published', False)
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/timetable', headers=outsider_headers)
    assert resp.status_code == 200
    assert [e['id'] for e in resp.json['results']] == [dummy_break.timetable_entry.id]
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/timetable/{contrib_entry.id}', headers=outsider_headers)
    assert resp.status_code == 404


def test_timetable_entry_of_another_event_is_not_found(dummy_break, create_event, token_headers, test_client):
    other = create_event()
    entry_id = dummy_break.timetable_entry.id
    resp = test_client.get(f'/api/v1/events/{other.id}/timetable/{entry_id}', headers=token_headers)
    assert resp.status_code == 404


ENTRY_TYPES = {'Session': 'session_block', 'Contribution': 'contribution', 'Break': 'break'}

BREAK_KEYS = {'venue_name': 'location', 'room_name': 'room', 'inherit_location': 'inheritLoc',
              'text_color': 'textColor', 'background_color': 'color'}


def flatten(days):
    entries = {}
    for day in days.values():
        for key, entry in day.items():
            entries[key] = entry
            entries.update(entry.get('entries') or {})
    return entries


def as_type(current):
    return ENTRY_TYPES[current['entryType']]


def as_parent_id(current):
    return current['sessionSlotEntryId'] if current['entryType'] != 'Session' else None


def as_session_block_id(current):
    return current['sessionSlotId'] if current['entryType'] == 'Session' else None


def as_contribution_id(current):
    return current['contributionId'] if current['entryType'] == 'Contribution' else None


def as_break(current):
    return {BREAK_KEYS.get(key, key): value for key, value in current.items()} if current else None


def as_minutes(seconds):
    return seconds / 60


DERIVED = {'type': as_type, 'parent_id': as_parent_id, 'session_block_id': as_session_block_id,
           'contribution_id': as_contribution_id}


def entry_keys(as_timetable_date):
    return {'event_id': ('conferenceId', None), 'duration': ('duration', as_minutes),
            'start_dt': ('startDate', as_timetable_date), 'end_dt': ('endDate', as_timetable_date),
            'break': ('break', as_break), 'id': ('entry_id', None)}


@pytest.fixture
def as_timetable_date(dummy_event):
    tz = dummy_event.display_tzinfo

    def _convert(value):
        local = datetime.fromisoformat(value).astimezone(tz)
        return {'date': local.strftime('%Y-%m-%d'), 'time': local.strftime('%H:%M:%S'), 'tz': str(tz)}

    return _convert


def as_current(entry):
    return {**entry, 'entry_id': int(entry['id'][1:]),
            'break': entry if entry['entryType'] == 'Break' else None}


def test_timetable_entry_matches_current_api(dummy_event, dummy_break, token_headers, test_client, indico_api,
                                             as_timetable_date, same_json):
    days = indico_api(f'/export/timetable/{dummy_event.id}.json')['results'][str(dummy_event.id)]
    entry = dummy_break.timetable_entry
    current = as_current(flatten(days)[f'b{entry.id}'])
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/timetable/{entry.id}', headers=token_headers).json
    same_json(new, current, same=('title',), renamed=entry_keys(as_timetable_date), derived=DERIVED)


def test_timetable_matches_current_api(dummy_event, dummy_break, dummy_session_block, dummy_contribution,
                                       create_timetable_entry, token_headers, test_client, indico_api,
                                       as_timetable_date, same_json_list):
    create_timetable_entry(dummy_event, dummy_contribution, now_utc(), parent=dummy_session_block.timetable_entry)
    days = indico_api(f'/export/timetable/{dummy_event.id}.json')['results'][str(dummy_event.id)]
    current = [as_current(entry) for entry in flatten(days).values()]
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/timetable', headers=token_headers).json['results']
    same_json_list(new, current, same=('title',), renamed=entry_keys(as_timetable_date), derived=DERIVED)
