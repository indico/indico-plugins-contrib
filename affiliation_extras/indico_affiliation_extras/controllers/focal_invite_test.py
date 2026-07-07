# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest

from indico.modules.events.registration.models.invitations import RegistrationInvitation
from indico.modules.users.models.affiliations import Affiliation

from indico_affiliation_extras.models.catalogs import AffiliationCatalog
from indico_affiliation_extras.models.lists import AffiliationList
from indico_affiliation_extras.settings import event_settings


pytest_plugins = 'indico.modules.events.registration.testing.fixtures'


def _login(test_client, user):
    with test_client.session_transaction() as sess:
        sess.set_session_user(user)


def _url(regform):
    return f'/admin/plugins/affiliation_extras/events/{regform.event.id}/regforms/{regform.id}/focal-points/invite'


def _affiliation_invite_url(regform):
    return f'/admin/plugins/affiliation_extras/events/{regform.event.id}/regforms/{regform.id}/invite'


def _metadata_url(regform):
    return f'{_url(regform)}/metadata'


def _add_event_catalog(db, event, affiliations):
    catalog = AffiliationCatalog(name='Catalog', event=event)
    db.session.add(catalog)
    db.session.flush()
    affiliation_list = AffiliationList(catalog=catalog, name='Representatives', position=1, is_enabled=True)
    affiliation_list.affiliations.update(affiliations)
    db.session.add(affiliation_list)
    db.session.flush()
    event_settings.set(event, 'default_catalog_id', catalog.id)


@pytest.mark.usefixtures('no_csrf_check')
def test_invite_focal_points_invites_catalog_focal_points(
    test_client,
    db,
    dummy_regform,
    dummy_user,
    create_user,
    monkeypatch,
):
    monkeypatch.setattr('indico.modules.events.registration.util.notify_invitation', lambda *args, **kwargs: None)
    dummy_regform.event.update_principal(dummy_user, full_access=True)
    _login(test_client, dummy_user)

    managed = Affiliation(name='CERN')
    other = Affiliation(name='MIT')
    db.session.add_all([managed, other])
    db.session.flush()
    _add_event_catalog(db, dummy_regform.event, {managed})

    focal = create_user(1, first_name='Alice', last_name='Focal', email='alice@example.test')
    outside = create_user(2, first_name='Bob', last_name='Other', email='bob@example.test')
    managed.focal_points.add(focal)
    other.focal_points.add(outside)
    db.session.flush()

    resp = test_client.post(
        _url(dummy_regform),
        json={
            'sender_address': dummy_user.email,
            'subject': 'Invitation',
            'body': 'Please register',
            'bcc_addresses': [],
            'copy_for_sender': False,
            'skip_moderation': False,
            'skip_access_check': False,
            'lock_email': False,
            'focal_points': {'count': 1},
        },
    )

    assert resp.status_code == 200
    assert resp.json['sent'] == 1
    assert resp.json['skipped'] == 0
    assert [inv.email for inv in dummy_regform.invitations] == ['alice@example.test']


@pytest.mark.usefixtures('no_csrf_check')
def test_invite_focal_points_returns_invitations_sorted_by_name(
    test_client,
    db,
    dummy_regform,
    dummy_user,
):
    dummy_regform.event.update_principal(dummy_user, full_access=True)
    _login(test_client, dummy_user)
    dummy_regform.invitations.extend((
        RegistrationInvitation(
            first_name='Alice',
            last_name='Zulu',
            email='alice.zulu@example.test',
            affiliation='CERN',
        ),
        RegistrationInvitation(
            first_name='Alice',
            last_name='Alpha',
            email='alice.alpha@example.test',
            affiliation='CERN',
        ),
    ))
    db.session.flush()

    resp = test_client.post(
        _url(dummy_regform),
        json={
            'sender_address': dummy_user.email,
            'subject': 'Invitation',
            'body': 'Please register',
            'bcc_addresses': [],
            'copy_for_sender': False,
            'skip_moderation': False,
            'skip_access_check': False,
            'lock_email': False,
            'focal_points': {'count': 0},
        },
    )

    assert resp.status_code == 200
    assert [invitation['email'] for invitation in resp.json['invitation_list']] == [
        'alice.alpha@example.test',
        'alice.zulu@example.test',
    ]


@pytest.mark.usefixtures('no_csrf_check')
def test_invite_by_affiliation_invites_affiliation_users(
    test_client,
    db,
    dummy_regform,
    dummy_user,
    create_user,
    monkeypatch,
):
    monkeypatch.setattr('indico.modules.events.registration.util.notify_invitation', lambda *args, **kwargs: None)
    dummy_regform.event.update_principal(dummy_user, full_access=True)
    _login(test_client, dummy_user)

    managed = Affiliation(name='CERN')
    other = Affiliation(name='MIT')
    db.session.add_all([managed, other])
    db.session.flush()

    invited = create_user(1, first_name='Alice', last_name='Managed', email='alice@example.test')
    outside = create_user(2, first_name='Bob', last_name='Other', email='bob@example.test')
    invited.affiliation_link = managed
    outside.affiliation_link = other
    db.session.flush()

    resp = test_client.post(
        _affiliation_invite_url(dummy_regform),
        json={
            'sender_address': dummy_user.email,
            'subject': 'Invitation',
            'body': 'Please register',
            'bcc_addresses': [],
            'copy_for_sender': False,
            'skip_moderation': False,
            'skip_access_check': False,
            'lock_email': False,
            'affiliations': {'affiliations': [{'id': managed.id}], 'groups': [], 'tags': []},
        },
    )

    assert resp.status_code == 200
    assert resp.json['sent'] == 1
    assert resp.json['skipped'] == 0
    assert [inv.email for inv in dummy_regform.invitations] == ['alice@example.test']


def test_focal_point_invite_metadata_counts_catalog_focal_points(
    test_client,
    db,
    dummy_regform,
    dummy_user,
    create_user,
):
    dummy_regform.event.update_principal(dummy_user, full_access=True)
    _login(test_client, dummy_user)

    managed = Affiliation(name='CERN')
    unmanaged = Affiliation(name='MIT')
    db.session.add_all([managed, unmanaged])
    db.session.flush()
    _add_event_catalog(db, dummy_regform.event, {managed})

    managed.focal_points.add(create_user(1))
    unmanaged.focal_points.add(create_user(2))
    db.session.flush()

    resp = test_client.get(_metadata_url(dummy_regform))

    assert resp.status_code == 200
    assert resp.json == {'affiliation_count': 1, 'focal_point_count': 1}
