# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 Unconventional
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest

from indico.modules.users.models.affiliations import Affiliation


@pytest.fixture
def create_affiliation(db):
    def _create(name, **values):
        affiliation = Affiliation(name=name, **values)
        db.session.add(affiliation)
        db.session.flush()
        return affiliation

    return _create


def test_affiliation_details(dummy_affiliation, token_headers, test_client):
    resp = test_client.get(f'/api/v1/affiliations/{dummy_affiliation.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json == {
        'id': dummy_affiliation.id,
        'name': 'ACME',
        'code': 'ACM',
        'alt_names': ['Acme Inc'],
        'street': '1 Main street',
        'postcode': '1211',
        'city': 'Geneva',
        'country_code': 'CH',
        'country_name': 'Switzerland',
        'meta': {'source': 'test'},
    }


def test_affiliation_list_is_sorted_by_name(dummy_affiliation, create_affiliation, token_headers, test_client):
    other = create_affiliation('Ábaco Institute')
    resp = test_client.get('/api/v1/affiliations', headers=token_headers)
    assert resp.status_code == 200
    assert [affiliation['id'] for affiliation in resp.json['results']] == [other.id, dummy_affiliation.id]


def test_deleted_affiliations_are_not_served(db, dummy_affiliation, token_headers, test_client):
    dummy_affiliation.is_deleted = True
    db.session.flush()
    assert test_client.get('/api/v1/affiliations', headers=token_headers).json['count'] == 0
    assert test_client.get(f'/api/v1/affiliations/{dummy_affiliation.id}', headers=token_headers).status_code == 404


def test_affiliations_are_served_to_any_caller(dummy_affiliation, outsider_headers, test_client):
    # an affiliation is published next to every person carrying it, and the interface lets anybody
    # search the catalogue while filling in a name
    assert test_client.get('/api/v1/affiliations', headers=outsider_headers).json['count'] == 1
    assert test_client.get(f'/api/v1/affiliations/{dummy_affiliation.id}', headers=outsider_headers).status_code == 200


AFFILIATION_FIELDS = (
    'id',
    'name',
    'code',
    'alt_names',
    'street',
    'postcode',
    'city',
    'country_code',
    'country_name',
    'meta',
)


def test_affiliation_list_matches_current_api(
    dummy_affiliation, create_affiliation, admin_headers, test_client, indico_api, same_json_list
):
    create_affiliation('Ábaco Institute', code='ABI', city='Madrid', country_code='ES')
    # only the administration area lists the catalogue as a whole, while the search every user calls
    # while filling in a name answers with the same fields
    current = indico_api('/api/admin/affiliations')
    new = test_client.get('/api/v1/affiliations', headers=admin_headers).json
    same_json_list(new['results'], current, same=AFFILIATION_FIELDS)
