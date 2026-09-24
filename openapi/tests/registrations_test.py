# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 Unconventional
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from datetime import timedelta
from decimal import Decimal

import pytest

from indico.modules.events.features.util import set_feature_enabled
from indico.modules.events.registration import registration_settings
from indico.modules.events.registration.models.form_fields import RegistrationFormField
from indico.modules.events.registration.models.items import PersonalDataType, RegistrationFormSection
from indico.modules.events.registration.models.registrations import (
    PublishRegistrationsMode,
    RegistrationData,
    RegistrationState,
    RegistrationVisibility,
)
from indico.util.date_time import now_utc


CHOICE_IDS = ('10000000-0000-0000-0000-000000000000', '20000000-0000-0000-0000-000000000000')


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


def add_field(db, section, title, input_type, settings, **kwargs):
    field = RegistrationFormField(
        registration_form=section.registration_form, parent=section, title=title, input_type=input_type, **kwargs
    )
    field.data, field.versioned_data = field.field_impl.process_field_data(settings)
    db.session.add(field)
    db.session.flush()
    return field


def answer(db, registration, field, data):
    registration.data.append(RegistrationData(field_data=field.current_data, data=data))
    db.session.flush()


@pytest.fixture
def custom_section(db, dummy_regform):
    section = RegistrationFormSection(registration_form=dummy_regform, title='Preferences', description='Tell us more.')
    db.session.add(section)
    db.session.flush()
    return section


@pytest.fixture
def choice_field(db, custom_section):
    choices = [
        {'id': CHOICE_IDS[0], 'caption': 'Vegetarian', 'price': 5, 'places_limit': 0, 'is_enabled': True},
        {'id': CHOICE_IDS[1], 'caption': 'Anything', 'price': 0, 'places_limit': 10, 'is_enabled': True},
    ]
    return add_field(
        db,
        custom_section,
        'Diet',
        'single_choice',
        {'item_type': 'dropdown', 'with_extra_slots': False, 'default_item': CHOICE_IDS[1], 'choices': choices},
        description='Pick one.',
        is_required=True,
    )


@pytest.fixture
def checkbox_field(db, custom_section):
    return add_field(db, custom_section, 'Newsletter', 'checkbox', {'price': 0})


@pytest.fixture
def manager_field(db, dummy_regform):
    section = RegistrationFormSection(registration_form=dummy_regform, title='Internal', is_manager_only=True)
    db.session.add(section)
    db.session.flush()
    return add_field(db, section, 'Badge note', 'text', {})


@pytest.fixture
def answered_reg(db, dummy_regform, dummy_reg, choice_field, checkbox_field, manager_field):
    values = {
        'first_name': dummy_reg.first_name,
        'last_name': dummy_reg.last_name,
        'email': dummy_reg.email,
        'affiliation': {'id': None, 'text': 'ACME'},
    }
    for field in dummy_regform.active_fields:
        if field.personal_data_type:
            answer(db, dummy_reg, field, values.get(field.personal_data_type.name, field.field_impl.default_value))
    answer(db, dummy_reg, choice_field, {CHOICE_IDS[0]: 1})
    answer(db, dummy_reg, checkbox_field, True)
    answer(db, dummy_reg, manager_field, 'VIP')
    return dummy_reg


def field_named(fields, title):
    return next(field for field in fields if field['title'] == title)


def section_named(sections, title):
    return next(section for section in sections if section['title'] == title)


def test_registration_form_list(dummy_event, open_regform, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registration-forms', headers=token_headers)
    assert resp.status_code == 200
    form = resp.json['results'][0]
    assert form['id'] == open_regform.id
    assert form['event_id'] == dummy_event.id
    assert form['title'] == open_regform.title
    assert form['is_open']


def test_registration_form_details(dummy_event, open_regform, token_headers, test_client):
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/registration-forms/{open_regform.id}', headers=token_headers
    )
    assert resp.status_code == 200
    assert resp.json['id'] == open_regform.id
    assert resp.json['title'] == open_regform.title
    assert resp.json['introduction'] == open_regform.introduction


