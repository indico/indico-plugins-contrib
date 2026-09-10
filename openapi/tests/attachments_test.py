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
    assert 'link_url' not in resp.json
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
    assert 'filename' not in resp.json['results'][0]


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


FILE_FIELDS = ('id', 'title', 'description', 'type', 'is_protected', 'download_url', 'modified_dt', 'filename',
               'content_type', 'size', 'checksum')

LINK_FIELDS = ('id', 'title', 'description', 'type', 'is_protected', 'download_url', 'modified_dt', 'link_url')

FOLDER_KEYS = {'is_default': 'default_folder'}


def flatten(folders):
    return [{**attachment, 'folder': folder}
            for folder in folders for attachment in folder['attachments']]


def test_event_attachment_matches_current_api(dummy_event, dummy_attachment, token_headers, test_client, indico_api,
                                              same_json, rename_keys):
    current = flatten(indico_api(f'/export/attachments/{dummy_event.id}.json')['results']['folders'])[0]
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/attachments/{dummy_attachment.id}',
                          headers=token_headers).json
    same_json(new, current, same=FILE_FIELDS, renamed={'folder': ('folder', rename_keys(FOLDER_KEYS))})


def test_event_attachment_list_matches_current_api(dummy_event, dummy_user, dummy_attachment, create_attachment,
                                                   token_headers, test_client, indico_api, same_json_list,
                                                   rename_keys):
    create_attachment(dummy_user, dummy_event, 'Another file', description='Another one')
    current = flatten(indico_api(f'/export/attachments/{dummy_event.id}.json')['results']['folders'])
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/attachments', headers=token_headers).json['results']
    same_json_list(new, current, same=FILE_FIELDS, renamed={'folder': ('folder', rename_keys(FOLDER_KEYS))})


def test_link_attachment_matches_current_api(dummy_event, dummy_contribution, dummy_link, token_headers, test_client,
                                             indico_api, same_json, rename_keys):
    url = f'/export/attachments/{dummy_event.id}/contribution/{dummy_contribution.id}.json'
    current = flatten(indico_api(url)['results']['folders'])[0]
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}'
                          f'/attachments/{dummy_link.id}', headers=token_headers).json
    same_json(new, current, same=LINK_FIELDS, renamed={'folder': ('folder', rename_keys(FOLDER_KEYS))})
