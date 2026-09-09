# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


import pytest

from indico.modules.events.abstracts.models.abstracts import AbstractState
from indico.modules.events.features.util import set_feature_enabled
from indico.modules.events.tracks.models.tracks import Track
from indico.util.date_time import now_utc


@pytest.fixture(autouse=True)
def abstracts_enabled(db, dummy_event):
    set_feature_enabled(dummy_event, 'abstracts', True)
    db.session.flush()


@pytest.fixture
def dummy_track(db, dummy_event):
    track = Track(event=dummy_event, title='Dummy track', code='DT')
    db.session.add(track)
    db.session.flush()
    return track


def test_abstract_details(dummy_abstract, dummy_event, dummy_user, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/abstracts/{dummy_abstract.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_abstract.id
    assert resp.json['friendly_id'] == dummy_abstract.friendly_id
    assert resp.json['title'] == dummy_abstract.title
    assert resp.json['state'] == 'submitted'
    assert resp.json['judgment_comment'] == 'Vague but interesting!'
    assert resp.json['submitter']['id'] == dummy_user.id
    assert resp.json['judge'] is None
    assert resp.json['duplicate_of_id'] is None
    assert resp.json['merged_into_id'] is None


def test_abstract_persons(dummy_abstract, dummy_event, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/abstracts/{dummy_abstract.id}', headers=token_headers)
    assert [p['last_name'] for p in resp.json['persons']] == ['Doe', 'Silva', 'Smith']
    speaker = next(p for p in resp.json['persons'] if p['is_speaker'])
    assert speaker['email'] == 'doe@example.com'
    assert speaker['author_type'] == 'primary'
    assert speaker['title'] == 'Mr'


def test_abstract_files(dummy_abstract, dummy_abstract_file, dummy_event, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/abstracts/{dummy_abstract.id}', headers=token_headers)
    assert [f['filename'] for f in resp.json['files']] == ['dummy_abstract_file.txt']
    assert resp.json['files'][0]['content_type'] == 'text/plain'


def test_abstract_tracks(db, dummy_abstract, dummy_event, dummy_track, token_headers, test_client):
    dummy_abstract.submitted_for_tracks = {dummy_track}
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/abstracts/{dummy_abstract.id}', headers=token_headers)
    assert [t['id'] for t in resp.json['submitted_for_tracks']] == [dummy_track.id]
    assert resp.json['accepted_track'] is None


def test_abstract_list(dummy_abstract, create_abstract, dummy_event, dummy_user, token_headers, test_client):
    other = create_abstract(dummy_event, 'Another abstract', friendly_id=315, submitter=dummy_user)
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/abstracts', headers=token_headers)
    assert resp.status_code == 200
    assert [a['id'] for a in resp.json['results']] == [dummy_abstract.id, other.id]


def test_abstract_of_someone_else_is_forbidden(dummy_abstract, dummy_event, outsider_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/abstracts/{dummy_abstract.id}', headers=outsider_headers)
    assert resp.status_code == 403


def test_abstract_list_skips_unreadable_abstracts(dummy_abstract, dummy_event, outsider_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/abstracts', headers=outsider_headers)
    assert resp.status_code == 200
    assert resp.json['results'] == []


def test_abstract_manager_sees_every_abstract(db, dummy_abstract, dummy_event, outsider, outsider_headers,
                                              test_client):
    dummy_event.update_principal(outsider, permissions={'abstracts'})
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/abstracts', headers=outsider_headers)
    assert [a['id'] for a in resp.json['results']] == [dummy_abstract.id]


def test_deleted_abstract_is_not_found(db, dummy_abstract, dummy_event, token_headers, test_client):
    dummy_abstract.is_deleted = True
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/abstracts/{dummy_abstract.id}', headers=token_headers)
    assert resp.status_code == 404
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/abstracts', headers=token_headers)
    assert resp.json['results'] == []


def test_abstracts_require_the_feature(db, dummy_abstract, dummy_event, token_headers, test_client):
    set_feature_enabled(dummy_event, 'abstracts', False)
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/abstracts', headers=token_headers)
    assert resp.status_code == 404


def test_abstracts_require_login(dummy_abstract, dummy_event, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/abstracts/{dummy_abstract.id}')
    assert resp.status_code == 403


def test_judged_abstract(db, dummy_abstract, dummy_event, dummy_user, token_headers, test_client):
    dummy_abstract.state = AbstractState.accepted
    dummy_abstract.judge = dummy_user
    dummy_abstract.judgment_dt = now_utc()
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/abstracts/{dummy_abstract.id}', headers=token_headers)
    assert resp.json['state'] == 'accepted'
    assert resp.json['judge']['id'] == dummy_user.id
