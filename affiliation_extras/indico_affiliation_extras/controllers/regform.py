# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

# Controllers for registration form affiliation endpoints.


from flask import jsonify, session
from marshmallow import ValidationError, fields, validate, validates_schema
from sqlalchemy.orm import joinedload
from webargs.flaskparser import abort
from werkzeug.exceptions import NotFound

from indico.core.db import db
from indico.core.marshmallow import mm
from indico.modules.events import EventLogRealm
from indico.modules.events.registration.controllers.display import RHRegistrationFormFieldActionBase
from indico.modules.events.registration.controllers.management import (
    RHManageRegFormBase,
    RHManageRegistrationFieldActionBase,
)
from indico.modules.events.registration.models.invitations import InvitationState, RegistrationInvitation
from indico.modules.events.registration.schemas import RegistrationInvitationSchema
from indico.modules.events.registration.util import create_invitation
from indico.modules.logs import LogKind
from indico.modules.users.models.affiliations import Affiliation
from indico.modules.users.models.users import User
from indico.modules.users.util import SearchAffiliationsMixin
from indico.util.marshmallow import LowercaseString, ModelField, no_relative_urls, not_empty
from indico.web.args import use_kwargs

from indico_affiliation_extras.controllers.base import (
    AffiliationGroupsWithUsersMixin,
    AffiliationTagsWithUsersMixin,
    SearchAffiliationsExtendedMixin,
)
from indico_affiliation_extras.controllers.compat import CountriesListMixin
from indico_affiliation_extras.focal_points import get_event_catalog_affiliation_ids, get_event_catalog_focal_points
from indico_affiliation_extras.invitations import (
    AffiliationCatalogRecipientSource,
    filter_invitation_recipients,
    get_affiliation_catalog_invitation_recipients,
)
from indico_affiliation_extras.models.contacts import AffiliationContactList
from indico_affiliation_extras.models.groups import AffiliationGroup
from indico_affiliation_extras.models.lists import AffiliationList
from indico_affiliation_extras.models.tags import AffiliationTag
from indico_affiliation_extras.schemas import (
    AffiliationWithUsersSchema,
)
from indico_affiliation_extras.util import get_default_catalog, get_users_by_affiliation, resolve_affiliations


class SearchRepresentationAffiliationsMixin(SearchAffiliationsMixin):
    """Shared search context for representation affiliation RHs."""

    normalize_url_spec = {
        'locators': {
            lambda self: self.field,
            lambda self: {'affiliation_list_id': self.affiliation_list.id},
        },
        'skipped_args': {'section_id'},
    }

    @use_kwargs(
        {'affiliation_list': ModelField(AffiliationList, required=True, data_key='affiliation_list_id')},
        location='view_args',
    )
    def _process_args(self, affiliation_list):
        super()._process_args()
        self.affiliation_list = affiliation_list
        catalog = get_default_catalog(self.event)
        if not catalog or self.affiliation_list.catalog_id != catalog.id or not self.affiliation_list.is_enabled:
            raise NotFound

    @property
    def context(self):
        return {
            'event': self.event,
            'registration_form': self.regform,
            'field': self.field,
            'affiliation_list': self.affiliation_list,
        }


class RHSearchRepresentationAffiliation(SearchRepresentationAffiliationsMixin, RHRegistrationFormFieldActionBase):
    """Public representation affiliation search for registrants."""


class RHManageSearchRepresentationAffiliation(
    SearchRepresentationAffiliationsMixin, RHManageRegistrationFieldActionBase
):
    """Management representation affiliation search for registration managers."""


class RHRegFormAffiliationCountries(CountriesListMixin, RHManageRegFormBase):
    pass


class RHRegFormSearchAffiliationsExtended(SearchAffiliationsExtendedMixin, RHManageRegFormBase):
    pass


class RHRegFormAffiliations(RHManageRegFormBase):
    """Return all non-deleted affiliations with their associated users."""

    def _process_GET(self):
        affiliations = (
            Affiliation.query
            .filter(~Affiliation.is_deleted)
            .order_by(db.func.indico.indico_unaccent(db.func.lower(Affiliation.name)))
            .all()
        )
        context = {'users_by_affiliation': get_users_by_affiliation(affiliations)}
        return AffiliationWithUsersSchema(many=True, context=context).jsonify(affiliations)


class RHRegFormAffiliationGroups(AffiliationGroupsWithUsersMixin, RHManageRegFormBase):
    pass


class RHRegFormAffiliationTags(AffiliationTagsWithUsersMixin, RHManageRegFormBase):
    pass


class RHAffiliationUserCountByIds(RHManageRegFormBase):
    """Return per-affiliation user counts for a given list of affiliation IDs."""

    @use_kwargs({'affiliation_ids': fields.List(fields.Integer(), load_default=list)})
    def _process(self, affiliation_ids):
        counts = dict(
            db.session.execute(
                db
                .select(User.affiliation_id, db.func.count(User.id))
                .where(User.affiliation_id.in_(affiliation_ids))
                .group_by(User.affiliation_id)
            ).all()
        )
        return jsonify({str(aid): counts.get(aid, 0) for aid in affiliation_ids})