def test_registration_form_hidden_until_scheduled(dummy_event, dummy_regform, outsider_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registration-forms', headers=outsider_headers)
    assert resp.status_code == 200
    assert resp.json['results'] == []
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/registration-forms/{dummy_regform.id}', headers=outsider_headers
    )
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


def test_published_registration_shows_checkin_when_enabled(
    db, dummy_event, published_reg, outsider_headers, test_client
):
    published_reg.registration_form.publish_checkin_enabled = True
    db.session.flush()
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/registrations/{published_reg.id}', headers=outsider_headers
    )
    assert resp.status_code == 200
    assert resp.json['checked_in'] == published_reg.checked_in


def test_registration_without_consent_is_hidden(
    db, dummy_event, dummy_regform, dummy_reg, outsider_headers, test_client
):
    dummy_regform.publish_registrations_public = PublishRegistrationsMode.show_with_consent
    dummy_reg.consent_to_publish = RegistrationVisibility.nobody
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registrations', headers=outsider_headers)
    assert resp.json['results'] == []
    dummy_reg.consent_to_publish = RegistrationVisibility.all
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registrations', headers=outsider_headers)
    assert [r['id'] for r in resp.json['results']] == [dummy_reg.id]


def test_registration_published_to_participants_only(
    db, dummy_event, dummy_regform, dummy_reg, create_registration, outsider, outsider_headers, test_client
):
    dummy_regform.publish_registrations_participants = PublishRegistrationsMode.show_all
    dummy_regform.publish_registrations_public = PublishRegistrationsMode.hide_all
    db.session.flush()
    url = f'/api/v1/events/{dummy_event.id}/registrations'
    assert test_client.get(url, headers=outsider_headers).json['results'] == []
    dummy_event.registrations.append(create_registration(outsider, dummy_regform))
    db.session.flush()
    assert {r['id'] for r in test_client.get(url, headers=outsider_headers).json['results']} == {
        reg.id for reg in dummy_regform.registrations
    }


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


def test_registration_form_sections(
    dummy_event, open_regform, choice_field, checkbox_field, token_headers, test_client
):
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/registration-forms/{open_regform.id}/sections', headers=token_headers
    )
    assert resp.status_code == 200
    assert [section['title'] for section in resp.json['results']] == ['Personal Data', 'Preferences']
    personal = resp.json['results'][0]
    assert personal['is_personal_data']
    assert not personal['is_manager_only']
    assert personal['registration_form_id'] == open_regform.id
    first_name = field_named(personal['fields'], 'First Name')
    assert first_name['personal_data_type'] == 'first_name'
    assert first_name['input_type'] == 'text'
    assert first_name['is_required']
    assert first_name['section_id'] == personal['id']
    assert first_name['price'] is None
    assert first_name['choices'] is None
    preferences = resp.json['results'][1]
    assert preferences['description'] == 'Tell us more.'
    assert [field['title'] for field in preferences['fields']] == ['Diet', 'Newsletter']
    diet = preferences['fields'][0]
    assert diet == {
        'id': choice_field.id,
        'section_id': preferences['id'],
        'position': 1,
        'title': 'Diet',
        'description': 'Pick one.',
        'input_type': 'single_choice',
        'is_required': True,
        'personal_data_type': None,
        'price': None,
        'default_value': {CHOICE_IDS[1]: 1},
        'show_if_field_id': None,
        'show_if_values': None,
        'is_purged': False,
        'choices': [
            {'id': CHOICE_IDS[0], 'caption': 'Vegetarian', 'price': 5.0, 'places_limit': 0, 'is_enabled': True},
            {'id': CHOICE_IDS[1], 'caption': 'Anything', 'price': 0.0, 'places_limit': 10, 'is_enabled': True},
        ],
    }
    newsletter = preferences['fields'][1]
    assert newsletter['input_type'] == 'checkbox'
    assert newsletter['price'] == 0
    assert newsletter['default_value'] is False


