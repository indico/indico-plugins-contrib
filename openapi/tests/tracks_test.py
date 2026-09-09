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


@pytest.fixture
def token_headers(dummy_personal_token):
    dummy_personal_token.scopes = ['read:everything']
    return {'Authorization': f'Bearer {dummy_personal_token._plaintext_token}'}


@pytest.fixture
def outsider_headers(db, dummy_personal_token, create_user):
    dummy_personal_token.user = create_user(42)
    dummy_personal_token.scopes = ['read:everything']
    db.session.flush()
    return {'Authorization': f'Bearer {dummy_personal_token._plaintext_token}'}


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
