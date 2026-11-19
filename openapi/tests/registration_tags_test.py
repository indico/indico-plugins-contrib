# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 Unconventional
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest

from indico.modules.events.features.util import set_feature_enabled
from indico.modules.events.registration.models.tags import RegistrationTag


@pytest.fixture(autouse=True)
def registration_enabled(db, dummy_event):
    set_feature_enabled(dummy_event, 'registration', True)
    db.session.flush()


@pytest.fixture
def create_registration_tag(db, dummy_event):
    def _create(title, color='blue', event=None):
        tag = RegistrationTag(title=title, color=color, event=(event or dummy_event))
        db.session.add(tag)
        db.session.flush()
        return tag

    return _create


@pytest.fixture
def dummy_registration_tag(create_registration_tag):
    return create_registration_tag('VIP')


@pytest.mark.usefixtures('event_manager')
def test_registration_tag_details(dummy_event, dummy_registration_tag, token_headers, test_client):
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/registration-tags/{dummy_registration_tag.id}', headers=token_headers
    )
    assert resp.status_code == 200
    assert resp.json == {'id': dummy_registration_tag.id, 'title': 'VIP', 'color': 'blue'}


@pytest.mark.usefixtures('event_manager')
def test_registration_tag_list_is_sorted_by_title(
    dummy_event, dummy_registration_tag, create_registration_tag, token_headers, test_client
):
    other = create_registration_tag('Catering')
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registration-tags', headers=token_headers)
    assert resp.status_code == 200
    assert [tag['id'] for tag in resp.json['results']] == [other.id, dummy_registration_tag.id]


def test_registration_tags_are_manager_only(dummy_event, dummy_registration_tag, outsider_headers, test_client):
    # the tags of a registration are only served to the organisers, and so is the catalogue they come from
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registration-tags', headers=outsider_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json
    assert (
        test_client.get(
            f'/api/v1/events/{dummy_event.id}/registration-tags/{dummy_registration_tag.id}', headers=outsider_headers
        ).status_code
        == 403
    )


@pytest.mark.usefixtures('event_manager')
def test_registration_tag_of_another_event_is_not_found(
    dummy_event, dummy_registration_tag, create_event, create_registration_tag, token_headers, test_client
):
    other = create_event()
    tag = create_registration_tag('Speaker', event=other)
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registration-tags/{tag.id}', headers=token_headers)
    assert resp.status_code == 404


TAG_FIELDS = ('id', 'title', 'color')


@pytest.mark.usefixtures('event_manager')
def test_registration_tag_list_matches_current_api(
    dummy_event, dummy_registration_tag, create_registration_tag, token_headers, test_client, indico_api, same_json_list
):
    create_registration_tag('Catering')
    current = indico_api(f'/api/checkin/event/{dummy_event.id}/')['registration_tags']
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/registration-tags', headers=token_headers).json
    same_json_list(new['results'], current, same=TAG_FIELDS)
