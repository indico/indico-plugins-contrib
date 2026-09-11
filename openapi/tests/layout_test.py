# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from io import BytesIO

import pytest

from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.modules.events.features.util import set_feature_enabled
from indico.modules.events.layout import layout_settings
from indico.modules.events.layout.models.images import ImageFile
from indico.modules.events.layout.models.menu import EventPage, MenuEntry, MenuEntryType
from indico.modules.events.layout.util import menu_entries_for_event
from indico.modules.users.models.users import NameFormat
from indico.testing.fixtures.event import DUMMY_BMP_IMAGE


DEFAULT_LAYOUT = {
    'theme': None,
    'css_url': None,
    'js_url': None,
    'logo_url': None,
    'announcement': None,
    'is_searchable': True,
    'show_nav_bar': True,
    'show_social_badges': True,
    'show_banner': False,
    'header_logo_as_banner': True,
    'header_text_color': '',
    'header_background_color': '',
    'name_format': None,
    'timetable_theme': 'standard',
    'timetable_theme_settings': {},
    'timetable_by_room': False,
    'timetable_detailed': False,
    'show_vc_rooms': False,
}


@pytest.fixture
def custom_menu(db, dummy_event):
    layout_settings.set(dummy_event, 'use_custom_menu', True)
    # Indico stores the default entries the first time the menu is read, and only then can they be customised
    menu_entries_for_event(dummy_event)

    def _add(**kwargs):
        entry = MenuEntry(event=dummy_event, **kwargs)
        db.session.add(entry)
        db.session.flush()
        return entry

    return _add


@pytest.fixture
def dummy_page(db, dummy_event, custom_menu):
    page = EventPage(event=dummy_event, html='<p>Where to find us</p>')
    custom_menu(type=MenuEntryType.page, page=page, title='Venue info')
    db.session.flush()
    return page


@pytest.fixture
def dummy_image(db, dummy_event):
    set_feature_enabled(dummy_event, 'images', True)
    image = ImageFile(event=dummy_event, filename='sponsor.bmp', content_type='image/bmp')
    image.save(BytesIO(DUMMY_BMP_IMAGE))
    db.session.add(image)
    db.session.flush()
    return image


def entry_named(results, title):
    return next(entry for entry in results if entry['title'] == title)


def test_layout_defaults(dummy_event, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/layout', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json == {'event_id': dummy_event.id, **DEFAULT_LAYOUT}


def test_layout_reflects_the_settings(dummy_event, token_headers, test_client):
    layout_settings.set_multi(dummy_event, {
        'is_searchable': False,
        'show_nav_bar': False,
        'show_social_badges': False,
        'show_banner': True,
        'header_logo_as_banner': False,
        'header_text_color': '#ffffff',
        'header_background_color': '#000000',
        'name_format': NameFormat.first_last,
        'timetable_theme': 'indico_weeks_view',
        'timetable_theme_settings': {'inline_minutes': True},
        'timetable_by_room': True,
        'timetable_detailed': True,
        'show_vc_rooms': True,
    })
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/layout', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json == {
        'event_id': dummy_event.id,
        'theme': None,
        'css_url': None,
        'js_url': None,
        'logo_url': None,
        'announcement': None,
        'is_searchable': False,
        'show_nav_bar': False,
        'show_social_badges': False,
        'show_banner': True,
        'header_logo_as_banner': False,
        'header_text_color': '#ffffff',
        'header_background_color': '#000000',
        'name_format': 'first_last',
        'timetable_theme': 'indico_weeks_view',
        'timetable_theme_settings': {'inline_minutes': True},
        'timetable_by_room': True,
        'timetable_detailed': True,
        'show_vc_rooms': True,
    }


def test_layout_serves_a_shown_announcement(dummy_event, token_headers, test_client):
    layout_settings.set_multi(dummy_event, {'announcement': 'Registration closes on Friday',
                                            'show_announcement': True})
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/layout', headers=token_headers)
    assert resp.json['announcement'] == 'Registration closes on Friday'


