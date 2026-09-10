# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


import pytest

from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.modules.events.contributions.models.persons import AuthorType, ContributionPersonLink
from indico.modules.events.models.persons import EventPersonLink
from indico.modules.events.sessions.models.persons import SessionBlockPersonLink


@pytest.fixture
def event_chair(db, dummy_event, dummy_event_person):
    link = EventPersonLink(person=dummy_event_person)
    dummy_event.person_links.append(link)
    db.session.flush()
    return link


@pytest.fixture
def contribution_author(db, dummy_contribution, create_event_person, create_user):
    person = create_event_person(dummy_contribution.event, create_user(11))
    link = ContributionPersonLink(person=person, is_speaker=False, author_type=AuthorType.primary)
    dummy_contribution.person_links.append(link)
    db.session.flush()
    return person


@pytest.fixture
def block_convener(db, dummy_session_block, create_event_person, create_user):
    person = create_event_person(dummy_session_block.event, create_user(12))
    link = SessionBlockPersonLink(person=person)
    dummy_session_block.person_links.append(link)
    db.session.flush()
    return person


def test_person_details(dummy_event, dummy_event_person, event_chair, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/persons/{dummy_event_person.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_event_person.id
    assert resp.json['first_name'] == dummy_event_person.first_name
    assert resp.json['last_name'] == dummy_event_person.last_name
    assert resp.json['full_name'] == dummy_event_person.full_name
    assert resp.json['identifier'] == dummy_event_person.identifier
    assert resp.json['roles'] == ['chairperson']


@pytest.mark.usefixtures('event_chair')
def test_person_list(dummy_event, dummy_event_person, contribution_author, block_convener, token_headers,
                     test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/persons', headers=token_headers)
    assert resp.status_code == 200
    roles = {p['id']: p['roles'] for p in resp.json['results']}
    assert roles == {dummy_event_person.id: ['chairperson'],
                     contribution_author.id: ['author'],
                     block_convener.id: ['convener']}


def test_person_roles_add_up(db, dummy_event, dummy_event_person, event_chair, dummy_contribution, token_headers,
                             test_client):
    dummy_contribution.person_links.append(ContributionPersonLink(person=dummy_event_person, is_speaker=True))
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/persons/{dummy_event_person.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['roles'] == ['chairperson', 'speaker']


@pytest.mark.usefixtures('event_chair')
def test_person_hides_contact_details(db, dummy_event, dummy_event_person, dummy_user, token_headers, test_client):
    url = f'/api/v1/events/{dummy_event.id}/persons/{dummy_event_person.id}'
    resp = test_client.get(url, headers=token_headers)
    assert resp.status_code == 200
    assert 'email' not in resp.json
    assert 'phone' not in resp.json
    assert 'address' not in resp.json
    assert resp.json['email_hash']
    dummy_event.update_principal(dummy_user, full_access=True)
    db.session.flush()
    manager = test_client.get(url, headers=token_headers)
    assert manager.json['email'] == dummy_event_person.email


def test_person_without_visible_role_is_not_listed(dummy_event, dummy_event_person, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/persons', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['results'] == []
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/persons/{dummy_event_person.id}', headers=token_headers)
    assert resp.status_code == 403


def test_person_of_protected_session_is_hidden(db, dummy_event, dummy_session, dummy_session_block, block_convener,
                                               outsider_headers, test_client):
    dummy_session.protection_mode = ProtectionMode.protected
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/persons', headers=outsider_headers)
    assert resp.status_code == 200
    assert resp.json['results'] == []


def test_person_of_another_event_is_not_found(dummy_event_person, create_event, token_headers, test_client):
    other = create_event()
    resp = test_client.get(f'/api/v1/events/{other.id}/persons/{dummy_event_person.id}', headers=token_headers)
    assert resp.status_code == 404


@pytest.mark.usefixtures('event_chair')
def test_person_matches_indico_api(dummy_event, dummy_event_person, token_headers, test_client, indico_api):
    legacy = indico_api(f'/export/event/{dummy_event.id}.json')['results'][0]['chairs'][0]
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/persons/{dummy_event_person.id}',
                          headers=token_headers).json
    assert new['id'] == legacy['person_id']
    assert new['first_name'] == legacy['first_name']
    assert new['last_name'] == legacy['last_name']
    assert new['affiliation'] == legacy['affiliation']
    assert new['email_hash'] == legacy['emailHash']
    assert new.get('email') == legacy.get('email')


@pytest.mark.usefixtures('event_chair')
def test_person_list_matches_indico_api(dummy_event, dummy_event_person, token_headers, test_client, indico_api):
    legacy = {c['person_id']: c for c in indico_api(f'/export/event/{dummy_event.id}.json')['results'][0]['chairs']}
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/persons', headers=token_headers).json['results']
    chairs = [p for p in new if 'chairperson' in p['roles']]
    assert {p['id'] for p in chairs} == set(legacy)
    for person in chairs:
        assert person['first_name'] == legacy[person['id']]['first_name']
        assert person['last_name'] == legacy[person['id']]['last_name']
        assert person['email_hash'] == legacy[person['id']]['emailHash']
