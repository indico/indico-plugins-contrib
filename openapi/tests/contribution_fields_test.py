# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 Unconventional
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest

from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.modules.events.contributions.models.fields import ContributionField, ContributionFieldVisibility


@pytest.fixture
def create_contribution_field(db, dummy_event):
    def _create(title, field_type='text', field_data=None, **kwargs):
        field = ContributionField(
            event=dummy_event, title=title, field_type=field_type, field_data=field_data or {}, **kwargs
        )
        db.session.add(field)
        db.session.flush()
        return field

    return _create


@pytest.fixture
def summary_field(create_contribution_field):
    return create_contribution_field(
        'Summary',
        description='A few lines.',
        is_required=True,
        field_data={'max_length': 500, 'max_words': 0, 'multiline': True},
    )


@pytest.fixture
def internal_field(create_contribution_field):
    return create_contribution_field('Reviewer notes', visibility=ContributionFieldVisibility.managers_only)


@pytest.fixture
def retired_field(create_contribution_field):
    return create_contribution_field('Old question', is_active=False)


def test_contribution_field_details(dummy_event, summary_field, token_headers, test_client):
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contribution-fields/{summary_field.id}', headers=token_headers
    )
    assert resp.status_code == 200
    assert resp.json == {
        'id': summary_field.id,
        'event_id': dummy_event.id,
        'position': 1,
        'title': 'Summary',
        'description': 'A few lines.',
        'is_required': True,
        'is_active': True,
        'is_user_editable': True,
        'visibility': 'public',
        'field_type': 'text',
        'field_data': {'max_length': 500, 'max_words': 0, 'multiline': True},
    }


def test_contribution_field_list_follows_positions(
    dummy_event, summary_field, create_contribution_field, token_headers, test_client
):
    choice = create_contribution_field(
        'Format', field_type='single_choice', field_data={'display_type': 'select', 'options': []}
    )
    summary_field.position = 5
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/contribution-fields', headers=token_headers)
    assert resp.status_code == 200
    assert [f['id'] for f in resp.json['results']] == [choice.id, summary_field.id]


def test_restricted_contribution_fields_are_manager_only(
    dummy_event, summary_field, internal_field, retired_field, outsider_headers, test_client
):
    url = f'/api/v1/events/{dummy_event.id}/contribution-fields'
    resp = test_client.get(url, headers=outsider_headers)
    assert [f['id'] for f in resp.json['results']] == [summary_field.id]
    assert test_client.get(f'{url}/{internal_field.id}', headers=outsider_headers).status_code == 403
    assert test_client.get(f'{url}/{retired_field.id}', headers=outsider_headers).status_code == 403


@pytest.mark.usefixtures('event_manager')
def test_managers_see_every_contribution_field(
    dummy_event, summary_field, internal_field, retired_field, token_headers, test_client
):
    url = f'/api/v1/events/{dummy_event.id}/contribution-fields'
    resp = test_client.get(url, headers=token_headers)
    assert [f['id'] for f in resp.json['results']] == [summary_field.id, internal_field.id, retired_field.id]
    resp = test_client.get(f'{url}/{internal_field.id}', headers=token_headers)
    assert resp.json['visibility'] == 'managers_only'
    resp = test_client.get(f'{url}/{retired_field.id}', headers=token_headers)
    assert resp.json['is_active'] is False


def test_contribution_field_denied_without_event_access(db, dummy_event, summary_field, outsider_headers, test_client):
    dummy_event.protection_mode = ProtectionMode.protected
    db.session.flush()
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contribution-fields/{summary_field.id}', headers=outsider_headers
    )
    assert resp.status_code == 403
    assert 'error' in resp.json
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/contribution-fields', headers=outsider_headers)
    assert resp.status_code == 403


def test_contribution_field_of_another_event_is_not_found(db, summary_field, create_event, token_headers, test_client):
    other = create_event()
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{other.id}/contribution-fields/{summary_field.id}', headers=token_headers)
    assert resp.status_code == 404


FIELD_FIELDS = (
    'id',
    'position',
    'title',
    'description',
    'is_required',
    'is_active',
    'is_user_editable',
    'visibility',
    'field_type',
    'field_data',
)


@pytest.mark.usefixtures('event_manager')
def test_contribution_field_list_matches_current_api(
    dummy_event, summary_field, internal_field, retired_field, token_headers, test_client, indico_api, same_json_list
):
    current = indico_api(f'/event/{dummy_event.id}/manage/contributions/api/fields/')
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/contribution-fields', headers=token_headers).json
    same_json_list(new['results'], current, same=FIELD_FIELDS, derived={'event_id': lambda _: dummy_event.id})
