# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

# Controllers for registration form affiliation endpoints.

from email.utils import formataddr

from flask import jsonify, session
from marshmallow import fields, validate
from sqlalchemy.orm import joinedload, subqueryload
from webargs.flaskparser import abort
from werkzeug.exceptions import NotFound

from indico.core.config import config
from indico.core.db import db
from indico.modules.admin import RHAdminBase
from indico.modules.events.registration.controllers.display import RHRegistrationFormFieldActionBase
from indico.modules.events.registration.controllers.management import (
    RHManageRegFormBase,
    RHManageRegistrationFieldActionBase,
)
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.invitations import InvitationState, RegistrationInvitation
from indico.modules.events.registration.schemas import RegistrationInvitationSchema
from indico.modules.events.registration.util import create_invitation
from indico.modules.users.models.affiliations import Affiliation
from indico.modules.users.models.users import User
from indico.modules.users.util import SearchAffiliationsMixin
from indico.util.marshmallow import LowercaseString, ModelField, no_relative_urls, not_empty
from indico.web.args import use_kwargs

from indico_affiliation_extras.models.groups import AffiliationGroup
from indico_affiliation_extras.models.lists import AffiliationList
from indico_affiliation_extras.models.tags import AffiliationTag
from indico_affiliation_extras.schemas import (
    AffiliationGroupWithAffiliationsSchema,
    AffiliationTagWithAffiliationsSchema,
    AffiliationWithUsersSchema,
)
from indico_affiliation_extras.util import get_default_catalog, resolve_affiliations


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


class RHRegFormAffiliations(RHManageRegFormBase):
    """Return all non-deleted affiliations with their associated users."""

    def _process_GET(self):
        affiliations = (
            Affiliation.query.filter(~Affiliation.is_deleted)
            .order_by(db.func.indico.indico_unaccent(db.func.lower(Affiliation.name)))
            .all()
        )
        return AffiliationWithUsersSchema(many=True).jsonify(affiliations)


class RHRegFormAffiliationGroups(RHManageRegFormBase):
    """Return all non-deleted affiliation groups with their affiliations and users."""

    def _process_GET(self):
        groups = (
            AffiliationGroup.query.filter(~AffiliationGroup.is_deleted)
            .options(subqueryload('affiliations'))
            .order_by(db.func.indico.indico_unaccent(db.func.lower(AffiliationGroup.name)))
            .all()
        )
        return AffiliationGroupWithAffiliationsSchema(many=True).jsonify(groups)


class RHRegFormAffiliationTags(RHManageRegFormBase):
    """Return all affiliation tags with their affiliations and users."""

    def _process_GET(self):
        tags = (
            AffiliationTag.query.options(subqueryload('affiliations'))
            .order_by(db.func.indico.indico_unaccent(db.func.lower(AffiliationTag.name)))
            .all()
        )
        return AffiliationTagWithAffiliationsSchema(many=True).jsonify(tags)


class RHAffiliationUserCountByIds(RHManageRegFormBase):
    """Return per-affiliation user counts for a given list of affiliation IDs."""

    @use_kwargs({'affiliation_ids': fields.List(fields.Integer(), load_default=list)})
    def _process(self, affiliation_ids):
        counts = dict(
            db.session.execute(
                db.select(User.affiliation_id, db.func.count(User.id))
                .where(User.affiliation_id.in_(affiliation_ids))
                .group_by(User.affiliation_id)
            ).all()
        )
        return jsonify({str(aid): counts.get(aid, 0) for aid in affiliation_ids})


class RHAffiliationUserCount(RHAdminBase):
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
            db.session.execute(db.select(db.func.count(db.distinct(User.id))).where(User.affiliation_id.in_(aff_ids)))
            .scalar()
            if aff_ids
            else 0
        )
        return jsonify(count=count)