class RHAffiliationUserCount(RHManageRegFormBase):
    """Return the number of unique users for the given affiliation/group/tag selection."""

    @use_kwargs({
        'affiliation_ids': fields.List(fields.Integer(), load_default=list),
        'group_ids': fields.List(fields.Integer(), load_default=list),
        'tag_ids': fields.List(fields.Integer(), load_default=list),
    })
    def _process(self, affiliation_ids, group_ids, tag_ids):
        affiliations = set(Affiliation.query.filter(Affiliation.id.in_(affiliation_ids))) if affiliation_ids else set()
        groups = set(AffiliationGroup.query.filter(AffiliationGroup.id.in_(group_ids))) if group_ids else set()
        tags = set(AffiliationTag.query.filter(AffiliationTag.id.in_(tag_ids))) if tag_ids else set()
        all_affiliations = resolve_affiliations(groups, tags, affiliations)
        aff_ids = [aff.id for aff in all_affiliations]
        count = (
            db.session.execute(
                db.select(db.func.count(db.distinct(User.id))).where(User.affiliation_id.in_(aff_ids))
            ).scalar()
            if aff_ids
            else 0
        )
        return jsonify(count=count)


class InviteUsersArgs(mm.Schema):
    sender_address = fields.String(required=True, validate=not_empty)
    subject = fields.String(required=True, validate=[not_empty, validate.Length(max=200)])
    body = fields.String(required=True, validate=[not_empty, no_relative_urls])
    bcc_addresses = fields.List(LowercaseString(validate=validate.Email()), load_default=list)
    copy_for_sender = fields.Bool(load_default=False)
    skip_moderation = fields.Bool(load_default=False)
    skip_access_check = fields.Bool(load_default=False)
    lock_email = fields.Bool(load_default=False)


class InviteByAffiliationArgs(InviteUsersArgs):
    affiliations = fields.Dict(load_default=dict)


class AffiliationCatalogRecipientSelectionArgs(mm.Schema):
    recipient_source = fields.Enum(AffiliationCatalogRecipientSource, required=True)
    contact_lists = fields.List(fields.String(validate=not_empty), required=True)
    include_unnamed_lists = fields.Boolean(required=True)


class InviteAffiliationCatalogArgs(InviteUsersArgs, AffiliationCatalogRecipientSelectionArgs):
    @validates_schema
    def _validate_recipient_source(self, data, **kwargs):
        if (
            data['recipient_source']
            in {
                AffiliationCatalogRecipientSource.contacts,
                AffiliationCatalogRecipientSource.both,
            }
            and not data['contact_lists']
            and not data['include_unnamed_lists']
        ):
            raise ValidationError('At least one contact list is required', field_name='contact_lists')


class RHInviteUsersBase(RHManageRegFormBase):
    def _invite_recipients(
        self,
        recipients,
        sender_address,
        subject,
        body,
        bcc_addresses,
        copy_for_sender,
        skip_moderation,
        skip_access_check,
        lock_email,
        *,
        audit_log_data=None,
    ):
        sender_address = self.event.get_allowed_sender_emails(_for_sending=True).get(sender_address)
        if not sender_address:
            abort(422, messages={'sender_address': ['Invalid sender address']})
        if not self.regform.moderation_enabled:
            skip_moderation = False

        recipients = list(recipients)
        recipients_to_invite = filter_invitation_recipients(self.regform, recipients)
        skipped = len(recipients) - len(recipients_to_invite)

        for recipient in recipients_to_invite:
            create_invitation(
                self.regform,
                self._serialize_recipient(recipient),
                sender_address,
                subject,
                body,
                skip_moderation=skip_moderation,
                skip_access_check=skip_access_check,
                lock_email=lock_email,
                bcc_addresses=bcc_addresses,
                copy_for_sender=copy_for_sender,
            )

        self.regform.log(
            EventLogRealm.management,
            LogKind.other,
            'Registration',
            'Invitations sent',
            session.user,
            data={
                'Sender': sender_address,
                'BCC addresses': bcc_addresses,
                'CC to sender': copy_for_sender,
                'Subject': subject,
                'Body': body,
                'Skip moderation': skip_moderation,
                'Skip access check': skip_access_check,
                'Lock email': lock_email,
                **(audit_log_data or {}),
                '_html_fields': ['Body'],
            },
        )

        invitations = (
            RegistrationInvitation.query
            .with_parent(self.regform)
            .options(joinedload('registration'))
            .order_by(
                db.func.lower(RegistrationInvitation.first_name),
                db.func.lower(RegistrationInvitation.last_name),
                RegistrationInvitation.id,
            )
            .all()
        )
        return jsonify(
            sent=len(recipients_to_invite),
            skipped=skipped,
            has_pending_invitations=any(i.state == InvitationState.pending for i in invitations),
            invitation_list=RegistrationInvitationSchema(many=True).dump(invitations),
        )

    @staticmethod
    def _serialize_recipient(recipient):
        return {
            'first_name': recipient.first_name,
            'last_name': recipient.last_name,
            'email': recipient.email,
            'affiliation': recipient.affiliation or '',
        }


