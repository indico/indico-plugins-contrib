# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


import pytest

from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.modules.events.tracks.models.groups import TrackGroup
from indico.modules.events.tracks.models.tracks import Track


@pytest.fixture
def dummy_track_group(db, dummy_event):
    group = TrackGroup(event=dummy_event, title='Dummy track group')
    db.session.add(group)
    db.session.flush()
    return group


@pytest.fixture
def dummy_track(db, dummy_event, dummy_track_group):
    track = Track(event=dummy_event, title='Dummy track', code='DT', track_group=dummy_track_group)
    db.session.add(track)
    db.session.flush()
    return track


def test_track_details(dummy_event, dummy_track, dummy_track_group, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/tracks/{dummy_track.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_track.id
    assert resp.json['title'] == dummy_track.title
    assert resp.json['code'] == 'DT'
    assert resp.json['track_group']['id'] == dummy_track_group.id


def test_track_list(dummy_event, dummy_track, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/tracks', headers=token_headers)
    assert resp.status_code == 200
    assert [t['id'] for t in resp.json['results']] == [dummy_track.id]


def test_track_denied_without_event_access(db, dummy_event, dummy_track, outsider_headers, test_client):
    dummy_event.protection_mode = ProtectionMode.protected
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/tracks/{dummy_track.id}', headers=outsider_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json


def test_track_list_denied_without_event_access(db, dummy_event, dummy_track, outsider_headers, test_client):
    dummy_event.protection_mode = ProtectionMode.protected
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/tracks', headers=outsider_headers)
    assert resp.status_code == 403


def test_track_of_another_event_is_not_found(dummy_track, create_event, token_headers, test_client):
    other = create_event()
    resp = test_client.get(f'/api/v1/events/{other.id}/tracks/{dummy_track.id}', headers=token_headers)
    assert resp.status_code == 404


def test_track_matches_current_api(dummy_event, dummy_track, token_headers, test_client, indico_api):
    current = indico_api(f'/event/{dummy_event.id}/program.json')
    track = next(t for t in current['tracks'] if t['id'] == dummy_track.id)
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/tracks/{dummy_track.id}', headers=token_headers).json
    assert new['id'] == track['id']
    assert new['title'] == track['title']
    assert new['code'] == track['code']
    assert new['description'] == track['description']
    assert new['position'] == track['position']
    assert new['track_group_id'] == track['track_group_id']


def test_track_group_matches_current_api(dummy_event, dummy_track, dummy_track_group, token_headers, test_client,
                                         indico_api):
    current = indico_api(f'/event/{dummy_event.id}/program.json')
    group = next(g for g in current['track_groups'] if g['id'] == dummy_track_group.id)
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/tracks/{dummy_track.id}',
                          headers=token_headers).json['track_group']
    assert new['id'] == group['id']
    assert new['title'] == group['title']


def test_track_list_matches_current_api(dummy_event, dummy_track, token_headers, test_client, indico_api):
    current = indico_api(f'/event/{dummy_event.id}/program.json')
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/tracks', headers=token_headers).json
    assert [t['id'] for t in new['results']] == [t['id'] for t in current['tracks']]
