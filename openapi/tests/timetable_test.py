# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from datetime import datetime, timedelta

import pytest
import pytz

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


def as_timetable_date(value, tz_name):
    local = datetime.fromisoformat(value).astimezone(pytz.timezone(tz_name))
    return {'date': local.strftime('%Y-%m-%d'), 'time': local.strftime('%H:%M:%S'), 'tz': tz_name}


def test_timetable_list(dummy_event, dummy_break, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/timetable', headers=token_headers)
    assert resp.status_code == 200
    entry = resp.json['results'][0]
    assert entry['id'] == dummy_break.timetable_entry.id
    assert entry['type'] == 'break'
    assert entry['parent_id'] is None
    assert entry['duration'] == dummy_break.duration.total_seconds()
    assert entry['break']['title'] == 'Coffee'
    assert entry['break']['background_color'] == f'#{dummy_break.colors.background}'
    assert entry['contribution'] is None
    assert entry['session_block'] is None


def test_timetable_entry_details(dummy_event, dummy_contribution, create_timetable_entry, token_headers, test_client):
    entry = create_timetable_entry(dummy_event, dummy_contribution, now_utc())
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/timetable/{entry.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == entry.id
    assert resp.json['type'] == 'contribution'
    assert resp.json['contribution']['id'] == dummy_contribution.id
    assert resp.json['contribution']['title'] == dummy_contribution.title


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
    assert entries[block_entry.id]['session_block']['id'] == dummy_session_block.id
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


def test_timetable_matches_indico_api(dummy_event, dummy_break, token_headers, test_client, indico_api):
    days = indico_api(f'/export/timetable/{dummy_event.id}.json')['results'][str(dummy_event.id)]
    legacy = next(iter(next(iter(days.values())).values()))
    entry = dummy_break.timetable_entry
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/timetable/{entry.id}', headers=token_headers).json
    assert f'b{new["id"]}' == legacy['id']
    assert new['type'] == 'break'
    assert new['event_id'] == legacy['conferenceId']
    assert new['duration'] == legacy['duration'] * 60
    assert as_timetable_date(new['start_dt'], legacy['startDate']['tz']) == legacy['startDate']
    assert as_timetable_date(new['end_dt'], legacy['endDate']['tz']) == legacy['endDate']
    assert new['break']['title'] == legacy['title']
    assert new['break']['description'] == legacy['description']
    assert new['break']['background_color'] == legacy['color']
    assert new['break']['text_color'] == legacy['textColor']
    assert new['break']['venue_name'] == legacy['location']
    assert new['break']['room_name'] == legacy['room']
    assert new['break']['inherit_location'] == legacy['inheritLoc']


def test_timetable_list_matches_indico_api(dummy_event, dummy_break, dummy_session_block, dummy_contribution,
                                           create_timetable_entry, token_headers, test_client, indico_api):
    create_timetable_entry(dummy_event, dummy_contribution, now_utc())
    days = indico_api(f'/export/timetable/{dummy_event.id}.json')['results'][str(dummy_event.id)]
    legacy = {}
    for entries in days.values():
        legacy.update(entries)
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/timetable', headers=token_headers).json['results']
    prefixes = {'session_block': 's', 'contribution': 'c', 'break': 'b'}
    assert {f'{prefixes[e["type"]]}{e["id"]}' for e in new} == set(legacy)
    for entry in new:
        key = f'{prefixes[entry["type"]]}{entry["id"]}'
        assert entry['duration'] == legacy[key]['duration'] * 60
        assert as_timetable_date(entry['start_dt'], legacy[key]['startDate']['tz']) == legacy[key]['startDate']
