# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from copy import copy
from email.mime.image import MIMEImage
from email.utils import formataddr, make_msgid
from typing import NotRequired, TypedDict
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from flask import current_app, session
from itsdangerous import BadSignature
from lxml import html
from werkzeug.exceptions import HTTPException

from indico.core.config import config
from indico.core.db import db
from indico.core.errors import UserValueError
from indico.modules.files.models.files import File
from indico.modules.users.models.affiliations import Affiliation
from indico.util.signing import secure_serializer

from indico_affiliation_extras.models.contacts import AffiliationContactList
from indico_affiliation_extras.models.groups import AffiliationGroup
from indico_affiliation_extras.models.tags import AffiliationTag


class _Memberships(TypedDict):
    groups: NotRequired[set[AffiliationGroup]]
    tags: NotRequired[set[AffiliationTag]]


type _Changes = dict[str, tuple[object, object]]
type _LogFields = dict[str, str | dict[str, object]]


IMAGE_TOKEN_MAX_AGE = 60 * 60 * 24


def get_token_from_src(src: str) -> str | None:
    if not src:
        return None
    parts = urlsplit(src)
    token = parse_qs(parts.query).get('token', [None])[0]
    if not token:
        return None
    try:
        adapter = current_app.url_map.bind('', url_scheme=parts.scheme or 'http')
        endpoint, __ = adapter.match(parts.path, method='GET')
    except HTTPException:
        return None
    if endpoint != 'files.download_file':
        return None
    return token


def build_inline_attachment(token: str, _user_id: int):
    try:
        file_uuid = secure_serializer.loads(token, salt='file-download', max_age=IMAGE_TOKEN_MAX_AGE)
    except BadSignature:
        return None, None
    file = File.query.filter_by(uuid=UUID(file_uuid)).first()
    if file is None:
        return None, None
    maintype, __, subtype = (file.content_type or 'application/octet-stream').partition('/')
    if maintype != 'image':
        return None, None
    with file.open() as f:
        content = f.read()
    cid = make_msgid(domain='indico').strip('<>')
    attachment = MIMEImage(content, _subtype=subtype)
    attachment.add_header('Content-ID', f'<{cid}>')
    attachment.add_header('Content-Disposition', 'inline', filename=file.filename)
    return cid, attachment


def prepare_inline_images(body: str, *, user_id: int):
    if not body:
        return body, []
    try:
        root = html.fragment_fromstring(body, create_parent='div')
    except Exception:
        return body, []

    attachments = []
    token_cache: dict[str, str] = {}
    for img in root.iter('img'):
        src = img.get('src')
        token = get_token_from_src(src)
        if not token:
            continue
        if token in token_cache:
            img.set('src', f'cid:{token_cache[token]}')
            continue
        cid, attachment = build_inline_attachment(token, user_id)
        if not cid:
            continue
        token_cache[token] = cid
        attachments.append(attachment)
        img.set('src', f'cid:{cid}')

    chunks = []
    if root.text:
        chunks.append(root.text)
    for child in root:
        chunks.append(html.tostring(child, encoding='unicode', method='html'))
        if child.tail:
            chunks.append(child.tail)
    return ''.join(chunks), attachments


def get_allowed_sender_emails(*, for_sending: bool = False) -> dict[str, str]:
    emails: dict[str, str | None] = {}
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


def populate_memberships(
    obj: Affiliation | AffiliationGroup,
    memberships: _Memberships,
    *,
    keys: set[str] | None = None,
    changes: _Changes = None,
) -> _Changes:
    changes = copy(changes) or {}
    for key, value in memberships.items():
        if keys and key not in keys:
            continue
        old_value = sorted(v.code for v in getattr(obj, key))
        new_value = sorted(v.code for v in value)
        setattr(obj, key, value)
        if key in changes:
            if changes[key][0] == new_value:
                del changes[key]
            else:
                changes[key] = (changes[key][0], new_value)
        elif old_value != new_value:
            changes[key] = (old_value, new_value)
    return changes


def serialize_contact_lists(contact_lists: list[AffiliationContactList]) -> dict[int, dict]:
    return {
        item.id: {
            'name': item.name or '(unnamed list)',
            'emails': sorted(item.emails),
        }
        for item in contact_lists
    }


def populate_contacts(affiliation: Affiliation, contact_lists: list[dict]) -> tuple[_Changes, _LogFields]:
    existing_by_id = {item.id: item for item in affiliation.contact_lists}
    used_ids = set()
    touched_ids = set()

    old_contact_lists = serialize_contact_lists(affiliation.contact_lists)
    for contact_data in contact_lists:
        contact = contact_data.get('id')
        if contact is None:
            contact = AffiliationContactList()
            affiliation.contact_lists.append(contact)
        else:
            contact_id = contact.id
            if contact_id in used_ids:
                raise UserValueError('Contact list IDs must be unique')
            if contact_id not in existing_by_id:
                raise UserValueError('Contact list does not belong to this affiliation')
            touched_ids.add(contact_id)
            used_ids.add(contact_id)
        contact.name = contact_data['name']
        contact.emails = contact_data['emails']

    for contact_id, contact in existing_by_id.items():
        if contact_id not in touched_ids:
            affiliation.contact_lists.remove(contact)

    db.session.flush()
    new_contact_lists = serialize_contact_lists(affiliation.contact_lists)
    if old_contact_lists == new_contact_lists:
        return {}, {}
    changes = {}
    log_fields: _LogFields = {}

    # List names changes
    old_summary = sorted((lst['name'] for lst in old_contact_lists.values()), key=str.lower)
    new_summary = sorted((lst['name'] for lst in new_contact_lists.values()), key=str.lower)
    if old_summary != new_summary:
        changes['contact_lists'] = (old_summary, new_summary)

    # Individual list changes
    for id_ in old_contact_lists.keys() | new_contact_lists.keys():
        old_data = old_contact_lists.get(id_, {})
        new_data = new_contact_lists.get(id_, {})
        old_emails = old_data.get('emails', [])
        new_emails = new_data.get('emails', [])
        if old_emails == new_emails:
            continue
        name = new_data.get('name') or old_data.get('name')
        key = f'contact_lists_item_{id_}'
        changes[key] = (old_emails, new_emails)
        log_fields[key] = {'title': f'Contact list: {name}', 'type': 'list'}
    return changes, log_fields


def resolve_object_path(obj: dict | list, path: str) -> str:
    if not path:
        return ''
    for part in path.split('.'):
        if isinstance(obj, dict):
            obj = obj.get(part, '')
        elif isinstance(obj, list):
            try:
                obj = obj[int(part)]
            except (ValueError, IndexError):
                return ''
        else:
            return ''
    scalar_types = (str, int, float, bool)
    if isinstance(obj, list) and all(isinstance(x, scalar_types) for x in obj):
        return ', '.join(str(x) for x in obj)
    if isinstance(obj, scalar_types):
        return str(obj)
    return ''


def get_contact_list_names() -> list[str]:
    names = (
        db.session
        .query(AffiliationContactList.name)
        .filter(AffiliationContactList.name != '')  # noqa: PLC1901
        .group_by(AffiliationContactList.name)
        .order_by(db.func.indico.indico_unaccent(db.func.lower(AffiliationContactList.name)))
    )
    return [name for (name,) in names]
