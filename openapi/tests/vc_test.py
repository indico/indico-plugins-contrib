# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest
from flask_pluginengine.util import get_state

from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.core.plugins import IndicoPlugin
from indico.modules.vc import VCPluginMixin
from indico.modules.vc.models.vc_rooms import VCRoom, VCRoomEventAssociation, VCRoomStatus


class _CatsVCPlugin(VCPluginMixin, IndicoPlugin):
    name = 'vc_cats'


@pytest.fixture(autouse=True)
def vc_plugin(app):
    plugin = _CatsVCPlugin.__new__(_CatsVCPlugin)
    plugins = get_state(app).plugins
    plugins[plugin.name] = plugin
    yield plugin
    del plugins[plugin.name]


@pytest.fixture
def create_vc_room(db, dummy_event, dummy_user):
    def _create(name='Cats room', type_='cats', link_object=None, show=True,
                status=VCRoomStatus.created, data=None):
        vc_room = VCRoom(name=name, type=type_, status=status, created_by_user=dummy_user,
                         data=data if data is not None else {'url': 'https://cats.test/1'})
        assoc = VCRoomEventAssociation(vc_room=vc_room, show=show, data={'password': 'meow'})
        assoc.link_object = link_object if link_object is not None else dummy_event
        db.session.add(assoc)
        db.session.flush()
        return assoc

    return _create


@pytest.fixture
def dummy_vc_room(create_vc_room):
    return create_vc_room()


@pytest.mark.usefixtures('event_manager')
def test_videoconference_room_details(dummy_event, dummy_vc_room, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/videoconference-rooms/{dummy_vc_room.id}',
                           headers=token_headers)
    assert resp.status_code == 200
    assert resp.json == {'id': dummy_vc_room.id, 'event_id': dummy_event.id,
                         'videoconference_room_id': dummy_vc_room.vc_room.id, 'type': 'cats', 'name': 'Cats room',
                         'status': 'created', 'link_type': 'event', 'contribution_id': None,
                         'session_block_id': None, 'show': True}


def test_videoconference_room_list_is_sorted_by_name(dummy_event, create_vc_room, token_headers, test_client):
    create_vc_room(name='Zebra room')
    create_vc_room(name='Ant room')
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/videoconference-rooms', headers=token_headers)
    assert resp.status_code == 200
    assert [room['name'] for room in resp.json['results']] == ['Ant room', 'Zebra room']


def test_videoconference_room_linked_to_a_contribution(dummy_event, dummy_contribution, create_vc_room,
                                                       token_headers, test_client):
    assoc = create_vc_room(link_object=dummy_contribution)
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/videoconference-rooms/{assoc.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['link_type'] == 'contribution'
    assert resp.json['contribution_id'] == dummy_contribution.id
    assert resp.json['session_block_id'] is None


def test_one_room_attached_twice_is_served_once_per_link(db, dummy_event, dummy_contribution, dummy_vc_room,
                                                        token_headers, test_client):
    second = VCRoomEventAssociation(vc_room=dummy_vc_room.vc_room, show=True, data={})
    second.link_object = dummy_contribution
    db.session.add(second)
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/videoconference-rooms', headers=token_headers)
    assert resp.status_code == 200
    assert sorted(room['id'] for room in resp.json['results']) == sorted([dummy_vc_room.id, second.id])
    assert {room['videoconference_room_id'] for room in resp.json['results']} == {dummy_vc_room.vc_room.id}


def test_hidden_rooms_are_manager_only(dummy_event, create_vc_room, token_headers, test_client):
    assoc = create_vc_room(show=False)
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/videoconference-rooms', headers=token_headers)
    assert resp.json['results'] == []
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/videoconference-rooms/{assoc.id}', headers=token_headers)
    assert resp.status_code == 404


@pytest.mark.usefixtures('event_manager')
def test_managers_see_hidden_rooms(dummy_event, create_vc_room, token_headers, test_client):
    assoc = create_vc_room(show=False)
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/videoconference-rooms', headers=token_headers)
    assert [room['id'] for room in resp.json['results']] == [assoc.id]
    assert resp.json['results'][0]['show'] is False
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/videoconference-rooms/{assoc.id}', headers=token_headers)
    assert resp.status_code == 200


def test_deleted_rooms_are_manager_only(dummy_event, create_vc_room, token_headers, test_client):
    assoc = create_vc_room(status=VCRoomStatus.deleted)
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/videoconference-rooms', headers=token_headers)
    assert resp.json['results'] == []
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/videoconference-rooms/{assoc.id}', headers=token_headers)
    assert resp.status_code == 404


@pytest.mark.usefixtures('event_manager')
def test_managers_see_deleted_rooms(dummy_event, create_vc_room, token_headers, test_client):
    assoc = create_vc_room(status=VCRoomStatus.deleted)
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/videoconference-rooms/{assoc.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['status'] == 'deleted'


@pytest.mark.usefixtures('event_manager')
def test_rooms_of_an_uninstalled_plugin_are_not_served(dummy_event, create_vc_room, token_headers, test_client):
    assoc = create_vc_room(type_='dogs')
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/videoconference-rooms', headers=token_headers)
    assert resp.json['results'] == []
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/videoconference-rooms/{assoc.id}', headers=token_headers)
    assert resp.status_code == 404


def test_videoconference_rooms_need_event_access(db, dummy_event, dummy_vc_room, outsider_headers, test_client):
    dummy_event.protection_mode = ProtectionMode.protected
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/videoconference-rooms', headers=outsider_headers)
    assert resp.status_code == 403
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/videoconference-rooms/{dummy_vc_room.id}',
                           headers=outsider_headers)
    assert resp.status_code == 403


def test_room_of_another_event_is_not_found(create_event, dummy_vc_room, token_headers, test_client):
    other = create_event()
    resp = test_client.get(f'/api/v1/events/{other.id}/videoconference-rooms/{dummy_vc_room.id}',
                           headers=token_headers)
    assert resp.status_code == 404


def test_the_provider_payload_is_never_served(dummy_event, dummy_vc_room, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/videoconference-rooms/{dummy_vc_room.id}',
                           headers=token_headers)
    assert 'data' not in resp.json
    assert 'meow' not in resp.get_data(as_text=True)
