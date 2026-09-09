# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


import pytest

from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.modules.events.contributions.models.persons import SubContributionPersonLink


@pytest.fixture
def subcontribution_speaker(db, dummy_subcontribution, dummy_event_person):
    link = SubContributionPersonLink(person=dummy_event_person)
    dummy_subcontribution.person_links.append(link)
    db.session.flush()
    return link


@pytest.fixture
def token_headers(dummy_personal_token):
    dummy_personal_token.scopes = ['read:everything']
    return {'Authorization': f'Bearer {dummy_personal_token._plaintext_token}'}


@pytest.fixture
def outsider_headers(db, dummy_personal_token, create_user):
    dummy_personal_token.user = create_user(42)
    dummy_personal_token.scopes = ['read:everything']
    db.session.flush()
    return {'Authorization': f'Bearer {dummy_personal_token._plaintext_token}'}


def test_subcontribution_details(dummy_event, dummy_contribution, dummy_subcontribution, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}'
                           f'/subcontributions/{dummy_subcontribution.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_subcontribution.id
    assert resp.json['title'] == dummy_subcontribution.title
    assert resp.json['contribution_id'] == dummy_contribution.id
    assert resp.json['duration'] == dummy_subcontribution.duration.total_seconds()


def test_subcontribution_list(dummy_event, dummy_contribution, dummy_subcontribution, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}'
                           f'/subcontributions', headers=token_headers)
    assert resp.status_code == 200
    assert [s['id'] for s in resp.json['results']] == [dummy_subcontribution.id]


def test_subcontribution_denied_without_access(db, dummy_event, dummy_contribution, dummy_subcontribution,
                                               outsider_headers, test_client):
    dummy_event.protection_mode = ProtectionMode.protected
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}'
                           f'/subcontributions/{dummy_subcontribution.id}', headers=outsider_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json


def test_subcontribution_of_another_contribution_is_not_found(dummy_event, dummy_subcontribution,
                                                              create_contribution, token_headers, test_client):
    other = create_contribution(dummy_event, 'Other')
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions/{other.id}'
                           f'/subcontributions/{dummy_subcontribution.id}', headers=token_headers)
    assert resp.status_code == 404


@pytest.mark.usefixtures('subcontribution_speaker')
def test_subcontribution_hides_person_contact_details(dummy_event, dummy_contribution, dummy_subcontribution,
                                                      outsider_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}'
                           f'/subcontributions/{dummy_subcontribution.id}', headers=outsider_headers)
    assert resp.status_code == 200
    assert resp.json['persons']
    assert all('email' not in person for person in resp.json['persons'])
