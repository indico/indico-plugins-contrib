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
    assert resp.json['blocks'][0]['duration'] == dummy_session_block.duration.total_seconds()


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


def test_session_matches_legacy_api(dummy_event, dummy_session, dummy_session_block, token_headers, test_client,
                                    legacy_api, as_legacy_date):
    legacy_block = legacy_api(f'/export/event/{dummy_event.id}/session/{dummy_session.id}.json')['results'][0]
    legacy = legacy_block['session']
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/sessions/{dummy_session.id}', headers=token_headers).json
    assert new['id'] == legacy['db_id']
    assert new['friendly_id'] == legacy['friendly_id']
    assert new['title'] == legacy['title']
    assert new['code'] == legacy['code']
    assert new['description'] == legacy['description']
    assert new['background_color'] == legacy['color']
    assert new['text_color'] == legacy['textColor']
    assert new['venue_name'] == legacy['location']
    assert new['room_name'] == legacy['roomFullname']
    assert new['address'] == legacy['address']
    assert (new['type'] or {}).get('name') == legacy['type']
    assert (new['type'] or {}).get('is_poster', False) == legacy['isPoster']
    assert len(new['blocks']) == legacy['numSlots']
    block = new['blocks'][0]
    assert block['id'] == legacy_block['id']
    assert block['title'] == legacy_block['slotTitle']
    assert block['room_name'] == legacy_block['roomFullname']
    assert as_legacy_date(block['start_dt']) == legacy_block['startDate']
    assert as_legacy_date(block['end_dt']) == legacy_block['endDate']


def test_session_list_matches_legacy_api(dummy_event, dummy_session, dummy_session_block, create_session,
                                         create_session_block, token_headers, test_client, legacy_api):
    other = create_session(dummy_event, 'Another session')
    create_session_block(other, 'Another block', timedelta(minutes=30), now_utc())
    ids = f'{dummy_session.id}-{other.id}'
    legacy = {b['session']['db_id']: b['session']
              for b in legacy_api(f'/export/event/{dummy_event.id}/session/{ids}.json')['results']}
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/sessions', headers=token_headers).json['results']
    assert {s['id'] for s in new} == set(legacy)
    for sess in new:
        assert sess['title'] == legacy[sess['id']]['title']
        assert sess['friendly_id'] == legacy[sess['id']]['friendly_id']
        assert len(sess['blocks']) == legacy[sess['id']]['numSlots']
