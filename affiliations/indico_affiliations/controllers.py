# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import mimetypes
from email.utils import formataddr

from flask import jsonify, session
from marshmallow import fields, validate
from webargs.flaskparser import abort
from werkzeug.exceptions import Forbidden, NotFound

from indico.core.config import config
from indico.core.db import db
from indico.core.notifications import make_email, send_email
from indico.core.plugins import get_plugin_template_module, url_for_plugin
from indico.modules.admin import RHAdminBase
from indico.modules.files.models.files import File
from indico.modules.files.util import validate_upload_file_size
from indico.modules.logs.models.entries import AppLogEntry, AppLogRealm, LogKind
from indico.modules.logs.util import make_diff_log
from indico.modules.users.models.affiliations import Affiliation
from indico.util.fs import secure_client_filename
from indico.util.marshmallow import LowercaseString, ModelField, ModelList, no_relative_urls, not_empty
from indico.util.placeholders import get_sorted_placeholders, replace_placeholders
from indico.util.string import validate_email
from indico.web.args import use_kwargs, use_rh_args, use_rh_kwargs
from indico.web.util import ExpectedError

from indico_affiliations.models.contacts import AffiliationContactList
from indico_affiliations.models.groups import AffiliationGroup
from indico_affiliations.models.tags import AffiliationTag
from indico_affiliations.schemas import (AffiliationGroupArgs, AffiliationGroupSchema, AffiliationTagArgs,
                                         AffiliationTagSchema)
from indico_affiliations.util import (IMAGE_TOKEN_MAX_AGE, load_image_token, make_image_token, populate_memberships,
                                      prepare_inline_images)


class RHEmailRepresentativesBase(RHAdminBase):
    """Base class for emailing affiliation representatives."""

    @use_kwargs({
        'affiliations': ModelList(
            Affiliation,
            filter_deleted=True,
            data_key='affiliation_ids',
            required=True,
        ),
        'contact_lists': fields.List(fields.String(), required=True)
    })
    def _process_args(self, affiliations, contact_lists):
        RHAdminBase._process_args(self)
        self.contact_lists = set(contact_lists)
        self.recipients = {
            aff: {e for e in self._get_affiliation_emails(aff) if validate_email(e)}
            for aff in affiliations
        }

    def _get_affiliation_emails(self, affiliation):
        return {
            email.strip().lower()
            for lst in affiliation.contacts if not self.contact_lists or lst.name in self.contact_lists
            for email in lst.emails
        }

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
        own_email = session.user.email if session.user else None
        return dict(sorted(formatted.items(), key=lambda x: (x[0] != own_email, x[1].lower())))


class RHEmailRepresentativesMetadata(RHEmailRepresentativesBase):
    """Return metadata for the email representatives form."""

    def _process(self):
        invalid_affiliations = [{
            'id': affiliation.id,
            'invalid_emails': [e for e in self._get_affiliation_emails(affiliation) if e not in to_list],
        } for affiliation, to_list in self.recipients.items()]
        placeholders = get_sorted_placeholders('affiliation-representation-email')
        return jsonify({
            'senders': list(self._get_allowed_sender_emails().items()),
            'recipients_count': sum(len(emails) for emails in self.recipients.values()),
            'invalid_affiliations': [a for a in invalid_affiliations if a['invalid_emails']],
            'placeholders': [p.serialize() for p in placeholders],
        })


class RHEmailRepresentativesPreview(RHEmailRepresentativesBase):
    """Preview an email sent to affiliation representatives."""

    @use_kwargs({
        'body': fields.String(required=True),
        'subject': fields.String(required=True, validate=validate.Length(max=200)),
    })
    def _process(self, body, subject):
        affiliation = next(aff for aff in self.recipients)
        email_body = replace_placeholders('affiliation-representation-email', body, affiliation=affiliation)
        email_subject = replace_placeholders('affiliation-representation-email', subject, affiliation=affiliation)
        tpl = get_plugin_template_module('emails/custom_email.html', subject=email_subject, body=email_body)
        return jsonify(subject=tpl.get_subject(), body=tpl.get_body())


