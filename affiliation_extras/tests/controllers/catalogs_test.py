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
