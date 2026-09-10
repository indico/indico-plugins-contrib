# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from uuid import uuid4

import pytest

from indico.modules.events.agreements.models.agreements import Agreement, AgreementState
from indico.util.date_time import now_utc


@pytest.fixture
def create_agreement(db, dummy_event):
    def _create_agreement(person_name, **params):
        params.setdefault('person_email', 'signer@example.test')
        params.setdefault('type', 'cern-speaker-release')
        params.setdefault('state', AgreementState.pending)
        agreement = Agreement(uuid=str(uuid4()), event=dummy_event, person_name=person_name,
                             identifier=f'Email:{params["person_email"]}', **params)
        db.session.add(agreement)
        db.session.flush()
        return agreement

    return _create_agreement


@pytest.fixture
def dummy_agreement(create_agreement):
    return create_agreement('Alice Smith')


@pytest.fixture
def event_manager(db, dummy_event, dummy_user):
    dummy_event.update_principal(dummy_user, full_access=True)
    db.session.flush()


def test_agreement_details(dummy_agreement, dummy_event, event_manager, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/agreements/{dummy_agreement.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_agreement.id
    assert resp.json['event_id'] == dummy_event.id
    assert resp.json['type'] == 'cern-speaker-release'
    assert resp.json['identifier'] == 'Email:signer@example.test'
    assert resp.json['person_name'] == 'Alice Smith'
    assert resp.json['person_email'] == 'signer@example.test'
    assert resp.json['state'] == 'pending'
    assert resp.json['timestamp'] == dummy_agreement.timestamp.isoformat()
    assert resp.json['user_id'] is None
    assert resp.json['signed_dt'] is None
    assert resp.json['reason'] is None
    assert resp.json['attachment_filename'] is None
    assert resp.json['data'] is None


def test_signed_agreement(db, create_agreement, dummy_event, dummy_user, event_manager, token_headers, test_client):
    signed_dt = now_utc()
    agreement = create_agreement('Alice Smith', state=AgreementState.accepted_on_behalf, user=dummy_user,
                                 signed_dt=signed_dt, reason='Signed by phone', attachment_filename='release.pdf',
                                 data={'speaker_id': 7})
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/agreements/{agreement.id}', headers=token_headers)
    assert resp.json['state'] == 'accepted_on_behalf'
    assert resp.json['user_id'] == dummy_user.id
    assert resp.json['signed_dt'] == signed_dt.isoformat()
    assert resp.json['reason'] == 'Signed by phone'
    assert resp.json['attachment_filename'] == 'release.pdf'
    assert resp.json['data'] == {'speaker_id': 7}


def test_agreement_list(dummy_agreement, create_agreement, dummy_event, event_manager, token_headers, test_client):
    other = create_agreement('Aaron Baker', person_email='other@example.test')
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/agreements', headers=token_headers)
    assert resp.status_code == 200
    assert [a['id'] for a in resp.json['results']] == [other.id, dummy_agreement.id]


def test_agreement_list_filtered_by_type(dummy_agreement, create_agreement, dummy_event, event_manager, token_headers,
                                         test_client):
    create_agreement('Alice Smith', type='other-release')
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/agreements?type=cern-speaker-release',
                           headers=token_headers)
    assert [a['id'] for a in resp.json['results']] == [dummy_agreement.id]


def test_agreement_does_not_expose_the_signing_token(dummy_agreement, dummy_event, event_manager, token_headers,
                                                     test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/agreements/{dummy_agreement.id}', headers=token_headers)
    assert 'uuid' not in resp.json


def test_agreements_are_manager_only(dummy_agreement, dummy_event, outsider_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/agreements/{dummy_agreement.id}',
                           headers=outsider_headers)
    assert resp.status_code == 403
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/agreements', headers=outsider_headers)
    assert resp.status_code == 403


def test_agreement_of_another_event_is_not_found(dummy_agreement, create_event, dummy_user, db, token_headers,
                                                test_client):
    other = create_event()
    other.update_principal(dummy_user, full_access=True)
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{other.id}/agreements/{dummy_agreement.id}', headers=token_headers)
    assert resp.status_code == 404