def test_registration_form_section_details(
    dummy_event, open_regform, custom_section, choice_field, token_headers, test_client
):
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/registration-forms/{open_regform.id}/sections/{custom_section.id}',
        headers=token_headers,
    )
    assert resp.status_code == 200
    assert resp.json['id'] == custom_section.id
    assert [field['id'] for field in resp.json['fields']] == [choice_field.id]


def test_registration_form_sections_skip_disabled_items(
    db, dummy_event, open_regform, custom_section, choice_field, checkbox_field, token_headers, test_client
):
    checkbox_field.is_enabled = False
    other = RegistrationFormSection(registration_form=open_regform, title='Disabled', is_enabled=False)
    db.session.add(other)
    db.session.flush()
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/registration-forms/{open_regform.id}/sections', headers=token_headers
    )
    assert [section['title'] for section in resp.json['results']] == ['Personal Data', 'Preferences']
    assert [field['id'] for field in resp.json['results'][1]['fields']] == [choice_field.id]


def test_manager_only_sections_are_hidden(dummy_event, open_regform, manager_field, outsider_headers, test_client):
    url = f'/api/v1/events/{dummy_event.id}/registration-forms/{open_regform.id}/sections'
    assert [s['title'] for s in test_client.get(url, headers=outsider_headers).json['results']] == ['Personal Data']
    resp = test_client.get(f'{url}/{manager_field.parent.id}', headers=outsider_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json


@pytest.mark.usefixtures('registration_manager')
def test_manager_only_sections_are_served_to_managers(
    dummy_event, open_regform, manager_field, token_headers, test_client
):
    url = f'/api/v1/events/{dummy_event.id}/registration-forms/{open_regform.id}/sections'
    assert [s['title'] for s in test_client.get(url, headers=token_headers).json['results']] == [
        'Personal Data',
        'Internal',
    ]
    resp = test_client.get(f'{url}/{manager_field.parent.id}', headers=token_headers)
    assert resp.json['is_manager_only']
    assert [field['title'] for field in resp.json['fields']] == ['Badge note']


def test_registration_form_sections_follow_form_access(
    dummy_event, dummy_regform, custom_section, outsider_headers, test_client
):
    url = f'/api/v1/events/{dummy_event.id}/registration-forms/{dummy_regform.id}/sections'
    assert test_client.get(url, headers=outsider_headers).status_code == 403
    assert test_client.get(f'{url}/{custom_section.id}', headers=outsider_headers).status_code == 403


def test_section_of_another_form_is_not_found(
    dummy_event, open_regform, custom_section, create_regform, token_headers, test_client
):
    other = create_regform(dummy_event, 'Another form')
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/registration-forms/{other.id}/sections/{custom_section.id}',
        headers=token_headers,
    )
    assert resp.status_code == 404


def test_registration_details_carry_the_answers(
    dummy_event, answered_reg, choice_field, checkbox_field, token_headers, test_client
):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registrations/{answered_reg.id}', headers=token_headers)
    assert resp.status_code == 200
    assert [section['title'] for section in resp.json['sections']] == ['Personal Data', 'Preferences']
    personal = section_named(resp.json['sections'], 'Personal Data')
    assert field_named(personal['fields'], 'Email Address')['value'] == answered_reg.email
    affiliation = field_named(personal['fields'], 'Affiliation')
    assert affiliation['id'] == answered_reg.registration_form.get_personal_data_field_id(PersonalDataType.affiliation)
    assert affiliation['input_type'] == 'affiliation'
    assert affiliation['data'] == {'id': None, 'text': 'ACME'}
    assert affiliation['value'] == 'ACME'
    preferences = section_named(resp.json['sections'], 'Preferences')
    assert preferences['id'] == choice_field.parent.id
    diet, newsletter = preferences['fields']
    assert diet['id'] == choice_field.id
    assert diet['title'] == 'Diet'
    assert diet['input_type'] == 'single_choice'
    assert diet['data'] == {CHOICE_IDS[0]: 1}
    assert diet['value'] == 'Vegetarian'
    assert Decimal(diet['price']) == 5
    assert newsletter['data'] is True
    assert newsletter['value'] == 'Yes'
    assert Decimal(newsletter['price']) == 0


