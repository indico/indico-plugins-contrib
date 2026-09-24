# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 Unconventional
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest

from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.modules.events.features.util import set_feature_enabled
from indico.modules.events.papers.file_types import PaperFileType


@pytest.fixture(autouse=True)
def papers_enabled(db, dummy_event):
    set_feature_enabled(dummy_event, 'papers', True)
    db.session.flush()


@pytest.fixture
def create_paper_file_type(db, dummy_event):
    def _create(name, **kwargs):
        file_type = PaperFileType(event=dummy_event, name=name, **kwargs)
        db.session.add(file_type)
        db.session.flush()
        return file_type

    return _create


@pytest.fixture
def pdf_file_type(create_paper_file_type):
    return create_paper_file_type(
        'Paper', extensions=['pdf'], required=True, publishable=True, filename_template='paper-{code}'
    )


def test_paper_file_type_details(dummy_event, pdf_file_type, token_headers, test_client):
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/paper-file-types/{pdf_file_type.id}', headers=token_headers
    )
    assert resp.status_code == 200
    assert resp.json == {
        'id': pdf_file_type.id,
        'event_id': dummy_event.id,
        'name': 'Paper',
        'extensions': ['pdf'],
        'allow_multiple_files': False,
        'required': True,
        'publishable': True,
        'filename_template': 'paper-{code}',
        'is_used': False,
    }


def test_paper_file_type_list_is_sorted_by_name(
    dummy_event, pdf_file_type, create_paper_file_type, token_headers, test_client
):
    slides = create_paper_file_type('Slides', extensions=['pdf', 'pptx'], allow_multiple_files=True)
    source = create_paper_file_type('archive', extensions=['zip'])
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/paper-file-types', headers=token_headers)
    assert resp.status_code == 200
    assert [t['id'] for t in resp.json['results']] == [source.id, pdf_file_type.id, slides.id]
    assert resp.json['results'][2]['extensions'] == ['pdf', 'pptx']


def test_paper_file_types_need_the_papers_feature(db, dummy_event, pdf_file_type, token_headers, test_client):
    set_feature_enabled(dummy_event, 'papers', False)
    db.session.flush()
    url = f'/api/v1/events/{dummy_event.id}/paper-file-types'
    assert test_client.get(url, headers=token_headers).status_code == 404
    assert test_client.get(f'{url}/{pdf_file_type.id}', headers=token_headers).status_code == 404


def test_paper_file_type_denied_without_event_access(db, dummy_event, pdf_file_type, outsider_headers, test_client):
    dummy_event.protection_mode = ProtectionMode.protected
    db.session.flush()
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/paper-file-types/{pdf_file_type.id}', headers=outsider_headers
    )
    assert resp.status_code == 403
    assert 'error' in resp.json
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/paper-file-types', headers=outsider_headers)
    assert resp.status_code == 403


def test_paper_file_type_of_another_event_is_not_found(db, pdf_file_type, create_event, token_headers, test_client):
    other = create_event()
    set_feature_enabled(other, 'papers', True)
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{other.id}/paper-file-types/{pdf_file_type.id}', headers=token_headers)
    assert resp.status_code == 404


FILE_TYPE_FIELDS = (
    'id',
    'name',
    'extensions',
    'allow_multiple_files',
    'required',
    'publishable',
    'is_used',
    'filename_template',
)


def test_paper_file_type_list_matches_current_api(
    dummy_event, pdf_file_type, create_paper_file_type, token_headers, test_client, indico_api, same_json_list
):
    create_paper_file_type('Slides', extensions=['pdf', 'pptx'], allow_multiple_files=True)
    current = indico_api(f'/event/{dummy_event.id}/papers/api/file-types/')
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/paper-file-types', headers=token_headers).json
    same_json_list(new['results'], current, same=FILE_TYPE_FIELDS, derived={'event_id': lambda _: dummy_event.id})
