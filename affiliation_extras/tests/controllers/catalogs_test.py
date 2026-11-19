# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from operator import attrgetter

import pytest

from indico_affiliation_extras.models.catalogs import AffiliationCatalog
from indico_affiliation_extras.settings import category_settings, event_settings


pytest_plugins = 'indico.modules.events.registration.testing.fixtures'


def _login(test_client, user):
    with test_client.session_transaction() as sess:
        sess.set_session_user(user)


@pytest.mark.usefixtures('no_csrf_check')
class TestCatalogSave:
    def test_changes_affiliation_mode_and_logs_it(
        self, test_client, db, dummy_event, dummy_user, dummy_contact_affiliation, create_event_catalog
    ):
        dummy_event.update_principal(dummy_user, full_access=True)
        _login(test_client, dummy_user)
        saved_list = create_event_catalog(dummy_event, {dummy_contact_affiliation})
        url = f'/event/{dummy_event.id}/manage/affiliations/api/affiliations/catalogs/{saved_list.catalog_id}'
        payload = {
            'name': 'Catalog',
            'lists': [
                {
                    'id': saved_list.id,
                    'name': saved_list.name,
                    'position': saved_list.position,
                    'affiliations': [dummy_contact_affiliation.id],
                }
            ],
        }

        response = test_client.patch(url, json=payload)
        assert response.status_code == 200
        assert response.json['lists'][0]['affiliation_mode'] == 'predefined'

        payload['lists'][0]['affiliation_mode'] = 'custom'
        response = test_client.patch(url, json=payload)
        assert response.status_code == 200
        db.session.expire_all()
        assert saved_list.affiliation_mode.name == 'custom'
        entry = dummy_event.log_entries.filter_by(module='Affiliation Catalogs').one()
        assert 'Affiliation mode' in str(entry.data)
        assert 'predefined' in str(entry.data)
        assert 'custom' in str(entry.data)

    def test_free_text_list_save_edit_and_clone(self, test_client, dummy_event, dummy_user):
        dummy_event.update_principal(dummy_user, full_access=True)
        _login(test_client, dummy_user)
        url = f'/event/{dummy_event.id}/manage/affiliations/api/affiliations/catalogs'
        payload = {
            'name': 'Catalog',
            'lists': [{'name': 'Other organizations', 'position': 1, 'affiliation_mode': 'custom'}],
        }

        response = test_client.post(url, json=payload)

        assert response.status_code == 201
        catalog = response.json
        saved_list = catalog['lists'][0]
        assert saved_list['affiliation_mode'] == 'custom'
        assert saved_list['affiliations'] == []
        payload['lists'][0].update(id=saved_list['id'], name='Other')
        response = test_client.patch(f'{url}/{catalog["id"]}', json=payload)
        assert response.status_code == 200
        assert response.json['lists'][0]['affiliation_mode'] == 'custom'
        assert response.json['lists'][0]['name'] == 'Other'

        response = test_client.post(f'{url}/{catalog["id"]}/clone')

        assert response.status_code == 200
        assert response.json['lists'][0]['affiliation_mode'] == 'custom'
        assert response.json['lists'][0]['id'] != saved_list['id']
        assert response.json['lists'][0]['affiliations'] == []

    @pytest.mark.parametrize('mode', ('both', 'invalid'))
    def test_rejects_unsupported_affiliation_mode(self, test_client, dummy_event, dummy_user, mode):
        dummy_event.update_principal(dummy_user, full_access=True)
        _login(test_client, dummy_user)

        response = test_client.post(
            f'/event/{dummy_event.id}/manage/affiliations/api/affiliations/catalogs',
            json={'name': 'Catalog', 'lists': [{'name': 'Other', 'position': 1, 'affiliation_mode': mode}]},
        )

        assert response.status_code == 422
        assert 'affiliation_mode' in response.json['webargs_errors']['lists']['0']

    @pytest.mark.parametrize('case', ('empty-lists', 'empty-members', 'duplicate-names'))
    def test_rejected_edit_preserves_catalog(
        self,
        test_client,
        db,
        dummy_event,
        dummy_user,
        dummy_contact_affiliation,
        create_event_catalog,
        case,
    ):
        dummy_event.update_principal(dummy_user, full_access=True)
        _login(test_client, dummy_user)
        affiliation = dummy_contact_affiliation
        saved_list = create_event_catalog(dummy_event, {affiliation})
        catalog = saved_list.catalog
        list_data = {'name': 'Members', 'position': 0, 'affiliations': [affiliation.id]}
        if case == 'empty-lists':
            lists = []
        elif case == 'empty-members':
            lists = [{**list_data, 'affiliations': []}]
        else:
            lists = [list_data, {**list_data, 'name': 'members', 'position': 1}]

        resp = test_client.patch(
            f'/event/{dummy_event.id}/manage/affiliations/api/affiliations/catalogs/{catalog.id}',
            json={'name': 'Changed', 'lists': lists},
        )

        assert resp.status_code == 422
        assert 'lists' in resp.json['webargs_errors']
        db.session.expire_all()
        assert catalog.name == 'Catalog'
        assert list(catalog.lists) == [saved_list]
        assert saved_list.name == 'Representatives'
        assert saved_list.affiliations == {affiliation}


