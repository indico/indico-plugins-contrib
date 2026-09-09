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


def test_note_details(dummy_event, dummy_note, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/notes/{dummy_note.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_note.id
    assert resp.json['link_type'] == 'event'
    assert resp.json['event_id'] == dummy_event.id
    assert resp.json['contribution_id'] is None
    assert resp.json['current_revision']['source'] == '<p>Minutes</p>'
    assert resp.json['current_revision']['render_mode'] == 'html'


def test_note_list(dummy_event, dummy_note, dummy_contribution, create_note, token_headers, test_client):
    contrib_note = create_note(dummy_contribution, '<p>Contribution minutes</p>')
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/notes', headers=token_headers)
    assert resp.status_code == 200
    assert [n['id'] for n in resp.json['results']] == [dummy_note.id, contrib_note.id]
    assert resp.json['results'][1]['contribution_id'] == dummy_contribution.id


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
