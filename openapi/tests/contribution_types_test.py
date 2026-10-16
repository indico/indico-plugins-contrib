# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 Unconventional
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest

from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.modules.events.contributions.models.types import ContributionType


@pytest.fixture
def create_contribution_type(db, dummy_event):
    def _create(name, **kwargs):
        contrib_type = ContributionType(event=dummy_event, name=name, **kwargs)
        db.session.add(contrib_type)
        db.session.flush()
        return contrib_type

    return _create


@pytest.fixture
def poster_type(create_contribution_type):
    return create_contribution_type('Poster', description='Shown in the poster session.')


def test_contribution_type_details(dummy_event, poster_type, token_headers, test_client):
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contribution-types/{poster_type.id}', headers=token_headers
    )
    assert resp.status_code == 200
    assert resp.json == {
        'id': poster_type.id,
        'event_id': dummy_event.id,
        'name': 'Poster',
        'description': 'Shown in the poster session.',
        'is_private': False,
    }


def test_contribution_type_list_is_sorted_by_name(
    dummy_event, poster_type, create_contribution_type, token_headers, test_client
):
    talk = create_contribution_type('Talk', is_private=True)
    keynote = create_contribution_type('keynote')
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/contribution-types', headers=token_headers)
    assert resp.status_code == 200
    assert [t['id'] for t in resp.json['results']] == [keynote.id, poster_type.id, talk.id]
    assert [t['is_private'] for t in resp.json['results']] == [False, False, True]


def test_contribution_type_denied_without_event_access(db, dummy_event, poster_type, outsider_headers, test_client):
    dummy_event.protection_mode = ProtectionMode.protected
    db.session.flush()
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contribution-types/{poster_type.id}', headers=outsider_headers
    )
    assert resp.status_code == 403
    assert 'error' in resp.json
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/contribution-types', headers=outsider_headers)
    assert resp.status_code == 403


def test_contribution_type_of_another_event_is_not_found(db, poster_type, create_event, token_headers, test_client):
    other = create_event()
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{other.id}/contribution-types/{poster_type.id}', headers=token_headers)
    assert resp.status_code == 404


def test_contribution_type_matches_current_api(
    db, dummy_event, dummy_contribution, poster_type, token_headers, test_client, indico_api, same_json
):
    dummy_contribution.type = poster_type
    db.session.flush()
    current = indico_api(f'/event/{dummy_event.id}/contributions/{dummy_contribution.id}.json')['type']
    new = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contribution-types/{poster_type.id}', headers=token_headers
    ).json
    # the current API only names the type of a contribution; the rest of its definition is in an HTML dialog
    same_json({key: value for key, value in new.items() if key in ('id', 'name')}, current, same=('id', 'name'))