@pytest.mark.usefixtures('no_csrf_check')
@pytest.mark.parametrize('active', (False, True))
def test_catalog_deletion_checks_explicit_field_usage(
    test_client, db, dummy_regform, dummy_user, create_event_catalog, create_representation_field, active
):
    dummy_regform.event.update_principal(dummy_user, full_access=True)
    _login(test_client, dummy_user)
    selected = create_event_catalog(dummy_regform.event, [])
    field = create_representation_field(dummy_regform)
    field.data = {'catalog_id': selected.catalog_id}
    field.is_enabled = active
    db.session.flush()

    response = test_client.delete(
        f'/event/{dummy_regform.event.id}/manage/affiliations/api/affiliations/catalogs/{selected.catalog_id}'
    )

    assert response.status_code == (400 if active else 204)
    assert selected.catalog.is_deleted is not active


@pytest.mark.parametrize('state', ('active', 'disabled', 'deleted-field', 'deleted-form', 'deleted-event'))
def test_catalog_serialization_includes_usage(
    db, dummy_regform, create_event_catalog, create_representation_field, state
):
    from indico_affiliation_extras.schemas import AffiliationCatalogSchema

    selected = create_event_catalog(dummy_regform.event, [])
    unused = create_event_catalog(dummy_regform.event, [])
    field = create_representation_field(dummy_regform)
    field.data = {'catalog_id': selected.catalog_id}
    if state == 'disabled':
        field.is_enabled = False
    elif state == 'deleted-field':
        field.is_deleted = True
    elif state == 'deleted-form':
        dummy_regform.is_deleted = True
    elif state == 'deleted-event':
        dummy_regform.event.is_deleted = True
    db.session.flush()

    schema = AffiliationCatalogSchema()
    assert schema.dump(selected.catalog)['is_used_by_regform'] == (state == 'active')
    assert not schema.dump(unused.catalog)['is_used_by_regform']


@pytest.mark.usefixtures('no_csrf_check')
@pytest.mark.parametrize('target_type', ('event', 'category'))
@pytest.mark.parametrize('set_as_default', (None, False, True))
def test_create_catalog_set_as_default(
    test_client, dummy_event, dummy_category, dummy_user, target_type, set_as_default
):
    target, settings = (dummy_event, event_settings) if target_type == 'event' else (dummy_category, category_settings)
    target.update_principal(dummy_user, full_access=True)
    _login(test_client, dummy_user)
    payload = {
        'name': 'Catalog',
        'lists': [{'name': 'Other organizations', 'position': 1, 'affiliation_mode': 'custom'}],
    }
    if set_as_default is not None:
        payload['set_as_default'] = set_as_default

    response = test_client.post(
        f'/{target_type}/{target.id}/manage/affiliations/api/affiliations/catalogs', json=payload
    )

    assert response.status_code == 201
    expected = response.json['id'] if set_as_default else None
    assert settings.get(target, 'default_catalog_id') == expected
    entry = target.log_entries.filter_by(module='Affiliation Catalogs').one()
    assert ('Default catalog' in entry.data) == bool(set_as_default)


