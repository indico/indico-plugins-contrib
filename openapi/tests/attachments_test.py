# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from hashlib import md5

import pytest

from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.modules.attachments.models.attachments import Attachment, AttachmentType
from indico.modules.attachments.models.folders import AttachmentFolder


@pytest.fixture
def dummy_link(db, dummy_user, dummy_contribution):
    folder = AttachmentFolder(object=dummy_contribution, title='Links', description='')
    link = Attachment(folder=folder, user=dummy_user, type=AttachmentType.link, title='Indico',
                      link_url='https://getindico.io')
    db.session.flush()
    return link


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


def test_event_attachment_details(dummy_event, dummy_attachment, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/attachments/{dummy_attachment.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_attachment.id
    assert resp.json['type'] == 'file'
    assert resp.json['title'] == 'dummy_attachment'
    assert resp.json['filename'] == 'dummy_file.txt'
    assert resp.json['content_type'] == 'text/plain'
    assert resp.json['size'] == len(b'hello world')
    assert resp.json['checksum'] == md5(b'hello world').hexdigest()
    assert resp.json['link_url'] is None
    assert resp.json['folder']['title'] == 'dummy_folder'


def test_event_attachment_list(dummy_event, dummy_attachment, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/attachments', headers=token_headers)
    assert resp.status_code == 200
    assert [a['id'] for a in resp.json['results']] == [dummy_attachment.id]


def test_contribution_attachment_list(dummy_event, dummy_contribution, dummy_link, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}/attachments',
                           headers=token_headers)
    assert resp.status_code == 200
    assert [a['id'] for a in resp.json['results']] == [dummy_link.id]
    assert resp.json['results'][0]['type'] == 'link'
    assert resp.json['results'][0]['link_url'] == 'https://getindico.io'
    assert resp.json['results'][0]['filename'] is None


def test_event_attachment_not_listed_for_contribution(dummy_event, dummy_contribution, dummy_attachment,
                                                      token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}/attachments',
                           headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['results'] == []


def test_attachment_denied_without_event_access(db, dummy_event, dummy_attachment, outsider_headers, test_client):
    dummy_event.protection_mode = ProtectionMode.protected
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/attachments/{dummy_attachment.id}',
                           headers=outsider_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json


def test_protected_attachment_is_not_listed(db, dummy_event, dummy_attachment, outsider_headers, test_client):
    dummy_attachment.protection_mode = ProtectionMode.protected
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/attachments', headers=outsider_headers)
    assert resp.status_code == 200
    assert resp.json['results'] == []


def test_protected_attachment_details_denied(db, dummy_event, dummy_attachment, outsider_headers, test_client):
    dummy_attachment.protection_mode = ProtectionMode.protected
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/attachments/{dummy_attachment.id}',
                           headers=outsider_headers)
    assert resp.status_code == 403
