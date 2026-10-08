# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest

from indico.modules.users.models.affiliations import Affiliation

from indico_affiliation_extras.focal_points import set_focal_points
from indico_affiliation_extras.invitations import (
    AffiliationCatalogRecipientSource,
    get_affiliation_catalog_invitation_recipients,
)
from indico_affiliation_extras.models.contacts import AffiliationContactList


class TestContactInvitationRecipients:
    def test_focal_point_precedence(self, db, dummy_event, dummy_user, create_event_catalog):
        dummy_user.secondary_emails.add('alice.secondary@example.test')
        affiliation = Affiliation(name='CERN')
        db.session.add(affiliation)
        affiliation.contact_lists.append(
            AffiliationContactList(
                name='Ops',
                emails=['alice.secondary@example.test'],
            )
        )
        create_event_catalog(dummy_event, {affiliation})
        set_focal_points(affiliation, {dummy_user})
        db.session.flush()

        recipients = get_affiliation_catalog_invitation_recipients(
            dummy_event,
            recipient_source=AffiliationCatalogRecipientSource.both,
            contact_lists=['Ops'],
            include_unnamed_lists=False,
        )

        assert len(recipients) == 1
        assert recipients[0].email == dummy_user.email

    def test_contact_order(self, db, dummy_event, dummy_user, create_event_catalog):
        dummy_user.email = 'z.primary@example.test'
        affiliation = Affiliation(name='CERN')
        db.session.add(affiliation)
        affiliation.contact_lists.append(
            AffiliationContactList(
                name='Ops',
                emails=[dummy_user.email, 'alice@example.test'],
            )
        )
        create_event_catalog(dummy_event, {affiliation})
        db.session.flush()

        recipients = get_affiliation_catalog_invitation_recipients(
            dummy_event,
            recipient_source=AffiliationCatalogRecipientSource.contacts,
            contact_lists=['Ops'],
            include_unnamed_lists=False,
        )

        assert [recipient.email for recipient in recipients] == ['alice@example.test', dummy_user.email]

    @pytest.mark.parametrize(
        ('profile_affiliation', 'second_affiliation', 'expected'),
        (
            ('', 'WIPO', ''),
            ('Profile', 'WIPO', 'Profile'),
            ('', 'CERN', 'CERN'),
        ),
    )
    @pytest.mark.parametrize('include_primary', (True, False))
    def test_alias_affiliation_ambiguity(
        self,
        db,
        dummy_event,
        dummy_user,
        create_event_catalog,
        profile_affiliation,
        second_affiliation,
        expected,
        include_primary,
    ):
        dummy_user.affiliation = profile_affiliation
        dummy_user.secondary_emails.add('alice.secondary@example.test')
        dummy_user.secondary_emails.add('z.secondary@example.test')
        cern = Affiliation(name='CERN')
        other = Affiliation(name=second_affiliation) if second_affiliation != 'CERN' else cern
        db.session.add_all([cern, other])
        first_email = dummy_user.email if include_primary else 'z.secondary@example.test'
        cern.contact_lists.append(AffiliationContactList(name='Ops', emails=[first_email]))
        other.contact_lists.append(AffiliationContactList(name='Secondary', emails=['alice.secondary@example.test']))
        create_event_catalog(dummy_event, {cern, other})
        db.session.flush()

        recipients = get_affiliation_catalog_invitation_recipients(
            dummy_event,
            recipient_source=AffiliationCatalogRecipientSource.contacts,
            contact_lists=['Ops', 'Secondary'],
            include_unnamed_lists=False,
        )

        assert len(recipients) == 1
        assert recipients[0].email == (dummy_user.email if include_primary else 'alice.secondary@example.test')
        assert recipients[0].affiliation == expected
