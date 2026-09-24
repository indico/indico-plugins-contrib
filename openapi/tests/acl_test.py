# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 Unconventional
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest

from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.modules.events.contributions import contribution_settings
from indico.modules.events.layout import layout_settings
from indico.modules.events.layout.models.menu import MenuEntry, MenuEntryType
from indico.modules.events.layout.util import menu_entries_for_event
from indico.modules.events.tracks.models.tracks import Track


@pytest.fixture
def event_acl(db, dummy_event, dummy_user, outsider, dummy_group):
    dummy_event.update_principal(dummy_user, full_access=True)
    dummy_event.update_principal(outsider, read_access=True)
    dummy_event.update_principal(dummy_group, add_permissions={'submit'})
    db.session.flush()


@pytest.fixture
def custom_menu(db, dummy_event):
    layout_settings.set(dummy_event, 'use_custom_menu', True)
    menu_entries_for_event(dummy_event)

    def _add(**kwargs):
        entry = MenuEntry(event=dummy_event, **kwargs)
        db.session.add(entry)
        db.session.flush()
        return entry

    return _add


def test_event_acl_lists_every_named_principal(
    dummy_event, event_acl, dummy_user, outsider, dummy_group, token_headers, test_client
):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/acl', headers=token_headers)
    assert resp.status_code == 200
    entries = {entry['identifier']: entry for entry in resp.json['results']}
    assert entries[f'User:{dummy_user.id}'] == {
        'type': 'user',
        'identifier': f'User:{dummy_user.id}',
        'name': dummy_user.name,
        'read_access': False,
        'full_access': True,
        'permissions': [],
    }
    assert entries[f'User:{outsider.id}']['read_access']
    group = entries[dummy_group.persistent_identifier]
    assert group['type'] == 'local_group'
    assert group['name'] == dummy_group.name
    assert group['permissions'] == ['submit']


def test_event_acl_needs_management(dummy_event, event_acl, outsider_headers, test_client):
    assert test_client.get(f'/api/v1/events/{dummy_event.id}/acl', headers=outsider_headers).status_code == 403


def test_acl_leaves_out_what_the_parent_grants(db, dummy_event, dummy_user, outsider, token_headers, test_client):
    dummy_event.update_principal(dummy_user, full_access=True)
    dummy_event.category.update_principal(outsider, full_access=True)
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/acl', headers=token_headers)
    assert [entry['identifier'] for entry in resp.json['results']] == [f'User:{dummy_user.id}']


def test_acl_leaves_out_permissions_the_object_does_not_define(db, dummy_event, dummy_user, token_headers, test_client):
    dummy_event.update_principal(dummy_user, full_access=True, add_permissions={'submit'})
    entry = next(iter(dummy_event.acl_entries))
    entry.permissions = [*entry.permissions, 'nonsense']
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/acl', headers=token_headers)
    assert resp.json['results'][0]['permissions'] == ['submit']


def test_category_acl(db, dummy_category, dummy_user, token_headers, test_client):
    dummy_category.update_principal(dummy_user, full_access=True)
    db.session.flush()
    resp = test_client.get(f'/api/v1/categories/{dummy_category.id}/acl', headers=token_headers)
    assert resp.status_code == 200
    assert [entry['identifier'] for entry in resp.json['results']] == [f'User:{dummy_user.id}']


def test_session_acl(db, dummy_event, dummy_session, outsider, event_manager, token_headers, test_client):
    dummy_session.update_principal(outsider, add_permissions={'coordinate'})
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/sessions/{dummy_session.id}/acl', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['results'] == [
        {
            'type': 'user',
            'identifier': f'User:{outsider.id}',
            'name': outsider.name,
            'read_access': False,
            'full_access': False,
            'permissions': ['coordinate'],
        }
    ]


def test_contribution_acl(db, dummy_event, dummy_contribution, outsider, event_manager, token_headers, test_client):
    dummy_contribution.update_principal(outsider, add_permissions={'submit'})
    db.session.flush()
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}/acl', headers=token_headers
    )
    assert resp.status_code == 200
    assert [entry['permissions'] for entry in resp.json['results']] == [['submit']]


def test_contribution_acl_needs_management(dummy_event, dummy_contribution, outsider_headers, test_client):
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}/acl', headers=outsider_headers
    )
    assert resp.status_code == 403


def test_contribution_acl_answers_its_manager_before_publication(
    db, dummy_event, dummy_contribution, dummy_user, token_headers, test_client
):
    contribution_settings.set(dummy_event, 'published', False)
    dummy_contribution.update_principal(dummy_user, full_access=True)
    db.session.flush()
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}/acl', headers=token_headers
    )
    assert resp.status_code == 200
    assert [entry['full_access'] for entry in resp.json['results']] == [True]


