# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from datetime import UTC, datetime

import pytest

from indico.modules.events.static.models.static import StaticSite, StaticSiteState


@pytest.fixture
def create_offline_copy(db, dummy_event, dummy_user):
    def _create(requested_dt, state=StaticSiteState.pending):
        site = StaticSite(event=dummy_event, creator=dummy_user, requested_dt=requested_dt, state=state)
        db.session.add(site)
        db.session.flush()
        return site

    return _create


@pytest.fixture
def dummy_offline_copy(create_offline_copy):
    return create_offline_copy(datetime(2026, 9, 1, 8, 0, tzinfo=UTC))


@pytest.mark.usefixtures('event_manager')
def test_offline_copy_details(dummy_event, dummy_offline_copy, dummy_user, token_headers, test_client):
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/offline-copies/{dummy_offline_copy.id}', headers=token_headers
    )
    assert resp.status_code == 200
    assert resp.json == {
        'id': dummy_offline_copy.id,
        'event_id': dummy_event.id,
        'state': 'pending',
        'requested_dt': '2026-09-01T08:00:00+00:00',
        'creator': {
            'id': dummy_user.id,
            'identifier': dummy_user.identifier,
            'full_name': dummy_user.full_name,
            'email': dummy_user.email,
        },
        'download_url': None,
    }


@pytest.mark.usefixtures('event_manager')
def test_download_url_is_served_once_the_build_succeeded(dummy_event, create_offline_copy, token_headers, test_client):
    site = create_offline_copy(datetime(2026, 9, 1, 8, 0, tzinfo=UTC), state=StaticSiteState.success)
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/offline-copies/{site.id}', headers=token_headers)
    assert resp.json['state'] == 'success'
    assert resp.json['download_url'].endswith(f'/event/{dummy_event.id}/manage/offline-copy/{site.id}.zip')


@pytest.mark.usefixtures('event_manager')
def test_a_build_that_failed_has_nothing_to_download(dummy_event, create_offline_copy, token_headers, test_client):
    site = create_offline_copy(datetime(2026, 9, 1, 8, 0, tzinfo=UTC), state=StaticSiteState.failed)
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/offline-copies/{site.id}', headers=token_headers)
    assert resp.json['state'] == 'failed'
    assert resp.json['download_url'] is None


@pytest.mark.usefixtures('event_manager')
def test_offline_copy_list_is_ordered_by_request_time(
    dummy_event, dummy_offline_copy, create_offline_copy, token_headers, test_client
):
    later = create_offline_copy(datetime(2026, 9, 2, 8, 0, tzinfo=UTC))
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/offline-copies', headers=token_headers)
    assert resp.status_code == 200
    assert [site['id'] for site in resp.json['results']] == [later.id, dummy_offline_copy.id]


def test_offline_copies_are_manager_only(dummy_event, dummy_offline_copy, token_headers, test_client):
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/offline-copies/{dummy_offline_copy.id}', headers=token_headers
    )
    assert resp.status_code == 403
    assert 'error' in resp.json
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/offline-copies', headers=token_headers)
    assert resp.status_code == 403


def test_offline_copy_of_another_event_is_not_found(
    db, dummy_offline_copy, create_event, dummy_user, token_headers, test_client
):
    other = create_event(1, creator_has_privileges=True)
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{other.id}/offline-copies/{dummy_offline_copy.id}', headers=token_headers)
    assert resp.status_code == 404
