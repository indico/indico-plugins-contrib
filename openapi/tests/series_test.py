# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from datetime import timedelta

import pytest

from indico.modules.events.models.series import EventSeries


@pytest.fixture
def create_series(db):
    def _create(events, **kwargs):
        series = EventSeries(events=events, **kwargs)
        db.session.add(series)
        db.session.flush()
        return series

    return _create


@pytest.mark.usefixtures('event_manager')
def test_event_series_details(dummy_event, create_series, token_headers, test_client):
    series = create_series([dummy_event], event_title_pattern='Workshop {n}')
    resp = test_client.get(f'/api/v1/event-series/{series.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json == {
        'id': series.id,
        'event_ids': [dummy_event.id],
        'show_sequence_in_title': True,
        'show_links': True,
        'event_title_pattern': 'Workshop {n}',
    }


@pytest.mark.usefixtures('event_manager')
def test_event_series_lists_its_events_in_order(
    db, dummy_event, create_event, create_series, token_headers, test_client
):
    later = create_event(
        1,
        start_dt=dummy_event.start_dt + timedelta(days=1),
        end_dt=dummy_event.end_dt + timedelta(days=1),
        creator_has_privileges=True,
    )
    earlier = create_event(
        2,
        start_dt=dummy_event.start_dt - timedelta(days=1),
        end_dt=dummy_event.end_dt - timedelta(days=1),
        creator_has_privileges=True,
    )
    series = create_series([later, dummy_event, earlier])
    db.session.expire(series)
    resp = test_client.get(f'/api/v1/event-series/{series.id}', headers=token_headers)
    assert resp.json['event_ids'] == [earlier.id, dummy_event.id, later.id]


@pytest.mark.usefixtures('event_manager')
def test_event_series_list_only_holds_series_the_caller_manages(
    dummy_event, create_event, create_series, token_headers, test_client
):
    mine = create_series([dummy_event])
    create_series([create_event(1)])
    resp = test_client.get('/api/v1/event-series', headers=token_headers)
    assert resp.status_code == 200
    assert [series['id'] for series in resp.json['results']] == [mine.id]


def test_event_series_needs_management_access(dummy_event, create_series, token_headers, test_client):
    series = create_series([dummy_event])
    resp = test_client.get(f'/api/v1/event-series/{series.id}', headers=token_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json


@pytest.mark.usefixtures('event_manager')
def test_a_series_holding_an_unmanaged_event_is_forbidden(
    dummy_event, create_event, create_series, token_headers, test_client
):
    series = create_series([dummy_event, create_event(1)])
    resp = test_client.get(f'/api/v1/event-series/{series.id}', headers=token_headers)
    assert resp.status_code == 403


@pytest.mark.usefixtures('event_manager')
def test_unknown_series_is_not_found(token_headers, test_client):
    resp = test_client.get('/api/v1/event-series/1337', headers=token_headers)
    assert resp.status_code == 404


SERIES_FIELDS = ('id', 'show_sequence_in_title', 'show_links', 'event_title_pattern')


def as_event_ids(current):
    return [event['id'] for event in current['events']]


@pytest.mark.usefixtures('event_manager')
def test_event_series_matches_current_api(
    dummy_event, create_event, create_series, token_headers, test_client, indico_api, same_json
):
    series = create_series([dummy_event], event_title_pattern='Workshop {n}')
    current = indico_api(f'/event-series/{series.id}')
    new = test_client.get(f'/api/v1/event-series/{series.id}', headers=token_headers).json
    same_json(new, current, same=SERIES_FIELDS, derived={'event_ids': as_event_ids})


@pytest.mark.usefixtures('event_manager')
def test_event_series_list_matches_current_api(
    dummy_event, create_event, create_series, token_headers, test_client, indico_api, same_json_list
):
    other = create_event(1, creator_has_privileges=True)
    create_series([dummy_event], event_title_pattern='Workshop {n}')
    create_series([other], show_links=False)
    new = test_client.get('/api/v1/event-series', headers=token_headers).json['results']
    current = [indico_api(f'/event-series/{series["id"]}') for series in new]
    same_json_list(new, current, same=SERIES_FIELDS, derived={'event_ids': as_event_ids})
