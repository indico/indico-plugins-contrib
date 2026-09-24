# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from datetime import timedelta

import pytest

from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.modules.events.models.references import EventReference, ReferenceType
from indico.modules.events.settings import event_contact_settings
from indico.util.date_time import now_utc


@pytest.fixture
def decorated_event(db, dummy_event, doi, create_label):
    plain = ReferenceType(name='Ticket')
    db.session.add(plain)
    dummy_event.references.append(EventReference(reference_type=doi, value='10.1000/xyz'))
    dummy_event.references.append(EventReference(reference_type=plain, value='42'))
    dummy_event.label = create_label('Cancelled')
    dummy_event.label.is_event_not_happening = True
    dummy_event.label_message = 'Moved to next year'
    event_contact_settings.set_multi(
        dummy_event,
        {'title': 'Organisers', 'emails': ['org@example.com'], 'phones': ['+41 22 767 6111', '+41 22 767 6112']},
    )
    db.session.flush()
    return dummy_event


def test_event_details(dummy_event, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_event.id
    assert resp.json['title'] == dummy_event.title
    assert resp.json['timezone'] == dummy_event.timezone


def test_event_details_carry_references_label_and_contact(decorated_event, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{decorated_event.id}', headers=token_headers)
    assert resp.json['references'] == [
        {'type': 'DOI', 'value': '10.1000/xyz', 'url': 'https://doi.org/10.1000/xyz', 'urn': 'doi:10.1000/xyz'},
        {'type': 'Ticket', 'value': '42', 'url': None, 'urn': None},
    ]
    assert resp.json['label'] == {
        'id': decorated_event.label.id,
        'title': 'Cancelled',
        'color': 'red',
        'is_event_not_happening': True,
        'message': 'Moved to next year',
    }
    assert resp.json['contact'] == {
        'title': 'Organisers',
        'emails': ['org@example.com'],
        'phones': ['+41 22 767 6111', '+41 22 767 6112'],
    }


def test_event_without_extras(dummy_event, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}', headers=token_headers)
    assert resp.json['references'] == []
    assert resp.json['label'] is None
    assert resp.json['contact'] == {'title': 'Contact', 'emails': [], 'phones': []}


def test_event_details_denied_without_access(dummy_event, dummy_personal_token, create_user, db, test_client):
    outsider = create_user(42)
    dummy_personal_token.user = outsider
    dummy_personal_token.scopes = ['read:everything']
    dummy_event.protection_mode = ProtectionMode.protected
    db.session.flush()
    headers = {'Authorization': f'Bearer {dummy_personal_token._plaintext_token}'}
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}', headers=headers)
    assert resp.status_code == 403
    assert 'error' in resp.json


def test_event_details_denied_without_scope(dummy_event, dummy_personal_token, test_client):
    dummy_personal_token.scopes = ['read:user']
    headers = {'Authorization': f'Bearer {dummy_personal_token._plaintext_token}'}
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}', headers=headers)
    assert resp.status_code == 403


