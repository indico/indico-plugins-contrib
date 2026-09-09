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


def test_event_attachment_matches_legacy_api(dummy_event, dummy_attachment, token_headers, test_client, legacy_api):
    legacy_folder = legacy_api(f'/export/attachments/{dummy_event.id}.json')['results']['folders'][0]
    legacy = legacy_folder['attachments'][0]
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/attachments/{dummy_attachment.id}',
                          headers=token_headers).json
    assert new['id'] == legacy['id']
    assert new['title'] == legacy['title']
    assert new['description'] == legacy['description']
    assert new['type'] == legacy['type']
    assert new['is_protected'] == legacy['is_protected']
    assert new['download_url'] == legacy['download_url']
    assert new['modified_dt'] == legacy['modified_dt']
    assert new['filename'] == legacy['filename']
    assert new['content_type'] == legacy['content_type']
    assert new['size'] == legacy['size']
    assert new['checksum'] == legacy['checksum']
    assert new['folder']['id'] == legacy_folder['id']
    assert new['folder']['title'] == legacy_folder['title']
    assert new['folder']['description'] == legacy_folder['description']
    assert new['folder']['is_default'] == legacy_folder['default_folder']
    assert new['folder']['is_protected'] == legacy_folder['is_protected']


def test_event_attachment_list_matches_legacy_api(dummy_event, dummy_attachment, token_headers, test_client,
                                                  legacy_api):
    legacy_folders = legacy_api(f'/export/attachments/{dummy_event.id}.json')['results']['folders']
    legacy = {a['id']: a for folder in legacy_folders for a in folder['attachments']}
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/attachments', headers=token_headers).json['results']
    assert {a['id'] for a in new} == set(legacy)
    for attachment in new:
        assert attachment['title'] == legacy[attachment['id']]['title']
        assert attachment['download_url'] == legacy[attachment['id']]['download_url']
        assert attachment['modified_dt'] == legacy[attachment['id']]['modified_dt']


def test_contribution_attachment_matches_legacy_api(dummy_event, dummy_contribution, dummy_link, token_headers,
                                                    test_client, legacy_api):
    legacy_folder = (legacy_api(f'/export/attachments/{dummy_event.id}/contribution/{dummy_contribution.id}.json')
                     ['results']['folders'][0])
    legacy = legacy_folder['attachments'][0]
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}'
                          f'/attachments/{dummy_link.id}', headers=token_headers).json
    assert new['id'] == legacy['id']
    assert new['title'] == legacy['title']
    assert new['type'] == legacy['type']
    assert new['link_url'] == legacy['link_url']
    assert new['download_url'] == legacy['download_url']
    assert new['folder']['title'] == legacy_folder['title']