@pytest.mark.usefixtures('no_csrf_check')
@pytest.mark.parametrize('target_type', ('event', 'category'))
def test_toggle_default_catalog_logs_change(test_client, dummy_event, dummy_category, dummy_user, target_type):
    target = dummy_event if target_type == 'event' else dummy_category
    target.update_principal(dummy_user, full_access=True)
    _login(test_client, dummy_user)
    url = f'/{target_type}/{target.id}/manage/affiliations/api/affiliations/catalogs'
    response = test_client.post(
        url, json={'name': 'Catalog', 'lists': [{'name': 'Other', 'position': 1, 'affiliation_mode': 'custom'}]}
    )
    catalog_id = response.json['id']

    assert test_client.post(f'{url}/{catalog_id}/toggle-default').status_code == 200
    assert test_client.post(f'{url}/{catalog_id}/toggle-default').status_code == 200

    entries = target.log_entries.filter_by(module='Affiliation Catalogs').all()
    toggle_entries = [entry for entry in entries if entry.summary.startswith('Default affiliation catalog')]
    set_entry, unset_entry = sorted(toggle_entries, key=attrgetter('id'))
    assert set_entry.summary == 'Default affiliation catalog changed to "Catalog"'
    assert set_entry.data == {'Previous default': 'None', 'New default': 'Catalog'}
    assert unset_entry.summary == 'Default affiliation catalog removed'
    assert unset_entry.data == {'Previous default': 'Catalog', 'New default': 'None'}
    assert {set_entry.meta['affiliation_catalog_id'], unset_entry.meta['affiliation_catalog_id']} == {catalog_id}


@pytest.mark.usefixtures('no_csrf_check')
def test_unpin_default_catalog_logs_inherited_fallback(test_client, db, dummy_user, create_category, create_event):
    category = create_category(title='Parent')
    event = create_event(category=category)
    event.update_principal(dummy_user, full_access=True)
    inherited = AffiliationCatalog(name='Inherited', category=category)
    own = AffiliationCatalog(name='Own', event=event)
    db.session.add_all([inherited, own])
    db.session.flush()
    category_settings.set(category, 'default_catalog_id', inherited.id)
    _login(test_client, dummy_user)
    url = f'/event/{event.id}/manage/affiliations/api/affiliations/catalogs/{own.id}/toggle-default'

    assert test_client.post(url).json['default_catalog_id'] == own.id
    response = test_client.post(url)

    assert response.json['default_catalog_id'] == inherited.id
    entry = max(event.log_entries.filter_by(module='Affiliation Catalogs'), key=attrgetter('id'))
    assert entry.summary == 'Default affiliation catalog changed to "Inherited"'
    assert entry.data == {'Previous default': 'Own', 'New default': 'Inherited (inherited)'}


@pytest.mark.usefixtures('no_csrf_check')
def test_unpin_default_catalog_matching_inherited_logs_change(
    test_client, db, dummy_user, create_category, create_event
):
    category = create_category(title='Parent')
    event = create_event(category=category)
    event.update_principal(dummy_user, full_access=True)
    shared = AffiliationCatalog(name='Shared', category=category)
    db.session.add(shared)
    db.session.flush()
    event_settings.set(event, 'default_catalog_id', shared.id)
    category_settings.set(category, 'default_catalog_id', shared.id)
    _login(test_client, dummy_user)
    url = f'/event/{event.id}/manage/affiliations/api/affiliations/catalogs/{shared.id}/toggle-default'

    response = test_client.post(url)

    assert response.json == {'default_catalog_id': shared.id, 'explicit_default_catalog_id': None}
    entry = event.log_entries.filter_by(module='Affiliation Catalogs').one()
    assert entry.summary == 'Default affiliation catalog changed to "Shared"'
    assert entry.data == {'Previous default': 'Shared', 'New default': 'Shared (inherited)'}
