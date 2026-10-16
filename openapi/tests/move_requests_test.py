# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 Unconventional
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from datetime import UTC, datetime

import pytest

from indico.modules.categories.models.event_move_request import EventMoveRequest, MoveRequestState


@pytest.fixture
def category_manager(db, dummy_category, dummy_user):
    dummy_category.update_principal(dummy_user, full_access=True)
    db.session.flush()


@pytest.fixture
def create_move_request(db, dummy_category, dummy_user):
    def _create(event, **kwargs):
        kwargs.setdefault('requestor', dummy_user)
        kwargs.setdefault('requestor_comment', 'This fits better here.')
        kwargs.setdefault('requested_dt', datetime(2026, 9, 1, 8, 0, tzinfo=UTC))
        request = EventMoveRequest(event=event, category=dummy_category, **kwargs)
        db.session.add(request)
        db.session.flush()
        return request

    return _create


@pytest.fixture
def dummy_move_request(dummy_event, create_move_request):
    return create_move_request(dummy_event)


@pytest.mark.usefixtures('category_manager')
def test_move_request_details(dummy_category, dummy_event, dummy_move_request, dummy_user, token_headers, test_client):
    resp = test_client.get(
        f'/api/v1/categories/{dummy_category.id}/move-requests/{dummy_move_request.id}', headers=token_headers
    )
    assert resp.status_code == 200
    assert resp.json == {
        'id': dummy_move_request.id,
        'category_id': dummy_category.id,
        'event_id': dummy_event.id,
        'state': 'pending',
        'requestor': resp.json['requestor'],
        'requestor_comment': 'This fits better here.',
        'requested_dt': '2026-09-01T08:00:00+00:00',
        'moderator': None,
        'moderator_comment': '',
    }
    assert resp.json['requestor']['id'] == dummy_user.id


@pytest.mark.usefixtures('category_manager')
def test_move_request_list_carries_every_state(
    db,
    dummy_category,
    dummy_event,
    dummy_move_request,
    create_event,
    create_move_request,
    dummy_user,
    token_headers,
    test_client,
):
    other = create_event()
    rejected = create_move_request(
        other, state=MoveRequestState.rejected, moderator=dummy_user, moderator_comment='Not this one.'
    )
    url = f'/api/v1/categories/{dummy_category.id}/move-requests'
    resp = test_client.get(url, headers=token_headers)
    assert resp.status_code == 200
    assert [r['id'] for r in resp.json['results']] == [dummy_move_request.id, rejected.id]
    assert resp.json['results'][1]['moderator']['id'] == dummy_user.id
    assert resp.json['results'][1]['moderator_comment'] == 'Not this one.'
    resp = test_client.get(f'{url}?state=pending', headers=token_headers)
    assert [r['id'] for r in resp.json['results']] == [dummy_move_request.id]


def test_move_requests_are_manager_only(dummy_category, dummy_move_request, outsider_headers, test_client):
    url = f'/api/v1/categories/{dummy_category.id}/move-requests'
    resp = test_client.get(f'{url}/{dummy_move_request.id}', headers=outsider_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json
    assert test_client.get(url, headers=outsider_headers).status_code == 403


@pytest.mark.usefixtures('category_manager')
def test_move_request_of_another_category_is_not_found(
    db, dummy_move_request, create_category, dummy_user, token_headers, test_client
):
    other = create_category(1)
    other.update_principal(dummy_user, full_access=True)
    db.session.flush()
    resp = test_client.get(
        f'/api/v1/categories/{other.id}/move-requests/{dummy_move_request.id}', headers=token_headers
    )
    assert resp.status_code == 404


MOVE_REQUEST_FIELDS = ('id', 'state', 'requestor_comment', 'requested_dt')

REQUESTOR_KEYS = ('id', 'first_name', 'last_name', 'full_name', 'affiliation')


def as_requestor(requestor):
    return {key: requestor[key] for key in REQUESTOR_KEYS}


@pytest.mark.usefixtures('category_manager')
def test_move_request_list_matches_current_api(
    dummy_category, dummy_event, dummy_move_request, token_headers, test_client, indico_api, same_json_list
):
    current = indico_api(f'/category/{dummy_category.id}/api/event-move-requests')
    new = test_client.get(
        f'/api/v1/categories/{dummy_category.id}/move-requests?state=pending', headers=token_headers
    ).json
    same_json_list(
        new['results'],
        current,
        same=MOVE_REQUEST_FIELDS,
        renamed={'requestor': ('requestor', as_requestor)},
        derived={
            'event_id': lambda current: current['event']['id'],
            # the moderation page carries the category the event is in, not the one it would move to
            'category_id': lambda _: dummy_category.id,
            # it only lists the pending requests, which nobody has answered yet
            'moderator': lambda _: None,
            'moderator_comment': lambda _: '',
        },
    )
