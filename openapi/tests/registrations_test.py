# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from datetime import timedelta

import pytest

from indico.modules.events.registration.models.registrations import (
    PublishRegistrationsMode,
    RegistrationState,
    RegistrationVisibility,
)
from indico.util.date_time import now_utc


@pytest.fixture
def open_regform(db, dummy_regform):
    dummy_regform.start_dt = now_utc() - timedelta(days=1)
    dummy_regform.end_dt = now_utc() + timedelta(days=1)
    db.session.flush()
    return dummy_regform


@pytest.fixture
def published_reg(db, dummy_regform, dummy_reg):
    dummy_regform.publish_registrations_public = PublishRegistrationsMode.show_all
    dummy_regform.publish_registrations_participants = PublishRegistrationsMode.show_all
    db.session.flush()
    return dummy_reg


def test_registration_form_list(dummy_event, open_regform, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registration-forms', headers=token_headers)
    assert resp.status_code == 200
    form = resp.json['results'][0]
    assert form['id'] == open_regform.id
    assert form['event_id'] == dummy_event.id
    assert form['title'] == open_regform.title
    assert form['currency'] == open_regform.currency
    assert form['is_open']
    assert form['is_scheduled']


def test_registration_form_details(dummy_event, open_regform, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registration-forms/{open_regform.id}',
                           headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == open_regform.id
    assert resp.json['base_price'] == str(open_regform.base_price)
    assert resp.json['moderation_enabled'] == open_regform.moderation_enabled


def test_registration_form_hidden_until_scheduled(dummy_event, dummy_regform, outsider_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registration-forms', headers=outsider_headers)
    assert resp.status_code == 200
    assert resp.json['results'] == []
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registration-forms/{dummy_regform.id}',
                           headers=outsider_headers)
    assert resp.status_code == 403


def test_registration_form_hides_count(db, dummy_event, open_regform, dummy_reg, token_headers, test_client):
    url = f'/api/v1/events/{dummy_event.id}/registration-forms/{open_regform.id}'
    assert 'registration_count' not in test_client.get(url, headers=token_headers).json
    open_regform.publish_registration_count = True
    db.session.flush()
    assert test_client.get(url, headers=token_headers).json['registration_count'] == 1


def test_own_registration_is_visible(dummy_event, dummy_reg, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registrations/{dummy_reg.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_reg.id
    assert resp.json['friendly_id'] == dummy_reg.friendly_id
    assert resp.json['registration_form_id'] == dummy_reg.registration_form_id
    assert resp.json['full_name'] == dummy_reg.full_name
    assert resp.json['email'] == dummy_reg.email
    assert resp.json['state'] == RegistrationState.complete.name
    assert resp.json['price'] == str(dummy_reg.price)
    assert resp.json['formatted_price'] == dummy_reg.render_price()


def test_registration_hidden_from_others(dummy_event, dummy_reg, outsider_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registrations', headers=outsider_headers)
    assert resp.status_code == 200
    assert resp.json['results'] == []
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registrations/{dummy_reg.id}', headers=outsider_headers)
    assert resp.status_code == 403


def test_published_registration_hides_restricted_fields(dummy_event, published_reg, outsider_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registrations', headers=outsider_headers)
    assert resp.status_code == 200
    reg = resp.json['results'][0]
    assert reg['id'] == published_reg.id
    assert reg['full_name'] == published_reg.full_name
    assert reg['first_name'] == published_reg.first_name
    assert 'email' not in reg
    assert 'state' not in reg
    assert 'price' not in reg
    assert 'checked_in' not in reg


def test_published_registration_shows_checkin_when_enabled(db, dummy_event, published_reg, outsider_headers,
                                                           test_client):
    published_reg.registration_form.publish_checkin_enabled = True
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registrations/{published_reg.id}',
                           headers=outsider_headers)
    assert resp.status_code == 200
    assert resp.json['checked_in'] == published_reg.checked_in


def test_registration_without_consent_is_hidden(db, dummy_event, dummy_regform, dummy_reg, outsider_headers,
                                                test_client):
    dummy_regform.publish_registrations_public = PublishRegistrationsMode.show_with_consent
    dummy_reg.consent_to_publish = RegistrationVisibility.nobody
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registrations', headers=outsider_headers)
    assert resp.json['results'] == []
    dummy_reg.consent_to_publish = RegistrationVisibility.all
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registrations', headers=outsider_headers)
    assert [r['id'] for r in resp.json['results']] == [dummy_reg.id]


def test_registration_published_to_participants_only(db, dummy_event, dummy_regform, dummy_reg, create_registration,
                                                     outsider, outsider_headers, test_client):
    dummy_regform.publish_registrations_participants = PublishRegistrationsMode.show_all
    dummy_regform.publish_registrations_public = PublishRegistrationsMode.hide_all
    db.session.flush()
    url = f'/api/v1/events/{dummy_event.id}/registrations'
    assert test_client.get(url, headers=outsider_headers).json['results'] == []
    dummy_event.registrations.append(create_registration(outsider, dummy_regform))
    db.session.flush()
    assert {r['id'] for r in test_client.get(url, headers=outsider_headers).json['results']} == \
        {reg.id for reg in dummy_regform.registrations}


def test_manager_sees_every_registration(db, dummy_event, dummy_user, dummy_reg, token_headers, test_client):
    dummy_event.update_principal(dummy_user, full_access=True)
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registrations', headers=token_headers)
    assert resp.status_code == 200
    reg = resp.json['results'][0]
    assert reg['email'] == dummy_reg.email
    assert reg['checked_in'] == dummy_reg.checked_in
    assert reg['visibility'] == dummy_reg.visibility.name
    assert reg['tags'] == []


def test_registration_of_another_event_is_not_found(dummy_reg, create_event, token_headers, test_client):
    other = create_event()
    resp = test_client.get(f'/api/v1/events/{other.id}/registrations/{dummy_reg.id}', headers=token_headers)
    assert resp.status_code == 404
