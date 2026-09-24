# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from datetime import UTC, datetime

import pytest
from logs_test import LOG_FIELDS, log_keys

from indico.modules.logs.models.entries import CategoryLogEntry, CategoryLogRealm, LogKind


@pytest.fixture
def create_category_log_entry(db, dummy_category, dummy_user):
    def _create(summary, realm=CategoryLogRealm.category, logged_dt=None, **kwargs):
        entry = dummy_category.log(realm, LogKind.change, 'Test', summary, user=dummy_user, **kwargs)
        if logged_dt is not None:
            entry.logged_dt = logged_dt
        db.session.flush()
        return entry

    return _create


@pytest.fixture
def dummy_category_log_entry(create_category_log_entry):
    return create_category_log_entry(
        'Category settings changed',
        logged_dt=datetime(2026, 9, 1, 8, 0, tzinfo=UTC),
        data={'Title': ['Old title', 'New title', 'text']},
    )


@pytest.fixture
def category_manager(db, dummy_category, dummy_user):
    dummy_category.update_principal(dummy_user, full_access=True)
    # granting a permission is logged too, and that entry would show up in every list below
    CategoryLogEntry.query.delete()
    db.session.flush()


@pytest.mark.usefixtures('category_manager')
def test_category_log_entry_details(dummy_category, dummy_category_log_entry, dummy_user, token_headers, test_client):
    resp = test_client.get(
        f'/api/v1/categories/{dummy_category.id}/logs/{dummy_category_log_entry.id}', headers=token_headers
    )
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_category_log_entry.id
    assert resp.json['realm'] == 'category'
    assert resp.json['kind'] == 'change'
    assert resp.json['module'] == 'Test'
    assert resp.json['summary'] == 'Category settings changed'
    assert resp.json['logged_dt'] == '2026-09-01T08:00:00+00:00'
    assert resp.json['data'] == {'Title': ['Old title', 'New title', 'text']}
    assert resp.json['user']['full_name'] == dummy_user.full_name


@pytest.mark.usefixtures('category_manager')
def test_category_log_list_is_newest_first(dummy_category, create_category_log_entry, token_headers, test_client):
    older = create_category_log_entry('Older', logged_dt=datetime(2026, 9, 1, 8, 0, tzinfo=UTC))
    newer = create_category_log_entry('Newer', logged_dt=datetime(2026, 9, 2, 8, 0, tzinfo=UTC))
    resp = test_client.get(f'/api/v1/categories/{dummy_category.id}/logs', headers=token_headers)
    assert resp.status_code == 200
    assert [entry['id'] for entry in resp.json['results']] == [newer.id, older.id]


@pytest.mark.usefixtures('category_manager')
def test_category_log_list_filters_by_realm(
    dummy_category, dummy_category_log_entry, create_category_log_entry, token_headers, test_client
):
    entry = create_category_log_entry('Event created', realm=CategoryLogRealm.events)
    resp = test_client.get(f'/api/v1/categories/{dummy_category.id}/logs?realm=events', headers=token_headers)
    assert resp.status_code == 200
    assert [listed['id'] for listed in resp.json['results']] == [entry.id]


@pytest.mark.usefixtures('category_manager')
def test_category_log_list_filters_by_text(
    dummy_category, dummy_category_log_entry, create_category_log_entry, token_headers, test_client
):
    entry = create_category_log_entry('Event of Gudrun moved')
    resp = test_client.get(f'/api/v1/categories/{dummy_category.id}/logs?q=gudrun', headers=token_headers)
    assert resp.status_code == 200
    assert [listed['id'] for listed in resp.json['results']] == [entry.id]


def test_category_logs_are_manager_only(dummy_category, dummy_category_log_entry, outsider_headers, test_client):
    resp = test_client.get(
        f'/api/v1/categories/{dummy_category.id}/logs/{dummy_category_log_entry.id}', headers=outsider_headers
    )
    assert resp.status_code == 403
    assert 'error' in resp.json
    assert test_client.get(f'/api/v1/categories/{dummy_category.id}/logs', headers=outsider_headers).status_code == 403


@pytest.mark.usefixtures('category_manager')
def test_category_log_entry_of_another_category_is_not_found(
    dummy_category_log_entry, create_category, token_headers, test_client
):
    other = create_category(123)
    resp = test_client.get(f'/api/v1/categories/{other.id}/logs/{dummy_category_log_entry.id}', headers=token_headers)
    assert resp.status_code == 404


ALL_REALMS = '&'.join(f'filters={realm.name}' for realm in CategoryLogRealm)


@pytest.fixture
def current_entries(dummy_category, indico_api):
    def _fetch():
        return indico_api(f'/category/{dummy_category.id}/manage/logs/api/logs?{ALL_REALMS}')['entries']

    return _fetch


@pytest.mark.usefixtures('category_manager')
def test_category_log_list_matches_current_api(
    dummy_category,
    dummy_category_log_entry,
    create_category_log_entry,
    token_headers,
    test_client,
    current_entries,
    same_json_list,
):
    create_category_log_entry('Event created', realm=CategoryLogRealm.events)
    new = test_client.get(f'/api/v1/categories/{dummy_category.id}/logs', headers=token_headers).json['results']
    same_json_list(new, current_entries(), same=LOG_FIELDS, renamed=log_keys(dummy_category.tzinfo))
