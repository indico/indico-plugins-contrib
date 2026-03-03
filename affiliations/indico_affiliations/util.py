# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from copy import copy
from email.mime.image import MIMEImage
from email.utils import make_msgid
from typing import NotRequired, TypedDict
from urllib.parse import urlsplit

from lxml import html

from indico.modules.files.models.files import File
from indico.modules.users.models.affiliations import Affiliation
from indico.util.signing import secure_serializer

from indico_affiliations.models.groups import AffiliationGroup
from indico_affiliations.models.tags import AffiliationTag


class _Memberships(TypedDict):
    groups: NotRequired[set[AffiliationGroup]]
    tags: NotRequired[set[AffiliationTag]]


type _Changes = dict[str, tuple[list[str], list[str]]]


IMAGE_TOKEN_SALT = 'affiliations-email-image'  # noqa: S105 - serializer salt identifier, not a credential
IMAGE_URL_PREFIX = '/api/admin/plugins/affiliations/representatives/email/image/'
IMAGE_TOKEN_MAX_AGE = 60 * 60 * 24


def make_image_token(file_uuid: str, user_id: int) -> str:
    return secure_serializer.dumps({'uuid': str(file_uuid), 'user_id': user_id}, salt=IMAGE_TOKEN_SALT)


def load_image_token(token: str, *, max_age: int = IMAGE_TOKEN_MAX_AGE) -> dict | None:
    try:
        return secure_serializer.loads(token, salt=IMAGE_TOKEN_SALT, max_age=max_age)
    except Exception:
        return None


def get_token_from_src(src: str) -> str | None:
    if not src:
        return None
    path = urlsplit(src).path
    if not path.startswith(IMAGE_URL_PREFIX):
        return None
    return path.rsplit('/', 1)[-1] or None


def build_inline_attachment(token: str, user_id: int):
    data = load_image_token(token)
    if not data or data.get('user_id') != user_id:
        return None, None
    file = File.query.filter_by(uuid=data['uuid']).first()
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


def populate_memberships(obj: Affiliation | AffiliationGroup, memberships: _Memberships, *,
                         keys: set[str] | None = None, changes: _Changes = None) -> _Changes:
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
