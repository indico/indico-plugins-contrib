# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from io import BytesIO

import pytest

from indico.modules.users.models.affiliations import Affiliation
from indico.testing.util import extract_emails

from indico_affiliation_extras.focal_points import get_focal_points, set_focal_points
from indico_affiliation_extras.models.contacts import AffiliationContactList


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


def test_email_image_upload_returns_url(test_client, db, create_user, no_csrf_check):
    admin = create_user(1, admin=True)
    _login(test_client, admin)

    resp = test_client.post(
        '/admin/plugins/affiliation_extras/representatives/email/image',
        data={'upload': (BytesIO(b'\x89PNG\r\n\x1a\n' + bytes(64)), 'logo.png')},
        content_type='multipart/form-data',
    )

    assert resp.status_code == 200
    assert resp.json['url']


class TestEmailRepresentatives:
    @pytest.mark.usefixtures('no_csrf_check')
    @pytest.mark.parametrize(('emails', 'inactive_emails', 'expected_recipients', 'skipped'), (
        (['disabled@example.com'], ['disabled@example.com'], set(), 1),
        (
            ['active@example.com', 'disabled@example.com'],
            ['disabled@example.com'],
            {'active@example.com'},
            0,
        ),
    ), ids=('all-disabled', 'mixed-active-disabled'))
    def test_send_excludes_disabled_addresses(
        self, test_client, db, create_user, smtp, emails, inactive_emails, expected_recipients, skipped
    ):
        admin = create_user(1, admin=True)
        _login(test_client, admin)
        affiliation = _create_affiliation(db)
        db.session.add(AffiliationContactList(
            affiliation=affiliation,
            name='Representatives',
            emails=emails,
            inactive_emails=inactive_emails,
        ))
        db.session.flush()

        resp = test_client.post(
            '/admin/plugins/affiliation_extras/representatives/email/send',
            json={
                'affiliation_ids': [affiliation.id],
                'sender_address': admin.email,
                'subject': 'Invitation',
                'body': 'Please register',
                'contact_lists': [],
            },
        )

        assert resp.status_code == 200
        mails = extract_emails(smtp, required=False)
        assert {mail['To'] for mail in mails} == expected_recipients
        assert len(mails) == len(expected_recipients)
        assert resp.json == {'count': len(expected_recipients), 'skipped': skipped}

    @pytest.mark.usefixtures('no_csrf_check')
    @pytest.mark.parametrize(('contact_lists', 'expected_recipients'), (
        ([], {'active@example.com', 'other@example.com'}),
        (['Representatives'], {'active@example.com'}),
    ), ids=('all-lists', 'selected-list'))
    def test_send_mixed_lists_counts_recipients_and_skipped_affiliations(
        self, test_client, db, create_user, smtp, contact_lists, expected_recipients
    ):
        admin = create_user(1, admin=True)
        _login(test_client, admin)
        mixed = _create_affiliation(db)
        disabled = _create_affiliation(db)
        empty = _create_affiliation(db)
        db.session.add_all([
            AffiliationContactList(
                affiliation=mixed,
                name='Representatives',
                emails=['active@example.com', 'disabled@example.com'],
                inactive_emails=['disabled@example.com'],
            ),
            AffiliationContactList(
                affiliation=mixed,
                name='Other',
                emails=['active@example.com', 'other@example.com', 'disabled@example.com'],
                inactive_emails=['disabled@example.com'],
            ),
            AffiliationContactList(
                affiliation=disabled,
                name='Representatives',
                emails=['disabled-only@example.com'],
                inactive_emails=['disabled-only@example.com'],
            ),
            AffiliationContactList(
                affiliation=disabled,
                name='Other',
                emails=['also-disabled@example.com'],
                inactive_emails=['also-disabled@example.com'],
            ),
        ])
        db.session.flush()

        resp = test_client.post(
            '/admin/plugins/affiliation_extras/representatives/email/send',
            json={
                'affiliation_ids': [mixed.id, disabled.id, empty.id],
                'sender_address': admin.email,
                'subject': 'Invitation',
                'body': 'Please register',
                'contact_lists': contact_lists,
                'include_unnamed_lists': False,
            },
        )

        assert resp.status_code == 200
        mails = extract_emails(smtp, required=False)
        assert {mail['To'] for mail in mails} == expected_recipients
        assert len(mails) == len(expected_recipients)
        assert resp.json == {'count': len(expected_recipients), 'skipped': 2}


class TestAffiliationFocalPoints:
    def test_focal_points_get_denies_non_admin(self, test_client, db, create_user):
        affiliation = _create_affiliation(db)
        _login(test_client, create_user(123))
        resp = test_client.get(_url(affiliation))
        assert resp.status_code == 403

    def test_focal_points_patch_denies_non_admin(self, test_client, db, create_user, no_csrf_check):
        affiliation = _create_affiliation(db)
        _login(test_client, create_user(123))
        resp = test_client.patch(_url(affiliation), json={'focal_points': []})
        assert resp.status_code == 403

    def test_focal_points_patch_then_get_returns_users(self, test_client, db, create_user, no_csrf_check):
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

    def test_focal_points_patch_empty_list_clears(self, test_client, db, create_user, no_csrf_check):
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