def test_registration_answers_follow_the_summary_page(
    db,
    dummy_event,
    answered_reg,
    choice_field,
    checkbox_field,
    manager_field,
    registration_manager,
    token_headers,
    test_client,
):
    checkbox_field.is_deleted = True
    db.session.flush()
    url = f'/api/v1/events/{dummy_event.id}/registrations/{answered_reg.id}'
    sections = test_client.get(url, headers=token_headers).json['sections']
    assert [section['title'] for section in sections] == ['Personal Data', 'Preferences', 'Internal']
    assert [f['title'] for f in section_named(sections, 'Preferences')['fields']] == ['Diet', 'Newsletter']
    assert section_named(sections, 'Internal')['fields'][0]['value'] == 'VIP'
    dummy_event.update_principal(answered_reg.user, permissions=set())
    db.session.flush()
    sections = test_client.get(url, headers=token_headers).json['sections']
    assert [section['title'] for section in sections] == ['Personal Data', 'Preferences']
    assert [f['title'] for f in section_named(sections, 'Preferences')['fields']] == ['Diet']


def test_registration_answers_skip_hidden_conditional_fields(
    db, dummy_event, answered_reg, choice_field, checkbox_field, token_headers, test_client
):
    checkbox_field.show_if_field = choice_field
    checkbox_field.show_if_values = [CHOICE_IDS[1]]
    db.session.flush()
    url = f'/api/v1/events/{dummy_event.id}/registrations/{answered_reg.id}'
    sections = test_client.get(url, headers=token_headers).json['sections']
    assert [f['title'] for f in section_named(sections, 'Preferences')['fields']] == ['Diet']


def test_registration_answers_leave_purged_values_out(
    db, dummy_event, answered_reg, checkbox_field, token_headers, test_client
):
    checkbox_field.is_purged = True
    db.session.flush()
    url = f'/api/v1/events/{dummy_event.id}/registrations/{answered_reg.id}'
    sections = test_client.get(url, headers=token_headers).json['sections']
    newsletter = field_named(section_named(sections, 'Preferences')['fields'], 'Newsletter')
    assert newsletter['data'] is None
    assert newsletter['value'] is None