class RHInviteByAffiliation(RHAdminBase):
    """Invite users by affiliation, group, or tag membership."""

    @use_kwargs({'event_id': fields.Integer(required=True), 'reg_form_id': fields.Integer(required=True)},
                location='view_args')
    def _process_args(self, event_id, reg_form_id):
        RHAdminBase._process_args(self)
        self.regform = RegistrationForm.get_or_404(reg_form_id)
        if self.regform.event_id != event_id:
            abort(404)
        self.event = self.regform.event

    @use_kwargs({
        'sender_address': fields.String(required=True, validate=not_empty),
        'subject': fields.String(required=True, validate=[not_empty, validate.Length(max=200)]),
        'body': fields.String(required=True, validate=[not_empty, no_relative_urls]),
        'bcc_addresses': fields.List(LowercaseString(validate=validate.Email()), load_default=lambda: []),
        'copy_for_sender': fields.Bool(load_default=False),
        'skip_moderation': fields.Bool(load_default=False),
        'skip_access_check': fields.Bool(load_default=False),
        'lock_email': fields.Bool(load_default=False),
        'affiliations': fields.Dict(load_default=lambda: {}),
    })
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
        sender_address = self._get_allowed_sender_emails(for_sending=True).get(sender_address)
        if not sender_address:
            abort(422, messages={'sender_address': ['Invalid sender address']})
        if not self.regform.moderation_enabled:
            skip_moderation = False

        aff_ids = [a['id'] for a in affiliations.get('affiliations', [])]
        group_ids = [g['id'] for g in affiliations.get('groups', [])]
        tag_ids = [t['id'] for t in affiliations.get('tags', [])]

        group_objs = set(AffiliationGroup.query.filter(AffiliationGroup.id.in_(group_ids))) if group_ids else set()
        tag_objs = set(AffiliationTag.query.filter(AffiliationTag.id.in_(tag_ids))) if tag_ids else set()
        aff_objs = set(Affiliation.query.filter(Affiliation.id.in_(aff_ids))) if aff_ids else set()
        all_affiliations = resolve_affiliations(group_objs, tag_objs, aff_objs)
        users_by_id = {u.id: u for aff in all_affiliations for u in aff.user_affiliations.all()}

        invited = {inv.email.lower() for inv in self.regform.invitations}
        registered = {r.email.lower() for r in self.regform.registrations if r.is_active and r.email}
        existing = invited | registered
        users_to_invite = [u for u in users_by_id.values() if u.email and u.email.lower() not in existing]
        skipped = len(users_by_id) - len(users_to_invite)

        for user in users_to_invite:
            create_invitation(
                self.regform,
                {
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'email': user.email,
                    'affiliation': user.affiliation or '',
                },
                sender_address,
                subject,
                body,
                skip_moderation=skip_moderation,
                skip_access_check=skip_access_check,
                lock_email=lock_email,
                bcc_addresses=bcc_addresses,
                copy_for_sender=copy_for_sender,
            )

        invitations = (
            RegistrationInvitation.query.with_parent(self.regform)
            .options(joinedload('registration'))
            .order_by(db.func.lower(RegistrationInvitation.first_name))
            .all()
        )
        return jsonify(
            sent=len(users_to_invite),
            skipped=skipped,
            has_pending_invitations=any(i.state == InvitationState.pending for i in invitations),
            invitation_list=RegistrationInvitationSchema(many=True).dump(invitations),
        )

    def _get_allowed_sender_emails(self, *, for_sending=False):
        emails = {}
        if session.user:
            emails[session.user.email] = session.user.full_name
        for email in (config.SUPPORT_EMAIL, config.PUBLIC_SUPPORT_EMAIL, config.NO_REPLY_EMAIL):
            if email:
                emails.setdefault(email, None)
        formatted = {
            email.strip().lower(): (
                formataddr((name, email.strip().lower()))
                if for_sending and name
                else (f'{name} <{email}>' if name else email)
            )
            for email, name in emails.items()
            if email and email.strip()
        }
        own = session.user.email if session.user else None
        return dict(sorted(formatted.items(), key=lambda x: (x[0] != own, x[1].lower())))
