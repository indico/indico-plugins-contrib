# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest

from indico.modules.events import EventLogRealm
from indico.modules.events.registration.models.invitations import RegistrationInvitation
from indico.modules.logs import LogKind
from indico.modules.users.models.affiliations import Affiliation

from indico_affiliation_extras.focal_points import set_focal_points
from indico_affiliation_extras.models.contacts import AffiliationContactList


pytest_plugins = 'indico.modules.events.registration.testing.fixtures'


def _login(test_client, user):
    with test_client.session_transaction() as sess:
        sess.set_session_user(user)


def _url(regform):
    return (
        f'/admin/plugins/affiliation_extras/events/{regform.event.id}/regforms/{regform.id}/affiliation-catalog/invite'
    )


def _affiliation_invite_url(regform):
    return f'/admin/plugins/affiliation_extras/events/{regform.event.id}/regforms/{regform.id}/invite'


def _metadata_url(regform):
    return f'{_url(regform)}/metadata'


def _recipient_count_url(regform):
    return f'{_url(regform)}/recipient-count'


class TestInvitations:
    @pytest.mark.parametrize('first_source', ('contacts', 'focal_points'))
    @pytest.mark.usefixtures('no_csrf_check')
    def test_invite_catalog_skips_previously_invited_user(
        self,
        test_client,
        db,
        dummy_regform,
        dummy_user,
        create_user,
        create_event_catalog,
        monkeypatch,
        first_source,
    ):
        monkeypatch.setattr('indico.modules.events.registration.util.notify_invitation', lambda *args, **kwargs: None)
        dummy_regform.event.update_principal(dummy_user, full_access=True)
        _login(test_client, dummy_user)
        managed = Affiliation(name='CERN')
        db.session.add(managed)
        db.session.flush()
        create_event_catalog(dummy_regform.event, {managed})
        contact = create_user(1, email='primary@example.test')
        contact.secondary_emails.add('secondary@example.test')
        set_focal_points(managed, {contact})
        db.session.add(
            AffiliationContactList(
                affiliation=managed,
                name='Operations',
                emails=['secondary@example.test'],
            )
        )
        db.session.flush()
        data = {
            'sender_address': dummy_user.email,
            'subject': 'Invitation',
            'body': 'Please register',
            'contact_lists': ['Operations'],
            'include_unnamed_lists': False,
        }

        first = test_client.post(_url(dummy_regform), json={**data, 'recipient_source': first_source})
        assert first.status_code == 200
        assert first.json['sent'] == 1
        second_source = 'focal_points' if first_source == 'contacts' else 'contacts'
        second = test_client.post(_url(dummy_regform), json={**data, 'recipient_source': second_source})

        assert second.status_code == 200
        assert second.json['sent'] == 0
        assert second.json['skipped'] == 1
        expected_email = 'secondary@example.test' if first_source == 'contacts' else contact.email
        assert [inv.email for inv in dummy_regform.invitations] == [expected_email]

    @pytest.mark.parametrize('registered', (True, False))
    @pytest.mark.usefixtures('no_csrf_check')
    def test_invite_secondary_contact_address(
        self,
        test_client,
        db,
        dummy_regform,
        dummy_user,
        create_user,
        create_registration,
        create_event_catalog,
        monkeypatch,
        registered,
    ):
        monkeypatch.setattr('indico.modules.events.registration.util.notify_invitation', lambda *args, **kwargs: None)
        dummy_regform.event.update_principal(dummy_user, full_access=True)
        _login(test_client, dummy_user)
        managed = Affiliation(name='CERN')
        db.session.add(managed)
        db.session.flush()
        create_event_catalog(dummy_regform.event, {managed})
        contact = create_user(1, email='primary@example.test')
        contact.secondary_emails.add('secondary@example.test')
        if registered:
            db.session.add(create_registration(contact, dummy_regform))
        db.session.add(
            AffiliationContactList(
                affiliation=managed,
                name='Operations',
                emails=['secondary@example.test'],
            )
        )
        db.session.flush()

        resp = test_client.post(
            _url(dummy_regform),
            json={
                'sender_address': dummy_user.email,
                'subject': 'Invitation',
                'body': 'Please register',
                'recipient_source': 'contacts',
                'contact_lists': ['Operations'],
                'include_unnamed_lists': False,
            },
        )

        assert resp.status_code == 200
        assert resp.json['sent'] == (0 if registered else 1)
        assert resp.json['skipped'] == (1 if registered else 0)
        assert [inv.email for inv in dummy_regform.invitations] == ([] if registered else ['secondary@example.test'])

    @pytest.mark.parametrize('recipient_source', ('contacts', 'both'))
    @pytest.mark.parametrize('include_primary', (True, False))
    @pytest.mark.usefixtures('no_csrf_check')
    def test_invite_catalog_deduplicates_user_addresses(
        self,
        test_client,
        db,
        dummy_regform,
        dummy_user,
        create_user,
        create_event_catalog,
        monkeypatch,
        recipient_source,
        include_primary,
    ):
        monkeypatch.setattr('indico.modules.events.registration.util.notify_invitation', lambda *args, **kwargs: None)
        dummy_regform.event.update_principal(dummy_user, full_access=True)
        _login(test_client, dummy_user)
        managed = Affiliation(name='CERN')
        db.session.add(managed)
        db.session.flush()
        create_event_catalog(dummy_regform.event, {managed})
        contact = create_user(1, email='primary@example.test')
        contact.secondary_emails.add('secondary@example.test')
        contact.secondary_emails.add('another@example.test')
        set_focal_points(managed, {contact})
        emails = ['secondary@example.test', 'another@example.test', 'unknown@example.test']
        if include_primary:
            emails.append(contact.email)
        db.session.add(AffiliationContactList(affiliation=managed, name='Operations', emails=emails))
        db.session.flush()
        source = {
            'recipient_source': recipient_source,
            'contact_lists': ['Operations'],
            'include_unnamed_lists': False,
        }

        count = test_client.post(_recipient_count_url(dummy_regform), json=source)
        assert count.status_code == 200
        assert count.json == {'recipient_count': 2}
        resp = test_client.post(
            _url(dummy_regform),
            json={
                **source,
                'sender_address': dummy_user.email,
                'subject': 'Invitation',
                'body': 'Please register',
            },
        )
        assert resp.status_code == 200
        assert resp.json['sent'] == 2
        assert resp.json['skipped'] == 0
        expected_email = (
            'primary@example.test' if include_primary or recipient_source == 'both' else 'another@example.test'
        )
        assert {inv.email for inv in dummy_regform.invitations} == {expected_email, 'unknown@example.test'}

    @pytest.mark.parametrize(
        ('profile_affiliation', 'multiple_affiliations', 'expected_affiliation'),
        (
            ('', False, 'CERN'),
            ('WIPO', False, 'WIPO'),
            ('', True, ''),
            ('WIPO', True, 'WIPO'),
        ),
    )
    @pytest.mark.parametrize('recipient_source', ('focal_points', 'both'))
    @pytest.mark.usefixtures('no_csrf_check')
    def test_invite_affiliation_catalog_focal_points(
        self,
        test_client,
        db,
        dummy_regform,
        dummy_user,
        create_user,
        create_event_catalog,
        monkeypatch,
        profile_affiliation,
        multiple_affiliations,
        expected_affiliation,
        recipient_source,
    ):
        monkeypatch.setattr('indico.modules.events.registration.util.notify_invitation', lambda *args, **kwargs: None)
        dummy_regform.event.update_principal(dummy_user, full_access=True)
        _login(test_client, dummy_user)

        managed = Affiliation(name='CERN')
        other = Affiliation(name='MIT')
        db.session.add_all([managed, other])
        db.session.flush()
        create_event_catalog(dummy_regform.event, {managed})

        focal = create_user(1, first_name='Alice', last_name='Focal', email='alice@example.test')
        outside = create_user(2, first_name='Bob', last_name='Other', email='bob@example.test')
        set_focal_points(managed, {focal})
        set_focal_points(other, {outside})
        focal.affiliation = profile_affiliation
        if multiple_affiliations:
            additional = Affiliation(name='WIPO')
            db.session.add(additional)
            db.session.flush()
            create_event_catalog(dummy_regform.event, {managed, additional})
            set_focal_points(additional, {focal})
        db.session.add(AffiliationContactList(affiliation=managed, name='Operations', emails=[focal.email]))
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
                'recipient_source': recipient_source,
                'contact_lists': ['Operations'],
                'include_unnamed_lists': False,
            },
        )

        assert resp.status_code == 200
        assert resp.json['sent'] == 1
        assert resp.json['skipped'] == 0
        assert [inv.email for inv in dummy_regform.invitations] == ['alice@example.test']
        assert dummy_regform.invitations[0].affiliation == expected_affiliation
        log_entry = dummy_regform.event.log_entries.filter_by(module='Registration').one()
        assert log_entry.data['Recipient source'] == recipient_source
        assert log_entry.data['Contact lists'] == (['Operations'] if recipient_source == 'both' else [])
        assert log_entry.data['Include unnamed contact lists'] is False

    @pytest.mark.usefixtures('no_csrf_check')
    def test_invite_affiliation_catalog_contacts(
        self,
        test_client,
        db,
        dummy_regform,
        dummy_user,
        monkeypatch,
        create_event_catalog,
    ):
        monkeypatch.setattr('indico.modules.events.registration.util.notify_invitation', lambda *args, **kwargs: None)
        dummy_regform.event.update_principal(dummy_user, full_access=True)
        _login(test_client, dummy_user)

        managed = Affiliation(name='CERN')
        outside = Affiliation(name='MIT')
        db.session.add_all((managed, outside))
        db.session.flush()
        create_event_catalog(dummy_regform.event, {managed})
        db.session.add_all((
            AffiliationContactList(affiliation=managed, name='Operations', emails=['ops@example.test']),
            AffiliationContactList(affiliation=managed, name='Empty', emails=[]),
            AffiliationContactList(affiliation=managed, name='', emails=['contact@example.test']),
            AffiliationContactList(affiliation=outside, name='Operations', emails=['outside@example.test']),
        ))
        db.session.flush()

        resp = test_client.post(
            _url(dummy_regform),
            json={
                'sender_address': dummy_user.email,
                'subject': 'Invitation',
                'body': 'Please register',
                'recipient_source': 'contacts',
                'contact_lists': ['Empty', 'Operations'],
                'include_unnamed_lists': True,
            },
        )

        assert resp.status_code == 200
        assert resp.json['sent'] == 2
        assert resp.json['skipped'] == 0
        assert {(inv.email, inv.affiliation) for inv in dummy_regform.invitations} == {
            ('contact@example.test', 'CERN'),
            ('ops@example.test', 'CERN'),
        }
        log_entry = dummy_regform.event.log_entries.filter_by(module='Registration').one()
        assert log_entry.realm == EventLogRealm.management
        assert log_entry.kind == LogKind.other
        assert log_entry.module == 'Registration'
        assert log_entry.summary == 'Invitations sent'
        assert log_entry.user == dummy_user
        assert log_entry.data['Invitation mode'] == 'Affiliation catalog'
        assert log_entry.data['Recipient source'] == 'contacts'
        assert log_entry.data['Contact lists'] == ['Empty', 'Operations']
        assert log_entry.data['Include unnamed contact lists'] is True

    @pytest.mark.parametrize(('profile_affiliation', 'expected_affiliation'), (('', 'CERN'), ('WIPO', 'WIPO')))
    @pytest.mark.usefixtures('no_csrf_check')
    def test_invite_affiliation_catalog_uses_matching_user_data(
        self,
        test_client,
        db,
        dummy_regform,
        dummy_user,
        create_user,
        monkeypatch,
        profile_affiliation,
        expected_affiliation,
        create_event_catalog,
    ):
        monkeypatch.setattr('indico.modules.events.registration.util.notify_invitation', lambda *args, **kwargs: None)
        dummy_regform.event.update_principal(dummy_user, full_access=True)
        _login(test_client, dummy_user)

        managed = Affiliation(name='CERN')
        db.session.add(managed)
        db.session.flush()
        create_event_catalog(dummy_regform.event, {managed})
        contact_user = create_user(1, first_name='Alice', last_name='Contact', email='contact@example.test')
        contact_user.affiliation = profile_affiliation
        db.session.add(AffiliationContactList(affiliation=managed, name='Operations', emails=['contact@example.test']))
        db.session.flush()

        resp = test_client.post(
            _url(dummy_regform),
            json={
                'sender_address': dummy_user.email,
                'subject': 'Invitation',
                'body': 'Please register',
                'recipient_source': 'contacts',
                'contact_lists': ['Operations'],
                'include_unnamed_lists': False,
            },
        )

        assert resp.status_code == 200
        (invitation,) = dummy_regform.invitations
        assert (invitation.first_name, invitation.last_name, invitation.affiliation) == (
            'Alice',
            'Contact',
            expected_affiliation,
        )

    @pytest.mark.usefixtures('no_csrf_check')
    def test_invite_affiliation_catalog_omits_ambiguous_affiliation(
        self,
        test_client,
        db,
        dummy_regform,
        dummy_user,
        monkeypatch,
        create_event_catalog,
    ):
        monkeypatch.setattr('indico.modules.events.registration.util.notify_invitation', lambda *args, **kwargs: None)
        dummy_regform.event.update_principal(dummy_user, full_access=True)
        _login(test_client, dummy_user)

        cern = Affiliation(name='CERN')
        wipo = Affiliation(name='WIPO')
        db.session.add_all((cern, wipo))
        db.session.flush()
        create_event_catalog(dummy_regform.event, {cern, wipo})
        db.session.add_all((
            AffiliationContactList(affiliation=cern, name='Operations', emails=['shared@example.test']),
            AffiliationContactList(affiliation=wipo, name='Operations', emails=['shared@example.test']),
        ))
        db.session.flush()

        resp = test_client.post(
            _url(dummy_regform),
            json={
                'sender_address': dummy_user.email,
                'subject': 'Invitation',
                'body': 'Please register',
                'recipient_source': 'contacts',
                'contact_lists': ['Operations'],
                'include_unnamed_lists': False,
            },
        )

        assert resp.status_code == 200
        (invitation,) = dummy_regform.invitations
        assert invitation.affiliation == ''

    @pytest.mark.usefixtures('no_csrf_check')
    def test_invite_affiliation_catalog_returns_invitations_sorted_by_name(
        self,
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
                'recipient_source': 'focal_points',
                'contact_lists': [],
                'include_unnamed_lists': False,
            },
        )

        assert resp.status_code == 200
        assert [invitation['email'] for invitation in resp.json['invitation_list']] == [
            'alice.alpha@example.test',
            'alice.zulu@example.test',
        ]

    @pytest.mark.usefixtures('no_csrf_check')
    def test_invite_by_affiliation_invites_affiliation_users(
        self,
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

    @pytest.mark.parametrize('has_contacts', (True, False))
    def test_affiliation_catalog_invite_metadata(
        self,
        test_client,
        db,
        dummy_regform,
        dummy_user,
        create_user,
        create_event_catalog,
        has_contacts,
    ):
        dummy_regform.event.update_principal(dummy_user, full_access=True)
        _login(test_client, dummy_user)

        managed = Affiliation(name='CERN')
        additional = Affiliation(name='WIPO')
        unmanaged = Affiliation(name='MIT')
        db.session.add_all([managed, additional, unmanaged])
        db.session.flush()
        create_event_catalog(dummy_regform.event, {managed, additional})

        set_focal_points(managed, {create_user(1)})
        set_focal_points(unmanaged, {create_user(2)})
        db.session.add_all((
            AffiliationContactList(
                affiliation=managed,
                name='Operations',
                emails=['ops@example.test'] if has_contacts else [],
            ),
            AffiliationContactList(
                affiliation=managed,
                name='',
                emails=['contact@example.test'] if has_contacts else [],
            ),
            AffiliationContactList(affiliation=additional, name='Operations', emails=[]),
            AffiliationContactList(affiliation=managed, name='Empty', emails=[]),
            AffiliationContactList(affiliation=unmanaged, name='Outside', emails=['outside@example.test']),
        ))
        db.session.flush()

        resp = test_client.get(_metadata_url(dummy_regform))

        assert resp.status_code == 200
        assert resp.json == {
            'affiliation_count': 2,
            'contact_list_options': [
                {'name': '', 'has_contacts': has_contacts},
                {'name': 'Empty', 'has_contacts': False},
                {'name': 'Operations', 'has_contacts': has_contacts},
            ],
            'focal_point_count': 1,
            'has_affiliation_catalog': True,
        }

    def test_affiliation_catalog_invite_metadata_without_catalog(
        self,
        test_client,
        dummy_regform,
        dummy_user,
    ):
        dummy_regform.event.update_principal(dummy_user, full_access=True)
        _login(test_client, dummy_user)

        resp = test_client.get(_metadata_url(dummy_regform))

        assert resp.status_code == 200
        assert resp.json == {
            'affiliation_count': 0,
            'contact_list_options': [],
            'focal_point_count': 0,
            'has_affiliation_catalog': False,
        }

    @pytest.mark.usefixtures('no_csrf_check')
    def test_affiliation_catalog_invite_recipient_count_deduplicates_sources(
        self,
        test_client,
        db,
        dummy_regform,
        dummy_user,
        create_user,
        create_event_catalog,
    ):
        dummy_regform.event.update_principal(dummy_user, full_access=True)
        _login(test_client, dummy_user)

        managed = Affiliation(name='CERN')
        db.session.add(managed)
        db.session.flush()
        create_event_catalog(dummy_regform.event, {managed})

        focal_point = create_user(1, email='shared@example.test')
        set_focal_points(managed, {focal_point})
        db.session.add(
            AffiliationContactList(
                affiliation=managed,
                name='Operations',
                emails=['shared@example.test', 'contact@example.test'],
            )
        )
        db.session.flush()

        resp = test_client.post(
            _recipient_count_url(dummy_regform),
            json={
                'recipient_source': 'both',
                'contact_lists': ['Operations'],
                'include_unnamed_lists': False,
            },
        )

        assert resp.status_code == 200
        assert resp.json == {'recipient_count': 2}

    @pytest.mark.usefixtures('no_csrf_check')
    def test_affiliation_catalog_invite_rejects_unknown_contact_list(
        self,
        test_client,
        db,
        dummy_regform,
        dummy_user,
        create_event_catalog,
    ):
        dummy_regform.event.update_principal(dummy_user, full_access=True)
        _login(test_client, dummy_user)

        managed = Affiliation(name='CERN')
        db.session.add(managed)
        db.session.flush()
        create_event_catalog(dummy_regform.event, {managed})
        db.session.add(AffiliationContactList(affiliation=managed, name='Operations', emails=['ops@example.test']))
        db.session.flush()

        resp = test_client.post(
            _recipient_count_url(dummy_regform),
            json={
                'recipient_source': 'contacts',
                'contact_lists': ['Unknown'],
                'include_unnamed_lists': False,
            },
        )

        assert resp.status_code == 422
        assert 'contact_lists' in resp.json['webargs_errors']

    @pytest.mark.usefixtures('no_csrf_check')
    def test_affiliation_catalog_invite_recipient_count_requires_source(
        self,
        test_client,
        dummy_regform,
        dummy_user,
    ):
        dummy_regform.event.update_principal(dummy_user, full_access=True)
        _login(test_client, dummy_user)

        resp = test_client.post(
            _recipient_count_url(dummy_regform),
            json={
                'contact_lists': [],
                'include_unnamed_lists': False,
            },
        )

        assert resp.status_code == 422
        assert 'recipient_source' in resp.json['webargs_errors']

    @pytest.mark.usefixtures('no_csrf_check')
    def test_affiliation_catalog_invite_recipient_count_ignores_disabled_contacts(
        self,
        test_client,
        db,
        dummy_regform,
        dummy_user,
        create_event_catalog,
    ):
        dummy_regform.event.update_principal(dummy_user, full_access=True)
        _login(test_client, dummy_user)

        managed = Affiliation(name='CERN')
        db.session.add(managed)
        db.session.flush()
        create_event_catalog(dummy_regform.event, {managed})
        db.session.add(AffiliationContactList(affiliation=managed, name='Operations', emails=['ops@example.test']))
        db.session.flush()

        resp = test_client.post(
            _recipient_count_url(dummy_regform),
            json={
                'recipient_source': 'focal_points',
                'contact_lists': ['Unknown'],
                'include_unnamed_lists': True,
            },
        )

        assert resp.status_code == 200
        assert resp.json == {'recipient_count': 0}

    @pytest.mark.usefixtures('no_csrf_check')
    @pytest.mark.parametrize('recipient_source', ('contacts', 'both'))
    def test_invite_affiliation_catalog_rejects_no_contact_source(
        self,
        test_client,
        dummy_regform,
        dummy_user,
        recipient_source,
    ):
        dummy_regform.event.update_principal(dummy_user, full_access=True)
        _login(test_client, dummy_user)

        resp = test_client.post(
            _url(dummy_regform),
            json={
                'sender_address': dummy_user.email,
                'subject': 'Invitation',
                'body': 'Please register',
                'recipient_source': recipient_source,
                'contact_lists': [],
                'include_unnamed_lists': False,
            },
        )

        assert resp.status_code == 422
        assert resp.json['webargs_errors'] == {'contact_lists': ['At least one contact list is required']}

    @pytest.mark.usefixtures('no_csrf_check')
    @pytest.mark.parametrize('recipient_source', ('contacts', 'both'))
    @pytest.mark.parametrize('contact_list_name', ('Operations', '', None))
    @pytest.mark.parametrize('count_only', (False, True))
    def test_catalog_rejects_empty_contact_selection(
        self,
        test_client,
        db,
        dummy_regform,
        dummy_user,
        create_user,
        create_event_catalog,
        recipient_source,
        contact_list_name,
        count_only,
        monkeypatch,
    ):
        monkeypatch.setattr('indico.modules.events.registration.util.notify_invitation', lambda *args, **kwargs: None)
        dummy_regform.event.update_principal(dummy_user, full_access=True)
        _login(test_client, dummy_user)
        managed = Affiliation(name='CERN')
        db.session.add(managed)
        db.session.flush()
        create_event_catalog(dummy_regform.event, {managed})
        set_focal_points(managed, {create_user(1)})
        if contact_list_name is not None:
            db.session.add(AffiliationContactList(affiliation=managed, name=contact_list_name, emails=[]))
        db.session.flush()
        data = {
            'recipient_source': recipient_source,
            'contact_lists': [contact_list_name] if contact_list_name else [],
            'include_unnamed_lists': not contact_list_name,
        }
        if not count_only:
            data.update(sender_address=dummy_user.email, subject='Invitation', body='Please register')

        url = _recipient_count_url(dummy_regform) if count_only else _url(dummy_regform)
        resp = test_client.post(url, json=data)

        assert resp.status_code == 422
        assert resp.json['webargs_errors'] == {
            'contact_lists': ['No contacts match the selected contact lists.'],
        }
        assert not dummy_regform.invitations
