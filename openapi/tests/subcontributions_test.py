# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest

from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.modules.events.contributions.models.persons import SubContributionPersonLink
from indico.modules.events.contributions.models.references import SubContributionReference


@pytest.fixture
def subcontribution_speaker(db, dummy_subcontribution, dummy_event_person):
    link = SubContributionPersonLink(person=dummy_event_person)
    dummy_subcontribution.person_links.append(link)
    db.session.flush()
    return link


def test_subcontribution_details(dummy_event, dummy_contribution, dummy_subcontribution, token_headers, test_client):
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}'
        f'/subcontributions/{dummy_subcontribution.id}',
        headers=token_headers,
    )
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_subcontribution.id
    assert resp.json['title'] == dummy_subcontribution.title
    assert resp.json['duration'] == dummy_subcontribution.duration.total_seconds()


@pytest.fixture
def referenced_subcontribution(db, dummy_subcontribution, doi):
    dummy_subcontribution.references.append(SubContributionReference(reference_type=doi, value='10.1000/xyz'))
    db.session.flush()
    return dummy_subcontribution


def test_subcontribution_details_carry_references(
    dummy_event, dummy_contribution, referenced_subcontribution, token_headers, test_client
):
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}'
        f'/subcontributions/{referenced_subcontribution.id}',
        headers=token_headers,
    )
    assert resp.json['references'] == [
        {'type': 'DOI', 'value': '10.1000/xyz', 'url': 'https://doi.org/10.1000/xyz', 'urn': 'doi:10.1000/xyz'}
    ]


def test_subcontribution_list(dummy_event, dummy_contribution, dummy_subcontribution, token_headers, test_client):
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}/subcontributions', headers=token_headers
    )
    assert resp.status_code == 200
    assert [s['id'] for s in resp.json['results']] == [dummy_subcontribution.id]


def test_subcontribution_denied_without_access(
    db, dummy_event, dummy_contribution, dummy_subcontribution, outsider_headers, test_client
):
    dummy_event.protection_mode = ProtectionMode.protected
    db.session.flush()
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}'
        f'/subcontributions/{dummy_subcontribution.id}',
        headers=outsider_headers,
    )
    assert resp.status_code == 403
    assert 'error' in resp.json


def test_subcontribution_of_another_contribution_is_not_found(
    dummy_event, dummy_subcontribution, create_contribution, token_headers, test_client
):
    other = create_contribution(dummy_event, 'Other')
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{other.id}/subcontributions/{dummy_subcontribution.id}',
        headers=token_headers,
    )
    assert resp.status_code == 404


@pytest.mark.usefixtures('subcontribution_speaker')
def test_subcontribution_hides_person_contact_details(
    dummy_event, dummy_contribution, dummy_subcontribution, outsider_headers, test_client
):
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}'
        f'/subcontributions/{dummy_subcontribution.id}',
        headers=outsider_headers,
    )
    assert resp.status_code == 200
    assert resp.json['persons']
    assert all('email' not in person for person in resp.json['persons'])


SUBCONTRIBUTION_FIELDS = ('friendly_id', 'title', 'code', 'references')

FOSSIL_PERSON_KEYS = {'id': 'db_id', 'email_hash': 'emailHash'}


def as_minutes(seconds):
    return seconds // 60


def test_subcontribution_matches_current_api(
    dummy_event,
    dummy_contribution,
    referenced_subcontribution,
    subcontribution_speaker,
    event_manager,
    token_headers,
    test_client,
    indico_api,
    same_json,
    rename_keys,
):
    current = indico_api(f'/export/event/{dummy_event.id}.json?detail=subcontributions')['results'][0]
    subcontrib = current['contributions'][0]['subContributions'][0]
    new = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}'
        f'/subcontributions/{referenced_subcontribution.id}',
        headers=token_headers,
    ).json
    same_json(
        new,
        subcontrib,
        same=SUBCONTRIBUTION_FIELDS,
        renamed={
            'id': ('db_id', None),
            'duration': ('duration', as_minutes),
            'persons': ('speakers', rename_keys(FOSSIL_PERSON_KEYS)),
        },
    )


def test_subcontribution_list_matches_current_api(
    dummy_event,
    dummy_contribution,
    referenced_subcontribution,
    subcontribution_speaker,
    create_subcontribution,
    event_manager,
    token_headers,
    test_client,
    indico_api,
    same_json_list,
    rename_keys,
):
    create_subcontribution(dummy_contribution, 'Another subcontribution')
    current = indico_api(f'/export/event/{dummy_event.id}.json?detail=subcontributions')['results'][0]
    new = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}/subcontributions', headers=token_headers
    ).json['results']
    same_json_list(
        new,
        current['contributions'][0]['subContributions'],
        same=SUBCONTRIBUTION_FIELDS,
        renamed={
            'id': ('db_id', None),
            'duration': ('duration', as_minutes),
            'persons': ('speakers', rename_keys(FOSSIL_PERSON_KEYS)),
        },
    )
