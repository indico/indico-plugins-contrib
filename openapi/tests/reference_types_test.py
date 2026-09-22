# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest

from indico.modules.events.models.references import ReferenceType


@pytest.fixture
def create_reference_type(db):
    def _create(name, scheme='', url_template=''):
        reference_type = ReferenceType(name=name, scheme=scheme, url_template=url_template)
        db.session.add(reference_type)
        db.session.flush()
        return reference_type

    return _create


def test_reference_type_details(doi, token_headers, test_client):
    resp = test_client.get(f'/api/v1/reference-types/{doi.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json == {'id': doi.id, 'name': 'DOI', 'scheme': 'doi', 'url_template': 'https://doi.org/{value}'}


def test_reference_type_list_is_sorted_by_name(doi, create_reference_type, token_headers, test_client):
    arxiv = create_reference_type('arXiv', url_template='https://arxiv.org/abs/{value}')
    resp = test_client.get('/api/v1/reference-types', headers=token_headers)
    assert resp.status_code == 200
    assert [reference_type['id'] for reference_type in resp.json['results']] == [arxiv.id, doi.id]


def test_reference_types_are_served_to_any_caller(doi, outsider_headers, test_client):
    # the identifiers themselves are published next to the events carrying them, so the systems they
    # point at are not restricted either
    assert test_client.get('/api/v1/reference-types', headers=outsider_headers).json['count'] == 1
    assert test_client.get(f'/api/v1/reference-types/{doi.id}', headers=outsider_headers).status_code == 200