def test_track_acl(db, dummy_event, outsider, event_manager, token_headers, test_client):
    track = Track(event=dummy_event, title='Dummy track')
    db.session.add(track)
    track.update_principal(outsider, add_permissions={'convene'})
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/tracks/{track.id}/acl', headers=token_headers)
    assert resp.status_code == 200
    assert [entry['permissions'] for entry in resp.json['results']] == [['convene']]


def test_track_acl_needs_event_management(db, dummy_event, dummy_user, token_headers, test_client):
    track = Track(event=dummy_event, title='Dummy track')
    db.session.add(track)
    track.update_principal(dummy_user, add_permissions={'convene'})
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/tracks/{track.id}/acl', headers=token_headers)
    assert resp.status_code == 403


def test_room_acl(db, dummy_room, outsider, token_headers, test_client):
    dummy_room.update_principal(outsider, add_permissions={'book'})
    db.session.flush()
    resp = test_client.get(f'/api/v1/rooms/{dummy_room.id}/acl', headers=token_headers)
    assert resp.status_code == 200
    assert [entry['permissions'] for entry in resp.json['results']] == [['book']]


def test_room_acl_needs_management(dummy_room, outsider_headers, test_client):
    assert test_client.get(f'/api/v1/rooms/{dummy_room.id}/acl', headers=outsider_headers).status_code == 403


def test_location_acl(db, dummy_location, dummy_room, dummy_user, token_headers, test_client):
    dummy_location.update_principal(dummy_user, full_access=True)
    db.session.flush()
    resp = test_client.get(f'/api/v1/locations/{dummy_location.id}/acl', headers=token_headers)
    assert resp.status_code == 200
    assert [entry['full_access'] for entry in resp.json['results']] == [True]


def test_location_acl_needs_management(dummy_location, dummy_room, outsider_headers, test_client):
    assert test_client.get(f'/api/v1/locations/{dummy_location.id}/acl', headers=outsider_headers).status_code == 403


def test_attachment_acl_names_the_principals_without_permissions(
    db, dummy_event, dummy_attachment, outsider, event_manager, token_headers, test_client
):
    dummy_attachment.acl.add(outsider)
    db.session.flush()
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/attachments/{dummy_attachment.id}/acl', headers=token_headers
    )
    assert resp.status_code == 200
    assert resp.json['results'] == [{'type': 'user', 'identifier': f'User:{outsider.id}', 'name': outsider.name}]


def test_attachment_folder_acl(db, dummy_event, dummy_attachment, outsider, event_manager, token_headers, test_client):
    folder = dummy_attachment.folder
    folder.acl.add(outsider)
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/attachment-folders/{folder.id}/acl', headers=token_headers)
    assert resp.status_code == 200
    assert [entry['identifier'] for entry in resp.json['results']] == [f'User:{outsider.id}']


def test_attachment_acl_needs_management(dummy_event, dummy_attachment, outsider_headers, test_client):
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/attachments/{dummy_attachment.id}/acl', headers=outsider_headers
    )
    assert resp.status_code == 403


def test_attachment_of_another_event_is_not_found(
    dummy_attachment, create_event, event_manager, token_headers, test_client
):
    other = create_event()
    resp = test_client.get(f'/api/v1/events/{other.id}/attachments/{dummy_attachment.id}/acl', headers=token_headers)
    assert resp.status_code == 404


def test_menu_entry_acl(db, dummy_event, custom_menu, outsider, event_manager, token_headers, test_client):
    entry = custom_menu(
        type=MenuEntryType.user_link,
        title='Restricted',
        link_url='https://example.com',
        protection_mode=ProtectionMode.protected,
    )
    entry.acl.add(outsider)
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/menu/{entry.id}/acl', headers=token_headers)
    assert resp.status_code == 200
    assert [entry['identifier'] for entry in resp.json['results']] == [f'User:{outsider.id}']


def test_menu_entry_acl_needs_management(db, dummy_event, custom_menu, outsider_headers, test_client):
    entry = custom_menu(type=MenuEntryType.user_link, title='Restricted', link_url='https://example.com')
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/menu/{entry.id}/acl', headers=outsider_headers)
    assert resp.status_code == 403


def test_permissions_describe_what_an_entry_can_hold(token_headers, test_client):
    resp = test_client.get('/api/v1/permissions', headers=token_headers)
    assert resp.status_code == 200
    permissions = {(perm['object_type'], perm['name']): perm for perm in resp.json['results']}
    assert permissions[('event', 'submit')]['title'] == 'Submission'
    assert permissions[('event', 'submit')]['user_selectable']
    assert permissions[('category', 'create')]['description'] == 'Allows creating events in the category'
    assert permissions[('room', 'prebook')]['default']
    assert {'session', 'contribution', 'track', 'location'} <= {object_type for object_type, _ in permissions}


def test_permissions_need_a_caller(test_client):
    assert test_client.get('/api/v1/permissions').status_code == 403
