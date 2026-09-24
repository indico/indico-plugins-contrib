# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 Unconventional
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from datetime import UTC, datetime

import pytest

from indico.core import signals
from indico.modules.events.requests.base import RequestDefinitionBase
from indico.modules.events.requests.models.requests import Request, RequestState


@pytest.fixture
def definitions():
    class CatsRequestDefinition(RequestDefinitionBase):
        name = 'cats'
        title = 'More cats'
        managers = set()

        @classmethod
        def can_be_managed(cls, user):
            return user in cls.managers

    class DogsRequestDefinition(CatsRequestDefinition):
        name = 'dogs'
        title = 'More dogs'
        managers = set()

    def _provide(sender, **kwargs):
        yield CatsRequestDefinition
        yield DogsRequestDefinition

    with signals.plugin.get_event_request_definitions.connected_to(_provide):
        yield {definition.name: definition for definition in (CatsRequestDefinition, DogsRequestDefinition)}


@pytest.fixture
def create_service_request(db, dummy_event, dummy_user):
    def _create(type_='cats', state=RequestState.pending, created_dt=None, **kwargs):
        kwargs.setdefault('data', {'how_many': 3})
        req = Request(event=dummy_event, type=type_, state=state, created_by_user=dummy_user, **kwargs)
        db.session.add(req)
        db.session.flush()
        if created_dt is not None:
            req.created_dt = created_dt
            db.session.flush()
        return req

    return _create


@pytest.fixture
def dummy_service_request(create_service_request):
    return create_service_request(created_dt=datetime(2026, 9, 1, 8, 0, tzinfo=UTC))


@pytest.mark.usefixtures('event_manager', 'definitions')
def test_service_request_details(dummy_event, dummy_service_request, dummy_user, token_headers, test_client):
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/requests/{dummy_service_request.id}', headers=token_headers
    )
    assert resp.status_code == 200
    assert resp.json == {
        'id': dummy_service_request.id,
        'event_id': dummy_event.id,
        'type': 'cats',
        'state': 'pending',
        'data': {'how_many': 3},
        'comment': None,
        'created_dt': '2026-09-01T08:00:00+00:00',
        'processed_dt': None,
        'processed_by': None,
        'created_by': {
            'id': dummy_user.id,
            'identifier': dummy_user.identifier,
            'full_name': dummy_user.full_name,
            'email': dummy_user.email,
        },
    }


@pytest.mark.usefixtures('event_manager', 'definitions')
def test_service_request_serves_who_processed_it(
    db, dummy_event, dummy_service_request, outsider, token_headers, test_client
):
    dummy_service_request.state = RequestState.accepted
    dummy_service_request.comment = 'Approved, enjoy'
    dummy_service_request.processed_by_user = outsider
    dummy_service_request.processed_dt = datetime(2026, 9, 2, 8, 0, tzinfo=UTC)
    db.session.flush()
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/requests/{dummy_service_request.id}', headers=token_headers
    )
    assert resp.json['state'] == 'accepted'
    assert resp.json['comment'] == 'Approved, enjoy'
    assert resp.json['processed_dt'] == '2026-09-02T08:00:00+00:00'
    assert resp.json['processed_by']['id'] == outsider.id


@pytest.mark.usefixtures('event_manager', 'definitions')
def test_service_request_list_is_newest_first(
    dummy_event, dummy_service_request, create_service_request, token_headers, test_client
):
    later = create_service_request('dogs', created_dt=datetime(2026, 9, 2, 8, 0, tzinfo=UTC))
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/requests', headers=token_headers)
    assert resp.status_code == 200
    assert [req['id'] for req in resp.json['results']] == [later.id, dummy_service_request.id]


@pytest.mark.usefixtures('event_manager', 'definitions')
def test_service_request_list_filters_by_type(
    dummy_event, dummy_service_request, create_service_request, token_headers, test_client
):
    create_service_request('dogs')
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/requests?type=cats', headers=token_headers)
    assert [req['id'] for req in resp.json['results']] == [dummy_service_request.id]


@pytest.mark.usefixtures('event_manager', 'definitions')
def test_service_request_list_filters_by_state(
    dummy_event, dummy_service_request, create_service_request, token_headers, test_client
):
    accepted = create_service_request('dogs', state=RequestState.accepted)
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/requests?state=accepted', headers=token_headers)
    assert [req['id'] for req in resp.json['results']] == [accepted.id]


@pytest.mark.usefixtures('event_manager', 'definitions')
def test_request_types_without_a_definition_are_not_served(
    dummy_event, create_service_request, token_headers, test_client
):
    orphan = create_service_request('birds')
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/requests', headers=token_headers)
    assert resp.json['results'] == []
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/requests/{orphan.id}', headers=token_headers)
    assert resp.status_code == 404


@pytest.mark.usefixtures('definitions')
def test_service_requests_are_manager_only(dummy_event, dummy_service_request, token_headers, test_client):
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/requests/{dummy_service_request.id}', headers=token_headers
    )
    assert resp.status_code == 403
    assert 'error' in resp.json
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/requests', headers=token_headers)
    assert resp.status_code == 403


def test_request_managers_see_only_the_types_they_manage(
    definitions, dummy_event, dummy_service_request, create_service_request, dummy_user, token_headers, test_client
):
    definitions['cats'].managers.add(dummy_user)
    theirs = create_service_request('dogs')
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/requests', headers=token_headers)
    assert resp.status_code == 200
    assert [req['id'] for req in resp.json['results']] == [dummy_service_request.id]
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/requests/{dummy_service_request.id}', headers=token_headers
    )
    assert resp.status_code == 200
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/requests/{theirs.id}', headers=token_headers)
    assert resp.status_code == 403


@pytest.mark.usefixtures('definitions')
def test_service_request_of_another_event_is_not_found(
    db, dummy_service_request, create_event, dummy_user, token_headers, test_client
):
    other = create_event()
    other.update_principal(dummy_user, full_access=True)
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{other.id}/requests/{dummy_service_request.id}', headers=token_headers)
    assert resp.status_code == 404
