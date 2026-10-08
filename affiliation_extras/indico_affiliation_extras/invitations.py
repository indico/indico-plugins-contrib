# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from collections.abc import Collection, Sequence
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Literal

from marshmallow import ValidationError
from sqlalchemy.orm import contains_eager, joinedload

from indico.core.db import db
from indico.modules.events.models.events import Event
from indico.modules.users.models.emails import UserEmail
from indico.modules.users.models.users import User

from indico_affiliation_extras.focal_points import get_event_catalog_affiliation_ids, get_event_catalog_focal_points
from indico_affiliation_extras.models.contacts import AffiliationContactList


type _RecipientIdentity = tuple[Literal['user'], int] | tuple[Literal['email'], str]


class AffiliationCatalogRecipientSource(Enum):
    focal_points = auto()
    contacts = auto()
    both = auto()


@dataclass(frozen=True)
class InvitationRecipient:
    first_name: str
    last_name: str
    email: str
    affiliation: str
    id: int | None = None

    @property
    def identity_key(self) -> _RecipientIdentity:
        return ('user', self.id) if self.id is not None else ('email', self.email.lower())


@dataclass
class _ContactRecipientGroup:
    user: User | None
    emails: set[str] = field(default_factory=set)
    affiliations: set[str] = field(default_factory=set)


def _get_catalog_contact_lists(
    affiliation_ids: set[int],
    contact_lists: Collection[str],
    include_unnamed_lists: bool,
) -> list[AffiliationContactList]:
    filters = []
    if contact_lists:
        filters.append(AffiliationContactList.name.in_(contact_lists))
    if include_unnamed_lists:
        filters.append(AffiliationContactList.name == '')  # noqa: PLC1901
    lists = []
    if filters and affiliation_ids:
        lists = (
            AffiliationContactList.query
            .options(joinedload('affiliation'))
            .filter(AffiliationContactList.affiliation_id.in_(affiliation_ids), db.or_(*filters))
            .order_by(AffiliationContactList.affiliation_id, AffiliationContactList.id)
            .all()
        )
    if set(contact_lists) - {contact_list.name for contact_list in lists}:
        raise ValidationError({'contact_lists': ['Unknown contact list']})
    if not any(contact_list.emails for contact_list in lists):
        raise ValidationError({'contact_lists': ['No contacts match the selected contact lists.']})
    return lists


def _get_focal_point_recipients(event: Event, affiliation_ids: set[int]) -> list[InvitationRecipient]:
    recipients = []
    for user in get_event_catalog_focal_points(event, affiliation_ids):
        if not user.email:
            continue
        affiliations = {
            entry.affiliation.name for entry in user.focal_point_entries if entry.affiliation_id in affiliation_ids
        }
        fallback_affiliation = next(iter(affiliations)) if len(affiliations) == 1 else ''
        recipients.append(
            InvitationRecipient(
                first_name=user.first_name,
                last_name=user.last_name,
                email=user.email,
                affiliation=user.affiliation or fallback_affiliation,
                id=user.id,
            )
        )
    return recipients


def _get_contact_users(contact_lists: Sequence[AffiliationContactList]) -> dict[str, User]:
    emails = {email for contact_list in contact_lists for email in contact_list.emails}
    if not emails:
        return {}

    return {
        user_email.email: user_email.user
        for user_email in UserEmail.query
        .join(User, User.id == UserEmail.user_id)
        .options(
            contains_eager('user').joinedload('_primary_email'),
        )
        .filter(
            UserEmail.email.in_(emails),
            ~UserEmail.is_user_deleted,
            ~User.is_deleted,
        )
    }


def _group_contact_recipients(
    contact_lists: Sequence[AffiliationContactList],
    users_by_email: dict[str, User],
) -> list[_ContactRecipientGroup]:
    groups: dict[_RecipientIdentity, _ContactRecipientGroup] = {}
    for contact_list in contact_lists:
        for email in contact_list.emails:
            user = users_by_email.get(email)
            identity = ('user', user.id) if user else ('email', email.lower())
            if identity not in groups:
                groups[identity] = _ContactRecipientGroup(user)
            group = groups[identity]
            group.emails.add(email)
            group.affiliations.add(contact_list.affiliation.name)
    return list(groups.values())


def _get_contact_recipients(contact_lists: Sequence[AffiliationContactList]) -> list[InvitationRecipient]:
    users_by_email = _get_contact_users(contact_lists)
    groups = _group_contact_recipients(contact_lists, users_by_email)
    recipients = []
    for group in groups:
        user = group.user
        primary_email = user.email.lower() if user else None
        email = primary_email if primary_email in group.emails else min(group.emails, key=str.lower)
        fallback_affiliation = next(iter(group.affiliations)) if len(group.affiliations) == 1 else ''
        recipients.append(
            InvitationRecipient(
                first_name=user.first_name if user else '',
                last_name=user.last_name if user else '',
                email=email,
                affiliation=(user.affiliation if user else '') or fallback_affiliation,
                id=user.id if user else None,
            )
        )
    return recipients


def _combine_invitation_recipients(
    focal_points: Sequence[InvitationRecipient],
    contacts: Sequence[InvitationRecipient],
) -> list[InvitationRecipient]:
    unique_recipients: dict[_RecipientIdentity, InvitationRecipient] = {}
    for recipient in sorted(focal_points, key=lambda recipient: recipient.email.lower()):
        unique_recipients.setdefault(recipient.identity_key, recipient)
    for recipient in sorted(contacts, key=lambda recipient: recipient.email.lower()):
        unique_recipients.setdefault(recipient.identity_key, recipient)
    return list(unique_recipients.values())


def get_affiliation_catalog_invitation_recipients(
    event: Event,
    *,
    recipient_source: AffiliationCatalogRecipientSource,
    contact_lists: Collection[str],
    include_unnamed_lists: bool,
) -> list[InvitationRecipient]:
    """Resolve catalog recipients, preferring focal points, listed primary emails, then alphabetical emails."""
    affiliation_ids = get_event_catalog_affiliation_ids(event)
    focal_points = []
    contacts = []
    if recipient_source in {AffiliationCatalogRecipientSource.focal_points, AffiliationCatalogRecipientSource.both}:
        focal_points = _get_focal_point_recipients(event, affiliation_ids)
    if recipient_source in {AffiliationCatalogRecipientSource.contacts, AffiliationCatalogRecipientSource.both}:
        lists = _get_catalog_contact_lists(affiliation_ids, contact_lists, include_unnamed_lists)
        contacts = _get_contact_recipients(lists)
    return _combine_invitation_recipients(focal_points, contacts)


def filter_invitation_recipients(regform, recipients):
    """Exclude recipients already invited or actively registered by email or user identity."""
    invited = {inv.email.lower() for inv in regform.invitations}
    invited_user_ids = (
        {
            user_id
            for (user_id,) in db.session
            .query(UserEmail.user_id)
            .join(User)
            .filter(
                UserEmail.email.in_(invited),
                ~UserEmail.is_user_deleted,
                ~User.is_deleted,
            )
            .distinct()
        }
        if invited
        else set()
    )
    registrations = [r for r in regform.registrations if r.is_active]
    registered = {r.email.lower() for r in registrations if r.email}
    registered_user_ids = {r.user_id for r in registrations if r.user_id is not None}
    existing = invited | registered
    existing_user_ids = invited_user_ids | registered_user_ids
    return [r for r in recipients if r.email and r.email.lower() not in existing and r.id not in existing_user_ids]
