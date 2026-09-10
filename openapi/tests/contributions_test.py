# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


import pytest

from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.modules.events.contributions import contribution_settings
from indico.modules.events.contributions.models.persons import ContributionPersonLink


@pytest.fixture
def contribution_speaker(db, dummy_contribution, dummy_event_person):
    link = ContributionPersonLink(person=dummy_event_person, is_speaker=True)
    dummy_contribution.person_links.append(link)
    db.session.flush()
    return link


def test_contribution_details(dummy_event, dummy_contribution, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}',
                           headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_contribution.id
    assert resp.json['title'] == dummy_contribution.title
    assert resp.json['duration'] == dummy_contribution.duration.total_seconds()


def test_contribution_list(dummy_event, dummy_contribution, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions', headers=token_headers)
    assert resp.status_code == 200
    assert [c['id'] for c in resp.json['results']] == [dummy_contribution.id]


def test_contribution_denied_without_access(dummy_event, dummy_contribution, dummy_personal_token, create_user, db,
                                            test_client):
    outsider = create_user(42)
    dummy_personal_token.user = outsider
    dummy_personal_token.scopes = ['read:everything']
    dummy_event.protection_mode = ProtectionMode.protected
    db.session.flush()
    headers = {'Authorization': f'Bearer {dummy_personal_token._plaintext_token}'}
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}', headers=headers)
    assert resp.status_code == 403
    assert 'error' in resp.json


def test_contribution_list_denied_while_unpublished(dummy_event, dummy_contribution, dummy_personal_token,
                                                    create_user, db, test_client):
    outsider = create_user(42)
    dummy_personal_token.user = outsider
    dummy_personal_token.scopes = ['read:everything']
    contribution_settings.set(dummy_event, 'published', False)
    db.session.flush()
    headers = {'Authorization': f'Bearer {dummy_personal_token._plaintext_token}'}
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions', headers=headers)
    assert resp.status_code == 404


@pytest.mark.usefixtures('contribution_speaker')
def test_contribution_hides_person_contact_details(dummy_event, dummy_contribution, outsider_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}',
                           headers=outsider_headers)
    assert resp.status_code == 200
    assert resp.json['persons']
    assert all('email' not in person for person in resp.json['persons'])


@pytest.mark.usefixtures('contribution_speaker')
def test_contribution_list_hides_person_contact_details(dummy_event, dummy_contribution, outsider_headers,
                                                        test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions', headers=outsider_headers)
    assert resp.status_code == 200
    persons = resp.json['results'][0]['persons']
    assert persons
    assert all('email' not in person for person in persons)


CONTRIBUTION_FIELDS = ('id', 'friendly_id', 'title', 'description', 'code', 'board_number', 'keywords', 'duration',
                       'start_dt', 'end_dt', 'inherit_location', 'venue_name', 'room_name', 'address', 'abstract_id',
                       'track', 'session', 'session_block', 'type', 'persons', 'custom_fields')


@pytest.fixture
def event_manager(db, dummy_event, dummy_user):
    dummy_event.update_principal(dummy_user, full_access=True)
    db.session.flush()


def test_contribution_matches_current_api(dummy_event, dummy_contribution, contribution_speaker, event_manager,
                                          token_headers, test_client, indico_api, same_json):
    current = indico_api(f'/event/{dummy_event.id}/contributions/{dummy_contribution.id}.json')
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}',
                          headers=token_headers).json
    same_json(new, current, same=CONTRIBUTION_FIELDS)


def test_contribution_list_matches_current_api(dummy_event, dummy_contribution, create_contribution, event_manager,
                                               token_headers, test_client, indico_api, same_json_list):
    create_contribution(dummy_event, 'Another contribution')
    current = indico_api(f'/event/{dummy_event.id}/manage/contributions/contributions.json')
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions', headers=token_headers).json['results']
    same_json_list(new, current, same=CONTRIBUTION_FIELDS)
