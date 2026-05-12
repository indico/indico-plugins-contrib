# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest
from sqlalchemy.exc import IntegrityError

from indico.modules.users.models.affiliations import Affiliation

from indico_affiliation_extras.models.catalogs import AffiliationCatalog
from indico_affiliation_extras.models.lists import AffiliationList
from indico_affiliation_extras.settings import event_settings


def _login(test_client, user):
    with test_client.session_transaction() as sess:
        sess.set_session_user(user)


def _create_affiliation(db, name='CERN'):
    affiliation = Affiliation(name=name)
    db.session.add(affiliation)
    db.session.flush()
    return affiliation


def _catalog_payload(affiliation_id, name='Catalog'):
    return {
        'name': name,
        'lists': [
            {
                'id': None,
                'name': 'List',
                'position': 1,
                'is_enabled': True,
                'groups': [],
                'tags': [],
                'affiliations': [affiliation_id],
            }
        ],
    }


def _create_catalog(db, affiliation, *, category=None, event=None, name='Catalog'):
    catalog = AffiliationCatalog(name=name, category=category, event=event)
    db.session.add(catalog)
    db.session.flush()
    list_obj = AffiliationList(catalog=catalog, name='List', position=1, is_enabled=True)
    list_obj.affiliations.add(affiliation)
    db.session.add(list_obj)
    db.session.flush()
    return catalog


def test_affiliation_catalog_requires_an_owner(db):
    db.session.add(AffiliationCatalog(name='Orphaned catalog'))
    with pytest.raises(IntegrityError):
        db.session.flush()
    db.session.rollback()


def test_affiliation_catalog_rejects_multiple_owners(db, create_category, create_event):
    category = create_category(title='Category')
    event = create_event(category=category)
    db.session.add(AffiliationCatalog(name='Ambiguous catalog', category=category, event=event))
    with pytest.raises(IntegrityError):
        db.session.flush()
    db.session.rollback()


def test_event_management_page_includes_own_and_inherited_catalogs(
    test_client, db, dummy_user, create_category, create_event
):
    parent = create_category(title='Parent')
    child = create_category(title='Child', parent=parent)
    child.update_principal(dummy_user, full_access=True)
    event = create_event(category=child)
    event.update_principal(dummy_user, full_access=True)
    affiliation = _create_affiliation(db)
    inherited_catalog = _create_catalog(db, affiliation, category=child, name='Inherited catalog')
    own_catalog = _create_catalog(db, affiliation, event=event, name='Own catalog')
    event_settings.set(event, 'default_catalog_id', own_catalog.id)
    _login(test_client, dummy_user)

    resp = test_client.get(f'/event/{event.id}/manage/affiliations/')

    assert resp.status_code == 200
    data = resp.get_data(as_text=True)
    assert 'affiliation-catalogs' in data
    assert inherited_catalog.name in data
    assert own_catalog.name in data


@pytest.mark.usefixtures('no_csrf_check')
def test_event_catalog_api_crud_clone_and_toggle_default(test_client, db, dummy_user, create_category, create_event):
    category = create_category(title='Category')
    category.update_principal(dummy_user, full_access=True)
    event = create_event(category=category)
    event.update_principal(dummy_user, full_access=True)
    affiliation = _create_affiliation(db)
    inherited_catalog = _create_catalog(db, affiliation, category=category, name='Inherited catalog')
    _login(test_client, dummy_user)

    create_resp = test_client.post(
        f'/event/{event.id}/manage/affiliations/api/affiliations/catalogs',
        json=_catalog_payload(affiliation.id, name='Event catalog'),
    )
    assert create_resp.status_code == 201
    created = create_resp.json
    created_id = created['id']
    assert created['owner']['locator']['event_id'] == event.id

    edit_resp = test_client.patch(
        f'/event/{event.id}/manage/affiliations/api/affiliations/catalogs/{created_id}',
        json=_catalog_payload(affiliation.id, name='Event catalog edited'),
    )
    assert edit_resp.status_code == 200
    assert edit_resp.json['name'] == 'Event catalog edited'

    clone_resp = test_client.post(
        f'/event/{event.id}/manage/affiliations/api/affiliations/catalogs/{inherited_catalog.id}/clone'
    )
    assert clone_resp.status_code == 200
    assert clone_resp.json['owner']['locator']['event_id'] == event.id
    clone_id = clone_resp.json['id']

    own_toggle_resp = test_client.post(
        f'/event/{event.id}/manage/affiliations/api/affiliations/catalogs/{created_id}/toggle-default'
    )
    assert own_toggle_resp.status_code == 200
    assert own_toggle_resp.json['default_catalog_id'] == created_id
    assert own_toggle_resp.json['explicit_default_catalog_id'] == created_id

    inherited_toggle_resp = test_client.post(
        f'/event/{event.id}/manage/affiliations/api/affiliations/catalogs/{inherited_catalog.id}/toggle-default'
    )
    assert inherited_toggle_resp.status_code == 200
    assert inherited_toggle_resp.json['default_catalog_id'] == inherited_catalog.id
    assert inherited_toggle_resp.json['explicit_default_catalog_id'] == inherited_catalog.id

    delete_resp = test_client.delete(f'/event/{event.id}/manage/affiliations/api/affiliations/catalogs/{created_id}')
    assert delete_resp.status_code == 204
    event_log_entries = event.log_entries.filter_by(module='Affiliation Catalogs').all()
    assert len(event_log_entries) == 4
    assert {entry.meta.get('affiliation_catalog_id') for entry in event_log_entries} == {created_id, clone_id}


@pytest.mark.usefixtures('no_csrf_check')
def test_event_catalog_api_forbids_cross_scope_catalog(test_client, db, dummy_user, create_category, create_event):
    category = create_category(title='Category')
    category.update_principal(dummy_user, full_access=True)
    event = create_event(category=category)
    event.update_principal(dummy_user, full_access=True)
    other_event = create_event(category=category)
    affiliation = _create_affiliation(db)
    foreign_catalog = _create_catalog(db, affiliation, event=other_event, name='Foreign catalog')
    _login(test_client, dummy_user)

    resp = test_client.patch(
        f'/event/{event.id}/manage/affiliations/api/affiliations/catalogs/{foreign_catalog.id}',
        json=_catalog_payload(affiliation.id, name='Should fail'),
    )
    assert resp.status_code == 403


@pytest.mark.usefixtures('no_csrf_check')
def test_category_catalog_routes_still_work(test_client, db, dummy_user, create_category):
    category = create_category(title='Category')
    category.update_principal(dummy_user, full_access=True)
    affiliation = _create_affiliation(db)
    _login(test_client, dummy_user)

    create_resp = test_client.post(
        f'/category/{category.id}/manage/affiliations/api/affiliations/catalogs',
        json=_catalog_payload(affiliation.id, name='Category catalog'),
    )
    assert create_resp.status_code == 201
    assert create_resp.json['owner']['locator']['category_id'] == category.id
    category_log_entries = category.log_entries.filter_by(module='Affiliation Catalogs').all()
    assert len(category_log_entries) == 1
    assert category_log_entries[0].meta.get('affiliation_catalog_id') == create_resp.json['id']

    page_resp = test_client.get(f'/category/{category.id}/manage/affiliations/')
    assert page_resp.status_code == 200
