# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest

from indico.modules.events.features.util import set_feature_enabled
from indico.modules.events.models.events import EventType


IMAGES_DESCRIPTION = (
    'Allows event managers to attach images to the event, which can then be used from HTML code. '
    'Very useful for e.g. sponsor logos and conference custom pages.'
)


def feature_named(results, name):
    return next(feature for feature in results if feature['name'] == name)


@pytest.mark.usefixtures('event_manager')
def test_feature_list(dummy_event, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/features', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['count'] == len(resp.json['results'])
    assert resp.json['next_offset'] is None
    assert [feature['title'] for feature in resp.json['results']] == [
        'Image manager',
        'Payment',
        'Registration',
        'Surveys',
    ]
    assert feature_named(resp.json['results'], 'images') == {
        'name': 'images',
        'title': 'Image manager',
        'description': IMAGES_DESCRIPTION,
        'enabled': False,
    }


@pytest.mark.usefixtures('event_manager')
def test_feature_list_skips_what_the_event_type_disallows(db, dummy_event, token_headers, test_client):
    dummy_event.type_ = EventType.conference
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/features', headers=token_headers)
    assert [feature['title'] for feature in resp.json['results']] == [
        'Call for Abstracts',
        'Editing',
        'Image manager',
        'Paper Peer Reviewing',
        'Payment',
        'Registration',
        'Surveys',
    ]


@pytest.mark.usefixtures('event_manager')
def test_feature_list_follows_the_toggles(dummy_event, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/features', headers=token_headers)
    assert feature_named(resp.json['results'], 'surveys')['enabled'] is True
    assert feature_named(resp.json['results'], 'images')['enabled'] is False
    set_feature_enabled(dummy_event, 'images', True)
    set_feature_enabled(dummy_event, 'surveys', False)
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/features', headers=token_headers)
    assert feature_named(resp.json['results'], 'images')['enabled'] is True
    assert feature_named(resp.json['results'], 'surveys')['enabled'] is False


def test_features_are_manager_only(dummy_event, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/features', headers=token_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json
