# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest

from indico.core.db.sqlalchemy.protection import ProtectionMode


@pytest.fixture
def linked_reservation(db, dummy_reservation, dummy_event):
    dummy_reservation.occurrences[0].linked_object = dummy_event
    db.session.flush()
    return dummy_reservation


def test_reservation_link_list(linked_reservation, dummy_event, token_headers, test_client):
    occurrence = linked_reservation.occurrences[0]
    resp = test_client.get(f'/api/v1/reservations/{linked_reservation.id}/links', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['results'] == [{'id': occurrence.link.id, 'type': 'event', 'event_id': dummy_event.id,
                                     'contribution_id': None, 'session_block_id': None, 'title': dummy_event.title,
                                     'occurrence_start_dt': occurrence.start_dt.isoformat(),
                                     'occurrence_state': 'valid'}]


def test_reservation_without_links(dummy_reservation, token_headers, test_client):
    resp = test_client.get(f'/api/v1/reservations/{dummy_reservation.id}/links', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['results'] == []


def test_restricted_linked_object_keeps_its_title(db, linked_reservation, dummy_event, outsider_headers, test_client):
    dummy_event.protection_mode = ProtectionMode.protected
    db.session.flush()
    resp = test_client.get(f'/api/v1/reservations/{linked_reservation.id}/links', headers=outsider_headers)
    assert resp.status_code == 200
    assert [link['title'] for link in resp.json['results']] == [None]
    assert [link['event_id'] for link in resp.json['results']] == [dummy_event.id]


def test_links_of_an_unknown_booking_are_not_found(token_headers, test_client):
    assert test_client.get('/api/v1/reservations/123/links', headers=token_headers).status_code == 404


LINK_FIELDS = ('id', 'type')


def test_reservation_link_list_matches_current_api(linked_reservation, dummy_event, token_headers, test_client,
                                                   indico_api, same_json_list):
    current = indico_api(f'/rooms/api/bookings/{linked_reservation.id}/links')
    new = test_client.get(f'/api/v1/reservations/{linked_reservation.id}/links', headers=token_headers).json
    same_json_list(new['results'], current, same=LINK_FIELDS,
                   renamed={'occurrence_start_dt': 'start_dt', 'occurrence_state': 'state'},
                   # the current API nests the linked object itself, which carries its title but none of the ids
                   derived={'event_id': lambda _: dummy_event.id, 'contribution_id': lambda _: None,
                            'session_block_id': lambda _: None,
                            'title': lambda current: current['object']['title']})