def test_registration_list_has_no_answers(dummy_event, answered_reg, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registrations', headers=token_headers)
    assert 'sections' not in resp.json['results'][0]


def test_published_registration_follows_the_participant_list(
    db, dummy_event, dummy_regform, answered_reg, choice_field, outsider_headers, test_client
):
    dummy_regform.publish_registrations_public = PublishRegistrationsMode.show_all
    dummy_regform.publish_registrations_participants = PublishRegistrationsMode.show_all
    db.session.flush()
    url = f'/api/v1/events/{dummy_event.id}/registrations/{answered_reg.id}'
    reg = test_client.get(url, headers=outsider_headers).json
    assert reg['first_name'] == answered_reg.first_name
    assert reg['affiliation'] == 'ACME'
    assert 'email' not in reg
    assert [section['title'] for section in reg['sections']] == ['Personal Data']
    assert [f['title'] for f in reg['sections'][0]['fields']] == ['First Name', 'Last Name', 'Affiliation']
    registration_settings.set(dummy_event, 'merge_registration_forms', False)
    email_field_id = dummy_regform.get_personal_data_field_id(PersonalDataType.email)
    registration_settings.set_participant_list_columns(dummy_event, [email_field_id, choice_field.id], dummy_regform)
    reg = test_client.get(url, headers=outsider_headers).json
    assert reg['email'] == answered_reg.email
    assert 'first_name' not in reg
    assert 'full_name' not in reg
    assert 'affiliation' not in reg
    assert [section['title'] for section in reg['sections']] == ['Personal Data', 'Preferences']
    assert [f['title'] for f in section_named(reg['sections'], 'Personal Data')['fields']] == ['Email Address']
    assert section_named(reg['sections'], 'Preferences')['fields'][0]['value'] == 'Vegetarian'


REGFORM_FIELDS = ('id', 'event_id', 'title', 'introduction', 'start_dt', 'end_dt', 'is_open', 'registration_count')

REGISTRATION_FIELDS = (
    'id',
    'event_id',
    'full_name',
    'email',
    'state',
    'checked_in',
    'checked_in_dt',
    'is_paid',
    'currency',
    'formatted_price',
    'tags',
)

REGISTRATION_KEYS = {
    'registration_form_id': 'regform_id',
    'submitted_dt': 'registration_date',
    'price': ('price', float),
}

PERSONAL_KEYS = {'first_name': 'firstName', 'last_name': 'surname'}


def from_personal_data(name):
    return lambda current: current['personal_data'].get(PERSONAL_KEYS.get(name, name), '')


PERSONAL_DATA = {
    name: from_personal_data(name)
    for name in ('first_name', 'last_name', 'affiliation', 'title', 'address', 'phone', 'country', 'position')
}


@pytest.fixture
def merged_registrations(dummy_event, open_regform, indico_api):
    def _merge():
        legacy = {
            int(reg['registrant_id']): reg
            for reg in indico_api(f'/api/events/{dummy_event.id}/registrants')['registrants']
        }
        checkin = indico_api(f'/api/checkin/event/{dummy_event.id}/forms/{open_regform.id}/registrations/')
        return [{**legacy[reg['id']], **reg} for reg in checkin]

    return _merge


def test_registration_form_matches_current_api(
    dummy_event, open_regform, dummy_reg, registration_manager, token_headers, test_client, indico_api, same_json
):
    current = next(f for f in indico_api(f'/api/checkin/event/{dummy_event.id}/forms/') if f['id'] == open_regform.id)
    new = test_client.get(
        f'/api/v1/events/{dummy_event.id}/registration-forms/{open_regform.id}', headers=token_headers
    ).json
    same_json(new, current, same=REGFORM_FIELDS)


def test_registration_form_list_matches_current_api(
    dummy_event,
    open_regform,
    dummy_reg,
    create_regform,
    registration_manager,
    token_headers,
    test_client,
    indico_api,
    same_json_list,
):
    create_regform(dummy_event, 'Another form')
    current = indico_api(f'/api/checkin/event/{dummy_event.id}/forms/')
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/registration-forms', headers=token_headers).json['results']
    same_json_list(new, current, same=REGFORM_FIELDS)


def without_sections(registration):
    # the answers are compared by their own test below, against the same payload
    return {key: value for key, value in registration.items() if key != 'sections'}


def test_registration_matches_current_api(
    dummy_event, dummy_reg, merged_registrations, registration_manager, token_headers, test_client, same_json
):
    current = next(reg for reg in merged_registrations() if reg['id'] == dummy_reg.id)
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/registrations/{dummy_reg.id}', headers=token_headers).json
    same_json(
        without_sections(new), current, same=REGISTRATION_FIELDS, renamed=REGISTRATION_KEYS, derived=PERSONAL_DATA
    )


def test_registration_list_matches_current_api(
    dummy_event,
    open_regform,
    dummy_reg,
    create_registration,
    outsider,
    merged_registrations,
    registration_manager,
    token_headers,
    test_client,
    same_json_list,
):
    dummy_event.registrations.append(create_registration(outsider, open_regform))
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/registrations', headers=token_headers).json['results']
    same_json_list(
        new, merged_registrations(), same=REGISTRATION_FIELDS, renamed=REGISTRATION_KEYS, derived=PERSONAL_DATA
    )


def affiliation_text(value):
    # the check-in API flattens an affiliation to its text and calls the field a text field
    return value['text'] if isinstance(value, dict) and 'text' in value else value


SECTION_FIELDS = ('id', 'position', 'title', 'description')
FIELD_FIELDS = ('id', 'position', 'title', 'description')
FIELD_KEYS = {
    'input_type': ('input_type', lambda t: 'text' if t == 'affiliation' else t),
    'default_value': ('default_value', affiliation_text),
}
CHOICE_KEYS = {'placesLimit': 'places_limit', 'isEnabled': 'is_enabled'}
ANSWER_FIELDS = ('id', 'title')
ANSWER_KEYS = {'input_type': FIELD_KEYS['input_type'], 'data': ('data', affiliation_text)}

# the rest of the form definition, the rendered value of an answer and its price are only ever embedded in
# HTML pages, so there is no JSON to compare them against
DEFINITION_ONLY = {
    'is_required',
    'personal_data_type',
    'show_if_field_id',
    'show_if_values',
    'is_purged',
    'registration_form_id',
    'is_manager_only',
    'is_personal_data',
    'fields',
    'value',
    'price',
}


def comparable(item):
    return {key: value for key, value in item.items() if key not in DEFINITION_ONLY}


def as_choices(rename_keys):
    def _choices(current):
        # a country field lists the countries as choices, without an id, and those are not served
        if not any('id' in choice for choice in current.get('choices', [])):
            return None
        return [
            {key: choice[key] for key in ('id', 'caption', 'price', 'places_limit', 'is_enabled')}
            for choice in rename_keys(CHOICE_KEYS)(current['choices'])
        ]

    return _choices


def as_price(current):
    return current.get('price')


@pytest.fixture
def current_registration_data(dummy_event, open_regform, indico_api):
    def _get(registration):
        return indico_api(
            f'/api/checkin/event/{dummy_event.id}/forms/{open_regform.id}/registrations/{registration.id}'
        )['registration_data']

    return _get


def test_registration_form_sections_match_current_api(
    dummy_event,
    open_regform,
    answered_reg,
    manager_field,
    registration_manager,
    token_headers,
    test_client,
    current_registration_data,
    same_json_list,
    rename_keys,
):
    current = current_registration_data(answered_reg)
    new = test_client.get(
        f'/api/v1/events/{dummy_event.id}/registration-forms/{open_regform.id}/sections', headers=token_headers
    ).json['results']
    same_json_list([comparable(section) for section in new], current, same=SECTION_FIELDS)
    for section in new:
        their_section = next(s for s in current if s['id'] == section['id'])
        same_json_list(
            [{**comparable(field), 'price': field['price']} for field in section['fields']],
            their_section['fields'],
            same=FIELD_FIELDS,
            renamed=FIELD_KEYS,
            derived={
                'section_id': lambda cur, section=section: section['id'],
                'price': as_price,
                'choices': as_choices(rename_keys),
            },
        )


def test_registration_answers_match_current_api(
    dummy_event,
    answered_reg,
    manager_field,
    registration_manager,
    token_headers,
    test_client,
    current_registration_data,
    same_json_list,
):
    current = current_registration_data(answered_reg)
    new = test_client.get(
        f'/api/v1/events/{dummy_event.id}/registrations/{answered_reg.id}', headers=token_headers
    ).json['sections']
    for section in new:
        their_section = next(s for s in current if s['id'] == section['id'])
        assert section['title'] == their_section['title']
        same_json_list(
            [comparable(field) for field in section['fields']],
            their_section['fields'],
            same=ANSWER_FIELDS,
            renamed=ANSWER_KEYS,
        )