def test_layout_hides_an_unpublished_announcement(dummy_event, token_headers, test_client):
    layout_settings.set_multi(dummy_event, {'announcement': 'Not ready yet', 'show_announcement': False})
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/layout', headers=token_headers)
    assert resp.json['announcement'] is None


@pytest.mark.usefixtures('dummy_event_logo')
def test_layout_serves_the_logo_url(dummy_event, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/layout', headers=token_headers)
    assert resp.json['logo_url'] == f'/event/{dummy_event.id}/logo-{dummy_event.logo_metadata["hash"]}.png'


def test_layout_serves_the_stylesheet_url(db, dummy_event, token_headers, test_client):
    dummy_event.stylesheet = 'body { color: red; }'
    dummy_event.stylesheet_metadata = {'hash': 'abcdef', 'size': 20, 'filename': 'custom.css'}
    layout_settings.set(dummy_event, 'use_custom_css', True)
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/layout', headers=token_headers)
    assert resp.json['css_url'] == f'/event/{dummy_event.id}/abcdef.css'


def test_layout_serves_the_conference_theme(dummy_event, token_headers, test_client):
    layout_settings.set(dummy_event, 'theme', 'orange.css')
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/layout', headers=token_headers)
    assert resp.json['theme'] == 'orange.css'
    assert resp.json['css_url'].endswith('/orange.css')


def test_layout_needs_event_access(db, dummy_event, outsider_headers, test_client):
    dummy_event.protection_mode = ProtectionMode.protected
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/layout', headers=outsider_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json


def test_menu_lists_the_default_entries(dummy_event, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/menu', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['count'] == len(resp.json['results'])
    assert resp.json['next_offset'] is None
    timetable = next(entry for entry in resp.json['results'] if entry['name'] == 'timetable')
    assert timetable == {'name': 'timetable', 'title': 'Timetable', 'type': 'internal_link',
                         'position': timetable['position'], 'new_tab': False, 'page_id': None,
                         'url': f'/event/{dummy_event.id}/timetable/', 'children': []}


def test_menu_serves_a_custom_page_entry(dummy_event, dummy_page, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/menu', headers=token_headers)
    assert resp.status_code == 200
    entry = entry_named(resp.json['results'], 'Venue info')
    assert entry['name'] is None
    assert entry['type'] == 'page'
    assert entry['page_id'] == dummy_page.id
    assert entry['url'] == f'/event/{dummy_event.id}/page/{dummy_page.id}-venue-info'


def test_menu_serves_a_user_link(dummy_event, custom_menu, token_headers, test_client):
    custom_menu(type=MenuEntryType.user_link, title='Our sponsor', link_url='https://example.com/sponsor',
                new_tab=True)
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/menu', headers=token_headers)
    entry = entry_named(resp.json['results'], 'Our sponsor')
    assert entry['type'] == 'user_link'
    assert entry['url'] == 'https://example.com/sponsor'
    assert entry['new_tab'] is True


def test_menu_serves_a_separator(dummy_event, custom_menu, token_headers, test_client):
    custom_menu(type=MenuEntryType.separator)
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/menu', headers=token_headers)
    entry = next(entry for entry in resp.json['results'] if entry['type'] == 'separator')
    assert entry['title'] == ''
    assert entry['url'] is None


def test_menu_nests_the_children(db, dummy_event, custom_menu, token_headers, test_client):
    parent = custom_menu(type=MenuEntryType.user_link, title='Links', link_url='https://example.com')
    custom_menu(type=MenuEntryType.user_link, title='Sponsor', link_url='https://example.com/sponsor',
                parent_id=parent.id)
    db.session.expire(parent)
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/menu', headers=token_headers)
    entry = entry_named(resp.json['results'], 'Links')
    assert [child['title'] for child in entry['children']] == ['Sponsor']


def test_menu_hides_disabled_entries(dummy_event, custom_menu, token_headers, test_client):
    custom_menu(type=MenuEntryType.user_link, title='Draft', link_url='https://example.com', is_enabled=False)
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/menu', headers=token_headers)
    assert not [entry for entry in resp.json['results'] if entry['title'] == 'Draft']


def test_menu_honours_the_entry_acl(db, dummy_event, dummy_user, custom_menu, token_headers, test_client):
    entry = custom_menu(type=MenuEntryType.user_link, title='Restricted', link_url='https://example.com',
                        protection_mode=ProtectionMode.protected)
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/menu', headers=token_headers)
    assert not [listed for listed in resp.json['results'] if listed['title'] == 'Restricted']
    entry.acl.add(dummy_user)
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/menu', headers=token_headers)
    assert entry_named(resp.json['results'], 'Restricted')['url'] == 'https://example.com'


def test_menu_needs_event_access(db, dummy_event, outsider_headers, test_client):
    dummy_event.protection_mode = ProtectionMode.protected
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/menu', headers=outsider_headers)
    assert resp.status_code == 403


def test_page_details(dummy_event, dummy_page, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/pages/{dummy_page.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json == {'id': dummy_page.id, 'event_id': dummy_event.id, 'title': 'Venue info',
                         'html': '<p>Where to find us</p>', 'is_default': False,
                         'url': f'http://localhost/event/{dummy_event.id}/page/{dummy_page.id}-venue-info'}


def test_page_list(dummy_event, dummy_page, custom_menu, token_headers, test_client):
    other = EventPage(event=dummy_event, html='<p>Programme</p>')
    custom_menu(type=MenuEntryType.page, page=other, title='Programme')
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/pages', headers=token_headers)
    assert resp.status_code == 200
    assert [page['id'] for page in resp.json['results']] == [dummy_page.id, other.id]


def test_default_page_is_flagged(db, dummy_event, dummy_page, token_headers, test_client):
    dummy_event.default_page = dummy_page
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/pages/{dummy_page.id}', headers=token_headers)
    assert resp.json['is_default'] is True


def test_page_of_a_restricted_entry_is_hidden(db, dummy_event, dummy_page, token_headers, test_client):
    dummy_page.menu_entry.protection_mode = ProtectionMode.protected
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/pages/{dummy_page.id}', headers=token_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/pages', headers=token_headers)
    assert resp.json['results'] == []


def test_page_of_another_event_is_not_found(dummy_page, create_event, token_headers, test_client):
    other = create_event()
    resp = test_client.get(f'/api/v1/events/{other.id}/pages/{dummy_page.id}', headers=token_headers)
    assert resp.status_code == 404


@pytest.mark.usefixtures('event_manager')
def test_image_details(dummy_event, dummy_image, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/images/{dummy_image.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json == {'id': dummy_image.id, 'event_id': dummy_event.id, 'filename': 'sponsor.bmp',
                         'content_type': 'image/bmp', 'size': len(DUMMY_BMP_IMAGE),
                         'created_dt': dummy_image.created_dt.isoformat(),
                         'download_url': f'http://localhost/event/{dummy_event.id}/images/'
                                         f'{dummy_image.id}-sponsor.bmp'}


@pytest.mark.usefixtures('event_manager')
def test_image_list(dummy_event, dummy_image, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/images', headers=token_headers)
    assert resp.status_code == 200
    assert [image['id'] for image in resp.json['results']] == [dummy_image.id]


def test_images_are_manager_only(dummy_event, dummy_image, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/images/{dummy_image.id}', headers=token_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/images', headers=token_headers)
    assert resp.status_code == 403


@pytest.mark.usefixtures('event_manager')
def test_images_need_the_feature(dummy_event, dummy_image, token_headers, test_client):
    set_feature_enabled(dummy_event, 'images', False)
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/images/{dummy_image.id}', headers=token_headers)
    assert resp.status_code == 404
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/images', headers=token_headers)
    assert resp.status_code == 404
