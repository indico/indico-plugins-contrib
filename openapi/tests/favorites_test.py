# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 Unconventional
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest

from indico.core.db.sqlalchemy.protection import ProtectionMode


@pytest.fixture
def favorites(db, dummy_user, outsider, dummy_category, dummy_event, dummy_room):
    dummy_user.favorite_users.add(outsider)
    dummy_user.favorite_categories.add(dummy_category)
    dummy_user.favorite_events.add(dummy_event)
    dummy_user.favorite_rooms.add(dummy_room)
    db.session.flush()


def test_favorite_users_match_the_current_api(favorites, outsider, indico_api, token_headers, test_client):
    resp = test_client.get('/api/v1/users/me/favorite-users', headers=token_headers)
    assert resp.status_code == 200
    assert [user['id'] for user in resp.json['results']] == [outsider.id]
    assert {user['identifier'] for user in resp.json['results']} == set(indico_api('/user/api/favorites/users'))


def test_favorite_categories_match_the_current_api(favorites, dummy_category, indico_api, token_headers, test_client):
    resp = test_client.get('/api/v1/users/me/favorite-categories', headers=token_headers)
    assert resp.status_code == 200
    assert [category['id'] for category in resp.json['results']] == [dummy_category.id]
    assert {str(category['id']) for category in resp.json['results']} == set(
        indico_api('/user/api/favorites/categories')
    )


def test_favorite_events_match_the_current_api(favorites, dummy_event, indico_api, token_headers, test_client):
    resp = test_client.get('/api/v1/users/me/favorite-events', headers=token_headers)
    assert resp.status_code == 200
    assert [event['id'] for event in resp.json['results']] == [dummy_event.id]
    assert {str(event['id']) for event in resp.json['results']} == set(indico_api('/user/api/favorites/events'))


def test_favorite_rooms_match_the_current_api(favorites, dummy_room, indico_api, token_headers, test_client):
    resp = test_client.get('/api/v1/users/me/favorite-rooms', headers=token_headers)
    assert resp.status_code == 200
    assert [room['id'] for room in resp.json['results']] == [dummy_room.id]
    assert [room['id'] for room in resp.json['results']] == indico_api('/rooms/api/user/favorite-rooms/')


def test_favorite_events_leave_out_deleted_ones(favorites, db, dummy_event, token_headers, test_client):
    dummy_event.is_deleted = True
    db.session.flush()
    resp = test_client.get('/api/v1/users/me/favorite-events', headers=token_headers)
    assert resp.json['results'] == []


def test_favorite_categories_leave_out_what_the_caller_cannot_read(
    favorites, db, dummy_category, create_user, token_headers, test_client
):
    dummy_category.protection_mode = ProtectionMode.protected
    dummy_category.update_principal(create_user(123), read_access=True)
    db.session.flush()
    resp = test_client.get('/api/v1/users/me/favorite-categories', headers=token_headers)
    assert resp.json['results'] == []


@pytest.mark.parametrize('path', ('favorite-users', 'favorite-categories', 'favorite-events', 'favorite-rooms'))
def test_favorites_are_served_for_the_caller_alone(favorites, path, outsider_headers, test_client):
    # the endpoints answer about whoever holds the token, so another user sees their own empty lists
    resp = test_client.get(f'/api/v1/users/me/{path}', headers=outsider_headers)
    assert resp.status_code == 200
    assert resp.json['results'] == []
