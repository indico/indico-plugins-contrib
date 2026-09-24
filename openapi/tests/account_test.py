# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest

from indico.modules.users.models.export import DataExportOptions, DataExportRequest, DataExportRequestState


SETTING_FIELDS = {
    'lang',
    'force_language',
    'timezone',
    'force_timezone',
    'show_future_events',
    'show_past_events',
    'name_format',
    'use_previewer_pdf',
    'add_ical_alerts',
    'add_ical_alerts_mins',
    'use_markdown_for_minutes',
    'synced_fields',
    'suggest_categories',
    'mastodon_server_url',
    'mastodon_server_name',
}


@pytest.fixture
def export_request(db, dummy_user):
    request = DataExportRequest(
        user=dummy_user,
        state=DataExportRequestState.running,
        selected_options=[DataExportOptions.personal_data, DataExportOptions.registrations],
        include_files=True,
    )
    db.session.add(request)
    db.session.flush()
    return request


def test_settings_are_served_to_the_caller(token_headers, test_client):
    resp = test_client.get('/api/v1/users/me/settings', headers=token_headers)
    assert resp.status_code == 200
    assert set(resp.json) == SETTING_FIELDS
    assert resp.json['name_format'] == 'first_last'
    assert resp.json['synced_fields'] is None


def test_settings_follow_what_the_user_saved(db, dummy_user, token_headers, test_client):
    dummy_user.settings.set_multi({
        'timezone': 'Europe/Zurich',
        'force_timezone': True,
        'add_ical_alerts_mins': 30,
        'synced_fields': ['first_name'],
    })
    db.session.flush()
    resp = test_client.get('/api/v1/users/me/settings', headers=token_headers)
    assert resp.json['timezone'] == 'Europe/Zurich'
    assert resp.json['force_timezone'] is True
    assert resp.json['add_ical_alerts_mins'] == 30
    assert resp.json['synced_fields'] == ['first_name']


def test_emails_list_the_primary_one_first(db, dummy_user, token_headers, test_client):
    dummy_user.secondary_emails.add('other@example.test')
    db.session.flush()
    resp = test_client.get('/api/v1/users/me/emails', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['results'] == [
        {'email': dummy_user.email, 'is_primary': True},
        {'email': 'other@example.test', 'is_primary': False},
    ]


def test_data_export_request_is_served(export_request, token_headers, test_client):
    resp = test_client.get('/api/v1/users/me/data-export', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json == {
        'state': 'running',
        'requested_dt': export_request.requested_dt.isoformat(),
        'selected_options': ['personal_data', 'registrations'],
        'include_files': True,
        'max_size_exceeded': False,
        'url': None,
    }


def test_data_export_is_404_until_one_is_requested(dummy_user, token_headers, test_client):
    assert test_client.get('/api/v1/users/me/data-export', headers=token_headers).status_code == 404


def test_emails_answer_about_whoever_holds_the_token(outsider, outsider_headers, test_client):
    resp = test_client.get('/api/v1/users/me/emails', headers=outsider_headers)
    assert resp.json['results'] == [{'email': outsider.email, 'is_primary': True}]


@pytest.mark.parametrize(('path', 'status'), (('settings', 200), ('emails', 200), ('data-export', 404)))
def test_account_endpoints_never_answer_about_another_user(export_request, path, status, outsider_headers, test_client):
    # the seeded export belongs to the other user, and nothing here reaches it
    assert test_client.get(f'/api/v1/users/me/{path}', headers=outsider_headers).status_code == status