class RHEmailRepresentativesSend(RHEmailRepresentativesBase):
    """Send emails to affiliation representatives."""

    @use_kwargs({
        'sender_address': fields.String(required=True, validate=not_empty),
        'body': fields.String(required=True, validate=[not_empty, no_relative_urls]),
        'subject': fields.String(required=True, validate=[not_empty, validate.Length(max=200)]),
        'bcc_addresses': fields.List(LowercaseString(validate=validate.Email()), load_default=lambda: []),
        'copy_for_sender': fields.Bool(load_default=False),
    })
    def _process(self, sender_address, body, subject, bcc_addresses, copy_for_sender):
        sender_address = self._get_allowed_sender_emails(for_sending=True).get(sender_address)
        if not sender_address:
            abort(422, messages={'sender_address': ['Invalid sender address']})
        valid_recipients = {affiliation: to_list for affiliation, to_list in self.recipients.items() if to_list}
        if not valid_recipients:
            raise ExpectedError('There are no recipients with contact emails.')

        bcc = {session.user.email} if copy_for_sender and session.user else set()
        bcc.update(bcc_addresses)

        body, inline_attachments = prepare_inline_images(body, user_id=session.user.id)

        for affiliation, to_list in valid_recipients.items():
            email_body = replace_placeholders('affiliation-representation-email', body, affiliation=affiliation)
            email_subject = replace_placeholders('affiliation-representation-email', subject, affiliation=affiliation)
            tpl = get_plugin_template_module('emails/custom_email.html', subject=email_subject, body=email_body)
            email = make_email(to_list=to_list, bcc_list=sorted(bcc), sender_address=sender_address,
                               template=tpl, html=True, attachments=inline_attachments)
            send_email(email, module='Affiliations', user=session.user)

        AppLogEntry.log(AppLogRealm.admin, LogKind.other, 'Affiliations',
                        'Sent email to affiliation representatives', session.user,
                        data={'Sender': sender_address, 'Subject': subject, 'Body': body, '_html_fields': ['Body']})
        return jsonify(count=len(self.recipients))


class RHEmailRepresentativesImageUpload(RHAdminBase):
    """Upload an image to embed in affiliation emails."""

    @use_kwargs({'upload': fields.Raw(required=True)}, location='files')
    def _process(self, upload):
        if not validate_upload_file_size(upload):
            abort(422, messages={'upload': ['File is too large']})
        filename = secure_client_filename(upload.filename)
        content_type = mimetypes.guess_type(upload.filename)[0] or upload.mimetype or 'application/octet-stream'
        if not content_type.startswith('image/'):
            abort(422, messages={'upload': ['Only image files are allowed']})
        file = File.create_from_stream(upload.stream, filename, content_type, context=('affiliations', 'email'))
        file_uuid = file.uuid.hex if hasattr(file.uuid, 'hex') else str(file.uuid)
        token = make_image_token(file_uuid, session.user.id)
        url = url_for_plugin('affiliations.email_representatives_image', token=token, _external=True)
        return jsonify(url=url)


class RHEmailRepresentativesImage(RHAdminBase):
    """Serve an uploaded image for previewing in the editor."""

    @use_kwargs({'token': fields.String(required=True)}, location='view_args')
    def _process(self, token):
        data = load_image_token(token, max_age=IMAGE_TOKEN_MAX_AGE)
        if not data:
            raise NotFound
        if data.get('user_id') != session.user.id:
            raise Forbidden
        file = File.query.filter_by(uuid=data['uuid']).first_or_404()
        return file.send(inline=True)


class RHAffiliationGroups(RHAdminBase):
    """Return all affiliation groups."""

    def _process_GET(self):
        groups = (AffiliationGroup.query
                  .filter(~AffiliationGroup.is_deleted)
                  .order_by(db.func.indico.indico_unaccent(db.func.lower(AffiliationGroup.name)))
                  .all())
        return AffiliationGroupSchema(many=True).jsonify(groups)

    @use_rh_kwargs(AffiliationGroupArgs)
    def _process_POST(self, name, code, tags, meta):
        group = AffiliationGroup(name=name, code=code, tags=tags, meta=meta)
        db.session.add(group)
        db.session.flush()
        group.log(AppLogRealm.admin, LogKind.positive, 'Affiliation Groups',
                  f'Affiliation group "{group.name}" created', session.user)
        return AffiliationGroupSchema().jsonify(group), 201


