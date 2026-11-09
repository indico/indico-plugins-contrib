# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest


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
