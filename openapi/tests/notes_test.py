# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


import pytest

from indico.core.db.sqlalchemy.descriptions import RenderMode
from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.modules.events.notes.models.notes import EventNote


@pytest.fixture
def create_note(db, dummy_user):
    def _create_note(obj, source):
        note = EventNote.get_or_create(obj)
        note.create_revision(RenderMode.html, source, dummy_user)
        db.session.flush()
        return note

    return _create_note


@pytest.fixture
def dummy_note(create_note, dummy_event):
    return create_note(dummy_event, '<p>Minutes</p>')


def test_note_details(dummy_event, dummy_note, dummy_user, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/notes/{dummy_note.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['html'] == '<p>Minutes</p>'
    assert resp.json['author_id'] == dummy_user.id
    assert resp.json['url'].endswith(f'/event/{dummy_event.id}/note/')


def test_note_list(dummy_event, dummy_note, dummy_contribution, create_note, token_headers, test_client):
    create_note(dummy_contribution, '<p>Contribution minutes</p>')
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/notes', headers=token_headers)
    assert resp.status_code == 200
    assert [n['html'] for n in resp.json['results']] == ['<p>Minutes</p>', '<p>Contribution minutes</p>']
    assert f'/contributions/{dummy_contribution.id}/' in resp.json['results'][1]['url']


def test_note_of_protected_contribution_is_not_listed(db, dummy_event, dummy_contribution, create_note,
                                                      outsider_headers, test_client):
    create_note(dummy_contribution, '<p>Secret</p>')
    dummy_contribution.protection_mode = ProtectionMode.protected
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/notes', headers=outsider_headers)
    assert resp.status_code == 200
    assert resp.json['results'] == []


def test_note_of_protected_contribution_denied(db, dummy_event, dummy_contribution, create_note, outsider_headers,
                                               test_client):
    note = create_note(dummy_contribution, '<p>Secret</p>')
    dummy_contribution.protection_mode = ProtectionMode.protected
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/notes/{note.id}', headers=outsider_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json


def test_note_of_another_event_is_not_found(dummy_note, create_event, token_headers, test_client):
    other = create_event()
    resp = test_client.get(f'/api/v1/events/{other.id}/notes/{dummy_note.id}', headers=token_headers)
    assert resp.status_code == 404


NOTE_FIELDS = ('url', 'html', 'modified_dt')


def test_note_matches_current_api(dummy_event, dummy_note, token_headers, test_client, indico_api, same_json):
    current = indico_api(f'/export/note/{dummy_event.id}.json')['results']
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/notes/{dummy_note.id}', headers=token_headers).json
    same_json(new, current, same=NOTE_FIELDS, renamed={'author_id': ('user', None)})


def test_note_list_matches_current_api(dummy_event, dummy_note, dummy_contribution, create_note, token_headers,
                                       test_client, indico_api, same_json_list):
    create_note(dummy_contribution, '<p>Contribution minutes</p>')
    contrib_url = f'/export/note/{dummy_event.id}/contribution/{dummy_contribution.id}.json'
    current = [indico_api(f'/export/note/{dummy_event.id}.json')['results'], indico_api(contrib_url)['results']]
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/notes', headers=token_headers).json['results']
    same_json_list(new, current, same=NOTE_FIELDS, renamed={'author_id': ('user', None)}, key='url')
