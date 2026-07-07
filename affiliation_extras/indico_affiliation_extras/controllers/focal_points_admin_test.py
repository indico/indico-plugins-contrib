# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from indico.modules.users.models.affiliations import Affiliation

from indico_affiliation_extras.models.focal_points import get_focal_points, set_focal_points


def _login(test_client, user):
    with test_client.session_transaction() as sess:
        sess.set_session_user(user)


def _url(affiliation):
    return f'/admin/plugins/affiliation_extras/affiliations/{affiliation.id}/focal-points'


def _create_affiliation(db):
    affiliation = Affiliation(name='CERN')
    db.session.add(affiliation)
    db.session.flush()
    return affiliation


def test_focal_points_get_denies_non_admin(test_client, db, create_user):
    affiliation = _create_affiliation(db)
    _login(test_client, create_user(123))
    resp = test_client.get(_url(affiliation))
    assert resp.status_code == 403


def test_focal_points_patch_denies_non_admin(test_client, db, create_user, no_csrf_check):
    affiliation = _create_affiliation(db)
    _login(test_client, create_user(123))
    resp = test_client.patch(_url(affiliation), json={'focal_points': []})
    assert resp.status_code == 403


def test_focal_points_patch_then_get_returns_users(test_client, db, create_user, no_csrf_check):
    affiliation = _create_affiliation(db)
    admin = create_user(1, admin=True)
    alice = create_user(2)
    bob = create_user(3)
    _login(test_client, admin)

    resp = test_client.patch(_url(affiliation), json={'focal_points': [alice.identifier, bob.identifier]})
    assert resp.status_code == 204
    assert get_focal_points(affiliation) == {alice, bob}

    resp = test_client.get(_url(affiliation))
    assert resp.status_code == 200
    assert set(resp.json) == {alice.identifier, bob.identifier}


def test_focal_points_patch_empty_list_clears(test_client, db, create_user, no_csrf_check):
    affiliation = _create_affiliation(db)
    admin = create_user(1, admin=True)
    alice = create_user(2)
    set_focal_points(affiliation, {alice})
    db.session.flush()
    _login(test_client, admin)

    resp = test_client.patch(_url(affiliation), json={'focal_points': []})
    assert resp.status_code == 204
    assert get_focal_points(affiliation) == set()

    resp = test_client.get(_url(affiliation))
    assert resp.status_code == 200
    assert resp.json == []