class RHInviteByAffiliation(RHInviteUsersBase):
    """Invite users by affiliation, group, or tag membership."""

    @use_kwargs(InviteByAffiliationArgs)
    def _process(
        self,
        sender_address,
        subject,
        body,
        bcc_addresses,
        copy_for_sender,
        skip_moderation,
        skip_access_check,
        lock_email,
        affiliations,
    ):
        aff_ids = [a['id'] for a in affiliations.get('affiliations', [])]
        group_ids = [g['id'] for g in affiliations.get('groups', [])]
        tag_ids = [t['id'] for t in affiliations.get('tags', [])]

        group_objs = set(AffiliationGroup.query.filter(AffiliationGroup.id.in_(group_ids))) if group_ids else set()
        tag_objs = set(AffiliationTag.query.filter(AffiliationTag.id.in_(tag_ids))) if tag_ids else set()
        aff_objs = set(Affiliation.query.filter(Affiliation.id.in_(aff_ids))) if aff_ids else set()
        all_affiliations = resolve_affiliations(group_objs, tag_objs, aff_objs)
        users_by_id = {
            user.id: user for user in User.query.filter(User.affiliation_id.in_(a.id for a in all_affiliations))
        }
        return self._invite_recipients(
            users_by_id.values(),
            sender_address,
            subject,
            body,
            bcc_addresses,
            copy_for_sender,
            skip_moderation,
            skip_access_check,
            lock_email,
        )


class RHAffiliationCatalogInviteMetadata(RHManageRegFormBase):
    """Return affiliation-catalog recipient information for the invitation dialog."""

    def _process(self):
        affiliation_ids = get_event_catalog_affiliation_ids(self.event)
        contact_lists = (
            db.session
            .query(
                AffiliationContactList.name,
                db.func.bool_or(db.func.cardinality(AffiliationContactList.emails) > 0),
            )
            .filter(AffiliationContactList.affiliation_id.in_(affiliation_ids))
            .group_by(AffiliationContactList.name)
            .order_by(db.func.indico.indico_unaccent(db.func.lower(AffiliationContactList.name)))
        )
        return jsonify(
            focal_point_count=len(get_event_catalog_focal_points(self.event, affiliation_ids)),
            affiliation_count=len(affiliation_ids),
            contact_list_options=[{'name': name, 'has_contacts': has_contacts} for name, has_contacts in contact_lists],
            has_affiliation_catalog=get_default_catalog(self.event) is not None,
        )


class RHAffiliationCatalogInviteRecipientCount(RHManageRegFormBase):
    """Return the number of unique recipients for an affiliation-catalog selection."""

    @use_kwargs(AffiliationCatalogRecipientSelectionArgs)
    def _process(self, recipient_source, contact_lists, include_unnamed_lists):
        recipients = get_affiliation_catalog_invitation_recipients(
            self.event,
            recipient_source=recipient_source,
            contact_lists=contact_lists,
            include_unnamed_lists=include_unnamed_lists,
        )
        return jsonify(recipient_count=len(recipients))


class RHInviteAffiliationCatalog(RHInviteUsersBase):
    """Invite selected recipients from the event's affiliation catalog."""

    @use_kwargs(InviteAffiliationCatalogArgs)
    def _process(
        self,
        sender_address,
        subject,
        body,
        bcc_addresses,
        copy_for_sender,
        skip_moderation,
        skip_access_check,
        lock_email,
        recipient_source,
        contact_lists,
        include_unnamed_lists,
    ):
        recipients = get_affiliation_catalog_invitation_recipients(
            self.event,
            recipient_source=recipient_source,
            contact_lists=contact_lists,
            include_unnamed_lists=include_unnamed_lists,
        )
        recipients.sort(key=lambda recipient: (recipient.last_name, recipient.first_name, recipient.email))
        include_contacts = recipient_source in {
            AffiliationCatalogRecipientSource.contacts,
            AffiliationCatalogRecipientSource.both,
        }
        return self._invite_recipients(
            recipients,
            sender_address,
            subject,
            body,
            bcc_addresses,
            copy_for_sender,
            skip_moderation,
            skip_access_check,
            lock_email,
            audit_log_data={
                'Invitation mode': 'Affiliation catalog',
                'Recipient source': recipient_source.name,
                'Contact lists': sorted(contact_lists) if include_contacts else [],
                'Include unnamed contact lists': include_contacts and include_unnamed_lists,
            },
        )
