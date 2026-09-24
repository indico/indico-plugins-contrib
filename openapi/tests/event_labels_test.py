# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 Unconventional
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest

from indico.modules.events.models.labels import EventLabel


@pytest.fixture
def create_event_label(db):
    def _create(title, color='red', is_event_not_happening=False):
        label = EventLabel(title=title, color=color, is_event_not_happening=is_event_not_happening)
        db.session.add(label)
        db.session.flush()
        return label

    return _create


@pytest.fixture
def dummy_event_label(create_event_label):
    return create_event_label('Cancelled', is_event_not_happening=True)


def test_event_label_details(dummy_event_label, token_headers, test_client):
    resp = test_client.get(f'/api/v1/event-labels/{dummy_event_label.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json == {
        'id': dummy_event_label.id,
        'title': 'Cancelled',
        'color': 'red',
        'is_event_not_happening': True,
    }


def test_event_label_list_is_sorted_by_title(dummy_event_label, create_event_label, token_headers, test_client):
    other = create_event_label('Postponed', color='orange')
    resp = test_client.get('/api/v1/event-labels', headers=token_headers)
    assert resp.status_code == 200
    assert [label['id'] for label in resp.json['results']] == [dummy_event_label.id, other.id]


def test_event_labels_are_served_to_any_caller(dummy_event_label, outsider_headers, test_client):
    # a label is published on the page of every event carrying it
    assert test_client.get('/api/v1/event-labels', headers=outsider_headers).json['count'] == 1
    assert test_client.get(f'/api/v1/event-labels/{dummy_event_label.id}', headers=outsider_headers).status_code == 200


def test_event_label_matches_the_one_carried_by_an_event(
    db, dummy_event, dummy_event_label, token_headers, test_client
):
    dummy_event.label = dummy_event_label
    dummy_event.label_message = 'The event was called off'
    db.session.flush()
    listed = test_client.get('/api/v1/event-labels', headers=token_headers).json['results'][0]
    carried = test_client.get(f'/api/v1/events/{dummy_event.id}', headers=token_headers).json['label']
    assert carried == {**listed, 'message': 'The event was called off'}
