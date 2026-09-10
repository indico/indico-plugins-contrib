# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from datetime import timedelta

from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.util.date_time import now_utc


def test_session_details(dummy_event, dummy_session, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/sessions/{dummy_session.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_session.id
    assert resp.json['title'] == dummy_session.title
    assert resp.json['friendly_id'] == dummy_session.friendly_id
    assert resp.json['text_color'] == f'#{dummy_session.colors.text}'
    assert resp.json['blocks'] == []


def test_session_details_include_blocks(dummy_event, dummy_session, dummy_session_block, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/sessions/{dummy_session.id}', headers=token_headers)
    assert resp.status_code == 200
    assert [b['id'] for b in resp.json['blocks']] == [dummy_session_block.id]
    assert resp.json['blocks'][0]['title'] == dummy_session_block.title


def test_session_list(dummy_event, dummy_session, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/sessions', headers=token_headers)
    assert resp.status_code == 200
    assert [s['id'] for s in resp.json['results']] == [dummy_session.id]


def test_session_denied_without_access(db, dummy_event, dummy_session, outsider_headers, test_client):
    dummy_session.protection_mode = ProtectionMode.protected
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/sessions/{dummy_session.id}', headers=outsider_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json


def test_session_list_hides_protected_sessions(db, dummy_event, dummy_session, create_session, outsider_headers,
                                               test_client):
    dummy_session.protection_mode = ProtectionMode.protected
    public = create_session(dummy_event, 'Public session')
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/sessions', headers=outsider_headers)
    assert resp.status_code == 200
    assert [s['id'] for s in resp.json['results']] == [public.id]


def test_session_of_another_event_is_not_found(dummy_session, create_event, token_headers, test_client):
    other = create_event()
    resp = test_client.get(f'/api/v1/events/{other.id}/sessions/{dummy_session.id}', headers=token_headers)
    assert resp.status_code == 404


SESSION_FIELDS = ('title', 'friendly_id', 'code', 'description', 'type', 'address')

SESSION_KEYS = {'id': ('db_id', None), 'is_poster': ('isPoster', None), 'text_color': ('textColor', None),
                'background_color': ('color', None), 'venue_name': ('location', None),
                'room_name': ('roomFullname', None)}

BLOCK_KEYS = {'title': 'slotTitle', 'room_name': 'roomFullname', 'start_dt': 'startDate', 'end_dt': 'endDate'}


def as_blocks(as_legacy_date):
    def convert(blocks):
        return [{BLOCK_KEYS.get(key, key): as_legacy_date(value) if key.endswith('_dt') else value
                 for key, value in block.items()}
                for block in blocks]

    return convert


def as_sessions(slots):
    sessions = {}
    for slot in slots:
        sessions.setdefault(slot['session']['db_id'], {**slot['session'], 'blocks': []})['blocks'].append(slot)
    return sessions


def test_session_matches_current_api(dummy_event, dummy_session, dummy_session_block, token_headers, test_client,
                                     indico_api, as_legacy_date, same_json):
    slots = indico_api(f'/export/event/{dummy_event.id}/session/{dummy_session.id}.json')['results']
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/sessions/{dummy_session.id}', headers=token_headers).json
    same_json(new, as_sessions(slots)[dummy_session.id], same=SESSION_FIELDS,
              renamed={**SESSION_KEYS, 'blocks': ('blocks', as_blocks(as_legacy_date))})


def test_session_list_matches_current_api(dummy_event, dummy_session, dummy_session_block, create_session,
                                          create_session_block, token_headers, test_client, indico_api,
                                          as_legacy_date, same_json_list):
    other = create_session(dummy_event, 'Another session')
    create_session_block(other, 'Another block', timedelta(minutes=30), now_utc())
    ids = f'{dummy_session.id}-{other.id}'
    slots = indico_api(f'/export/event/{dummy_event.id}/session/{ids}.json')['results']
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/sessions', headers=token_headers).json['results']
    same_json_list(new, list(as_sessions(slots).values()), same=SESSION_FIELDS,
                   renamed={**SESSION_KEYS, 'blocks': ('blocks', as_blocks(as_legacy_date))})
