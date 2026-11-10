# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest
from sqlalchemy.exc import IntegrityError

from indico.modules.users.models.affiliations import Affiliation

from indico_affiliation_extras.models.contacts import AffiliationContactList


@pytest.mark.parametrize('inactive_emails', ([], ['one@example.test'], ['one@example.test', 'two@example.test']))
def test_contact_list_accepts_inactive_email_subset(db, inactive_emails):
    contact_list = AffiliationContactList(
        affiliation=Affiliation(name='CERN'),
        emails=['one@example.test', 'two@example.test'],
        inactive_emails=inactive_emails,
    )
    db.session.add(contact_list)
    db.session.flush()

    assert contact_list.inactive_emails == inactive_emails


def test_contact_list_rejects_inactive_email_outside_list(db):
    db.session.add(
        AffiliationContactList(
            affiliation=Affiliation(name='CERN'),
            emails=['one@example.test'],
            inactive_emails=['other@example.test'],
        )
    )

    with pytest.raises(IntegrityError) as exc_info:
        db.session.flush()

    assert exc_info.value.orig.diag.constraint_name == 'ck_affiliation_contact_lists_inactive_emails_subset'


@pytest.mark.parametrize(
    ('emails', 'inactive_emails', 'expected'),
    (
        ([], [], False),
        (['one@example.test'], [], True),
        (['one@example.test'], ['one@example.test'], False),
        (['one@example.test', 'two@example.test'], ['one@example.test'], True),
        (['one@example.test', 'two@example.test'], ['one@example.test', 'one@example.test'], True),
    ),
)
def test_has_active_emails(db, emails, inactive_emails, expected):
    contact_list = AffiliationContactList(
        affiliation=Affiliation(name='CERN'),
        emails=emails,
        inactive_emails=inactive_emails,
    )
    db.session.add(contact_list)
    db.session.flush()

    assert contact_list.has_active_emails is expected
    assert (
        db.session
        .query(AffiliationContactList.has_active_emails)
        .filter(AffiliationContactList.id == contact_list.id)
        .scalar()
    ) is expected
