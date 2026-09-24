# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest

from indico.modules.rb import rb_settings
from indico.modules.rb.models.map_areas import MapArea


@pytest.fixture
def create_map_area(db):
    def _create(name, is_default=False, corners=(46.24, 6.04, 46.22, 6.06)):
        top_left_latitude, top_left_longitude, bottom_right_latitude, bottom_right_longitude = corners
        area = MapArea(
            name=name,
            is_default=is_default,
            top_left_latitude=top_left_latitude,
            top_left_longitude=top_left_longitude,
            bottom_right_latitude=bottom_right_latitude,
            bottom_right_longitude=bottom_right_longitude,
        )
        db.session.add(area)
        db.session.flush()
        return area

    return _create


@pytest.fixture
def dummy_map_area(create_map_area):
    return create_map_area('Main site', is_default=True)


def test_map_area_details(dummy_map_area, token_headers, test_client):
    resp = test_client.get(f'/api/v1/map-areas/{dummy_map_area.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json == {
        'id': dummy_map_area.id,
        'name': 'Main site',
        'is_default': True,
        'top_left_latitude': 46.24,
        'top_left_longitude': 6.04,
        'bottom_right_latitude': 46.22,
        'bottom_right_longitude': 6.06,
    }


def test_map_area_list(dummy_map_area, create_map_area, token_headers, test_client):
    other = create_map_area('Annex')
    resp = test_client.get('/api/v1/map-areas', headers=token_headers)
    assert resp.status_code == 200
    assert [area['name'] for area in resp.json['results']] == ['Annex', 'Main site']
    assert [area['id'] for area in resp.json['results']] == [other.id, dummy_map_area.id]


def test_map_areas_require_booking_access(dummy_map_area, dummy_user, outsider_headers, test_client):
    rb_settings.acls.add_principal('authorized_principals', dummy_user)
    assert test_client.get('/api/v1/map-areas', headers=outsider_headers).status_code == 403
    resp = test_client.get(f'/api/v1/map-areas/{dummy_map_area.id}', headers=outsider_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json


MAP_AREA_FIELDS = (
    'id',
    'name',
    'is_default',
    'top_left_latitude',
    'top_left_longitude',
    'bottom_right_latitude',
    'bottom_right_longitude',
)


def test_map_area_list_matches_current_api(
    dummy_map_area, create_map_area, token_headers, test_client, indico_api, same_json_list
):
    create_map_area('Annex')
    current = indico_api('/rooms/api/map-areas')
    new = test_client.get('/api/v1/map-areas', headers=token_headers).json
    same_json_list(new['results'], current, same=MAP_AREA_FIELDS)
