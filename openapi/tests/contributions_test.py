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


@pytest.mark.usefixtures('contribution_speaker')
def test_contribution_matches_indico_api(dummy_event, dummy_contribution, token_headers, test_client, indico_api,
                                         as_legacy_date):
    legacy = indico_api(f'/export/event/{dummy_event.id}.json?detail=contributions')['results'][0]['contributions'][0]
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}',
                          headers=token_headers).json
    assert new['id'] == legacy['db_id']
    assert new['friendly_id'] == legacy['friendly_id']
    assert new['title'] == legacy['title']
    assert new['description'] == legacy['description']
    assert new['code'] == legacy['code']
    assert new['board_number'] == legacy['board_number']
    assert new['keywords'] == legacy['keywords']
    assert new['duration'] == legacy['duration'] * 60
    assert new['venue_name'] == legacy['location']
    assert new['room_name'] == legacy['roomFullname']
    assert (new['track'] or {}).get('title') == legacy['track']
    assert (new['session'] or {}).get('title') == legacy['session']
    assert (new['type'] or {}).get('name') == legacy['type']
    assert as_legacy_date(new['start_dt']) == legacy['startDate']
    assert as_legacy_date(new['end_dt']) == legacy['endDate']
    speakers = [p for p in new['persons'] if p['is_speaker']]
    assert [(p['first_name'], p['last_name'], p['affiliation'], p['email_hash']) for p in speakers] == \
           [(p['first_name'], p['last_name'], p['affiliation'], p['emailHash']) for p in legacy['speakers']]
    authors = [p for p in new['persons'] if p['author_type'] == 'primary']
    assert [p['email_hash'] for p in authors] == [p['emailHash'] for p in legacy['primaryauthors']]


def test_contribution_list_matches_indico_api(dummy_event, dummy_contribution, create_contribution, token_headers,
                                              test_client, indico_api):
    create_contribution(dummy_event, 'Another contribution')
    legacy = {c['db_id']: c for c in
              indico_api(f'/export/event/{dummy_event.id}.json?detail=contributions')['results'][0]['contributions']}
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions', headers=token_headers).json['results']
    assert {c['id'] for c in new} == set(legacy)
    for contrib in new:
        assert contrib['title'] == legacy[contrib['id']]['title']
        assert contrib['friendly_id'] == legacy[contrib['id']]['friendly_id']
        assert contrib['duration'] == legacy[contrib['id']]['duration'] * 60