def test_event_list(dummy_event, token_headers, test_client):
    resp = test_client.get('/api/v1/events', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['count'] == 1
    assert resp.json['next_offset'] is None
    assert resp.json['results'][0]['id'] == dummy_event.id


def test_event_list_hides_inaccessible_events(dummy_event, dummy_personal_token, create_user, db, test_client):
    outsider = create_user(42)
    dummy_personal_token.user = outsider
    dummy_personal_token.scopes = ['read:everything']
    dummy_event.protection_mode = ProtectionMode.protected
    db.session.flush()
    headers = {'Authorization': f'Bearer {dummy_personal_token._plaintext_token}'}
    resp = test_client.get('/api/v1/events', headers=headers)
    assert resp.status_code == 200
    assert resp.json['results'] == []


def test_event_list_paginates(create_event, token_headers, test_client):
    events = [create_event() for _ in range(3)]
    resp = test_client.get('/api/v1/events?limit=2', headers=token_headers)
    assert resp.json['count'] == 2
    assert resp.json['next_offset'] == 2
    resp = test_client.get('/api/v1/events?limit=2&offset=2', headers=token_headers)
    assert resp.json['count'] == 1
    assert resp.json['next_offset'] is None
    listed = {e['id'] for e in resp.json['results']}
    assert listed <= {e.id for e in events}


def test_event_list_filters_by_category(dummy_event, create_category, create_event, token_headers, test_client):
    other = create_event(category=create_category(1))
    resp = test_client.get(f'/api/v1/events?category_id={dummy_event.category_id}', headers=token_headers)
    listed = {e['id'] for e in resp.json['results']}
    assert dummy_event.id in listed
    assert other.id not in listed


EVENT_FIELDS = (
    'title',
    'description',
    'timezone',
    'type',
    'url',
    'location',
    'room',
    'address',
    'keywords',
    'organizer',
    'language',
    'references',
)


def without_label_id(label):
    # the legacy export names the label but does not carry its id
    return label and {key: value for key, value in label.items() if key != 'id'}


EVENT_KEYS = {
    'id': ('id', str),
    'category_id': ('categoryId', None),
    'category_title': ('category', None),
    'room_full_name': ('roomFullname', None),
    'is_protected': ('hasAnyProtection', None),
    'label': ('label', without_label_id),
}


def date_keys(as_legacy_date):
    return {
        'start_dt': ('startDate', as_legacy_date),
        'end_dt': ('endDate', as_legacy_date),
        'created_dt': ('creationDate', as_legacy_date),
    }


def as_category_chain(current):
    return [entry['title'] for entry in current['chain']]


def as_contact(current):
    info = current['supportInfo']
    return {
        'title': info['caption'],
        'emails': info['email'].split(', ') if info['email'] else [],
        'phones': info['telephone'].split(', ') if info['telephone'] else [],
    }


DERIVED = {'category_chain': as_category_chain, 'contact': as_contact}


def with_extras(indico_api, sessions):
    # the legacy export only carries the contact of an event next to its sessions
    def add(current):
        session = sessions[int(current['id'])]
        slots = indico_api(f'/export/event/{current["id"]}/session/{session.id}.json')['results']
        return {
            **current,
            'chain': indico_api(f'/category/{current["categoryId"]}/info')['category']['path'],
            'supportInfo': slots[0]['conference']['supportInfo'],
        }

    return add


def test_event_matches_current_api(
    decorated_event,
    dummy_session,
    dummy_session_block,
    token_headers,
    test_client,
    indico_api,
    as_legacy_date,
    same_json,
):
    add_extras = with_extras(indico_api, {decorated_event.id: dummy_session})
    current = add_extras(indico_api(f'/export/event/{decorated_event.id}.json')['results'][0])
    new = test_client.get(f'/api/v1/events/{decorated_event.id}', headers=token_headers).json
    same_json(new, current, same=EVENT_FIELDS, renamed={**EVENT_KEYS, **date_keys(as_legacy_date)}, derived=DERIVED)


def test_event_list_matches_current_api(
    decorated_event,
    dummy_session,
    dummy_session_block,
    create_event,
    create_session,
    create_session_block,
    token_headers,
    test_client,
    indico_api,
    as_legacy_date,
    same_json_list,
):
    other = create_event(title='Another event')
    other_session = create_session(other, 'Other session')
    create_session_block(other_session, 'Other block', timedelta(minutes=20), now_utc())
    add_extras = with_extras(indico_api, {decorated_event.id: dummy_session, other.id: other_session})
    ids = f'{decorated_event.id}-{other.id}'
    current = [add_extras(event) for event in indico_api(f'/export/event/{ids}.json')['results']]
    new = test_client.get('/api/v1/events', headers=token_headers).json['results']
    same_json_list(
        new, current, same=EVENT_FIELDS, renamed={**EVENT_KEYS, **date_keys(as_legacy_date)}, derived=DERIVED
    )