class RHAffiliationGroup(RHAdminBase):
    """CRUD operations on a single affiliation group."""

    @use_kwargs({'group': ModelField(AffiliationGroup, filter_deleted=True, required=True, data_key='group_id')},
                location='view_args')
    def _process_args(self, group):
        RHAdminBase._process_args(self)
        self.group = group

    def _process_GET(self):
        return AffiliationGroupSchema().jsonify(self.group)

    @use_rh_args(AffiliationGroupArgs, partial=True)
    def _process_PATCH(self, data):
        if not data:
            return '', 204
        if self.group.system:
            changes = {}
        else:
            changes = self.group.populate_from_dict(data, skip={'tags'})
        # we allow assigning tags for system groups
        changes = populate_memberships(self.group, data, keys={'tags'}, changes=changes)
        log_fields = {
            'name': 'Name',
            'code': 'Code',
            'tags': {'title': 'Tags', 'type': 'list'},
            'meta': 'Metadata'
        }
        self.group.log(AppLogRealm.admin, LogKind.change, 'Affiliation Groups',
                       f'Affiliation group "{self.group.name}" modified', session.user,
                       data={'Changes': make_diff_log(changes, log_fields)})
        db.session.flush()
        return '', 204

    def _process_DELETE(self):
        self.group.log(AppLogRealm.admin, LogKind.negative, 'Affiliation Groups',
                       f'Affiliation group "{self.group.name}" deleted', session.user)
        self.group.is_deleted = True
        db.session.flush()
        return '', 204


class RHAffiliationTags(RHAdminBase):
    """Return all affiliation tags."""

    def _process_GET(self):
        tags = (AffiliationTag.query
                .filter(~AffiliationTag.is_deleted)
                .order_by(db.func.indico.indico_unaccent(db.func.lower(AffiliationTag.name)))
                .all())
        return AffiliationTagSchema(many=True).jsonify(tags)

    @use_rh_kwargs(AffiliationTagArgs)
    def _process_POST(self, name, code, color):
        tag = AffiliationTag(name=name, code=code, color=color)
        db.session.add(tag)
        db.session.flush()
        tag.log(AppLogRealm.admin, LogKind.positive, 'Affiliation Tags',
                f'Affiliation tag "{tag.name}" created', session.user)
        return AffiliationTagSchema().jsonify(tag), 201


class RHAffiliationTag(RHAdminBase):
    """CRUD operations on a single affiliation tag."""

    @use_kwargs({'tag': ModelField(AffiliationTag, filter_deleted=True, required=True, data_key='tag_id')},
                location='view_args')
    def _process_args(self, tag):
        RHAdminBase._process_args(self)
        self.tag = tag

    def _process_GET(self):
        return AffiliationTagSchema().jsonify(self.tag)

    @use_rh_args(AffiliationTagArgs, partial=True)
    def _process_PATCH(self, data):
        if not data:
            return '', 204
        changes = self.tag.populate_from_dict(data)
        log_fields = {'name': 'Name', 'code': 'Code', 'color': 'Color'}
        self.tag.log(AppLogRealm.admin, LogKind.change, 'Affiliation Tags',
                     f'Affiliation tag "{self.tag.name}" modified', session.user,
                     data={'Changes': make_diff_log(changes, log_fields)})
        db.session.flush()
        return '', 204

    def _process_DELETE(self):
        self.tag.log(AppLogRealm.admin, LogKind.negative, 'Affiliation Tags',
                     f'Affiliation tag "{self.tag.name}" deleted', session.user)
        self.tag.is_deleted = True
        db.session.flush()
        return '', 204


class RHContactListNames(RHAdminBase):
    """Return all contact-list names."""

    def _process_GET(self):
        names = (db.session.query(AffiliationContactList.name)
                 .filter(AffiliationContactList.name != '')  # noqa: PLC1901
                 .group_by(AffiliationContactList.name)
                 .order_by(db.func.indico.indico_unaccent(db.func.lower(AffiliationContactList.name)))
                 .all())
        return jsonify([name for name, in names])
