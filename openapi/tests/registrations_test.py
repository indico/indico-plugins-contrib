# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from datetime import timedelta

import pytest

from indico.modules.events.features.util import set_feature_enabled
from indico.modules.events.registration.models.registrations import (
    PublishRegistrationsMode,
    RegistrationState,
    RegistrationVisibility,
)
from indico.util.date_time import now_utc


@pytest.fixture(autouse=True)
def registration_enabled(db, dummy_event):
    set_feature_enabled(dummy_event, 'registration', True)
    db.session.flush()


@pytest.fixture
def open_regform(db, dummy_regform):
    dummy_regform.start_dt = now_utc() - timedelta(days=1)
    dummy_regform.end_dt = now_utc() + timedelta(days=1)
    db.session.flush()
    return dummy_regform


@pytest.fixture
def registration_manager(db, dummy_event, dummy_user):
    dummy_event.update_principal(dummy_user, permissions={'registration'})
    db.session.flush()


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
    assert form['is_open']


def test_registration_form_details(dummy_event, open_regform, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registration-forms/{open_regform.id}',
                           headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == open_regform.id
    assert resp.json['title'] == open_regform.title
    assert resp.json['introduction'] == open_regform.introduction


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
    assert resp.json['registration_form_id'] == dummy_reg.registration_form_id
    assert resp.json['full_name'] == dummy_reg.display_full_name
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
    assert reg['full_name'] == published_reg.display_full_name
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
    assert reg['tags'] == []


def test_registration_of_another_event_is_not_found(dummy_reg, create_event, token_headers, test_client):
    other = create_event()
    resp = test_client.get(f'/api/v1/events/{other.id}/registrations/{dummy_reg.id}', headers=token_headers)
    assert resp.status_code == 404


def test_registrations_require_the_feature(db, dummy_event, dummy_regform, token_headers, test_client):
    set_feature_enabled(dummy_event, 'registration', False)
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registration-forms', headers=token_headers)
    assert resp.status_code == 404
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registrations', headers=token_headers)
    assert resp.status_code == 404


REGFORM_FIELDS = ('id', 'event_id', 'title', 'introduction', 'start_dt', 'end_dt', 'is_open',
                  'registration_count')

REGISTRATION_FIELDS = ('id', 'event_id', 'full_name', 'email', 'state', 'checked_in', 'checked_in_dt', 'is_paid',
                       'currency', 'formatted_price', 'tags')

REGISTRATION_KEYS = {'registration_form_id': 'regform_id', 'submitted_dt': 'registration_date',
                     'price': ('price', float)}

PERSONAL_KEYS = {'first_name': 'firstName', 'last_name': 'surname'}


def from_personal_data(name):
    return lambda current: current['personal_data'].get(PERSONAL_KEYS.get(name, name), '')


PERSONAL_DATA = {name: from_personal_data(name)
                 for name in ('first_name', 'last_name', 'affiliation', 'title', 'address', 'phone', 'country',
                              'position')}


@pytest.fixture
def merged_registrations(dummy_event, open_regform, indico_api):
    def _merge():
        legacy = {int(reg['registrant_id']): reg
                  for reg in indico_api(f'/api/events/{dummy_event.id}/registrants')['registrants']}
        checkin = indico_api(f'/api/checkin/event/{dummy_event.id}/forms/{open_regform.id}/registrations/')
        return [{**legacy[reg['id']], **reg} for reg in checkin]

    return _merge


def test_registration_form_matches_current_api(dummy_event, open_regform, dummy_reg, registration_manager,
                                               token_headers, test_client, indico_api, same_json):
    current = next(f for f in indico_api(f'/api/checkin/event/{dummy_event.id}/forms/') if f['id'] == open_regform.id)
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/registration-forms/{open_regform.id}',
                          headers=token_headers).json
    same_json(new, current, same=REGFORM_FIELDS)


def test_registration_form_list_matches_current_api(dummy_event, open_regform, dummy_reg, create_regform,
                                                    registration_manager, token_headers, test_client, indico_api,
                                                    same_json_list):
    create_regform(dummy_event, 'Another form')
    current = indico_api(f'/api/checkin/event/{dummy_event.id}/forms/')
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/registration-forms', headers=token_headers).json['results']
    same_json_list(new, current, same=REGFORM_FIELDS)


def test_registration_matches_current_api(dummy_event, dummy_reg, merged_registrations, registration_manager,
                                          token_headers, test_client, same_json):
    current = next(reg for reg in merged_registrations() if reg['id'] == dummy_reg.id)
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/registrations/{dummy_reg.id}', headers=token_headers).json
    same_json(new, current, same=REGISTRATION_FIELDS, renamed=REGISTRATION_KEYS, derived=PERSONAL_DATA)


def test_registration_list_matches_current_api(dummy_event, open_regform, dummy_reg, create_registration, outsider,
                                               merged_registrations, registration_manager, token_headers, test_client,
                                               same_json_list):
    dummy_event.registrations.append(create_registration(outsider, open_regform))
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/registrations', headers=token_headers).json['results']
    same_json_list(new, merged_registrations(), same=REGISTRATION_FIELDS, renamed=REGISTRATION_KEYS,
                   derived=PERSONAL_DATA)
