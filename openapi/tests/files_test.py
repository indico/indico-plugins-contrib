# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 Unconventional
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from uuid import uuid4

import pytest


@pytest.fixture
def other_file(create_file):
    return create_file('other_file.pdf', 'application/pdf', 'dummy_context', 'Another file', id=421)


def test_file_details(dummy_file, token_headers, test_client):
    resp = test_client.get(f'/api/v1/files/{dummy_file.uuid}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['uuid'] == str(dummy_file.uuid)
    assert resp.json['filename'] == 'dummy_file.txt'
    assert resp.json['content_type'] == 'text/plain'
    assert resp.json['size'] == dummy_file.size
    assert resp.json['claimed'] is False


def test_file_requires_login(dummy_file, test_client):
    resp = test_client.get(f'/api/v1/files/{dummy_file.uuid}')
    assert resp.status_code == 403
    assert 'error' in resp.json


def test_unknown_file_is_not_found(dummy_file, token_headers, test_client):
    resp = test_client.get(f'/api/v1/files/{uuid4()}', headers=token_headers)
    assert resp.status_code == 404


def test_file_list_is_admin_only(dummy_file, token_headers, test_client):
    resp = test_client.get('/api/v1/files', headers=token_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json


def test_file_list(dummy_file, other_file, admin_headers, test_client):
    resp = test_client.get('/api/v1/files', headers=admin_headers)
    assert resp.status_code == 200
    assert [f['uuid'] for f in resp.json['results']] == [str(dummy_file.uuid), str(other_file.uuid)]


FILE_FIELDS = ('uuid', 'filename', 'content_type', 'size', 'claimed', 'created_dt')


def test_file_matches_current_api(dummy_file, token_headers, test_client, indico_api, same_json):
    current = indico_api(f'/files/{dummy_file.uuid}')
    new = test_client.get(f'/api/v1/files/{dummy_file.uuid}', headers=token_headers).json
    same_json(new, current, same=FILE_FIELDS)


def test_file_list_matches_current_api(dummy_file, other_file, admin_headers, test_client, indico_api, same_json_list):
    current = [indico_api(f'/files/{file.uuid}') for file in (dummy_file, other_file)]
    new = test_client.get('/api/v1/files', headers=admin_headers).json['results']
    same_json_list(new, current, same=FILE_FIELDS, key='uuid')
