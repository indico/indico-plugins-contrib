# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import re

import pytest
from sqlalchemy.exc import IntegrityError

from indico.core.errors import UserValueError
from indico.modules.users.models.affiliations import Affiliation

from indico_affiliations import util
from indico_affiliations.models.contacts import AffiliationContactList


def test_get_token_from_src():
    token = 'abc123'
    src = f'https://example.test{util.IMAGE_URL_PREFIX}{token}'
    assert util.get_token_from_src(src) == token
    assert util.get_token_from_src(src + '?x=1') == token
    assert util.get_token_from_src('https://example.test/other') is None
    assert util.get_token_from_src('') is None


def test_prepare_inline_images_replaces_src_and_collects_attachments(monkeypatch):
    calls = []

    def fake_build_inline_attachment(token, user_id):
        calls.append((token, user_id))
        return f'cid-{token}', f'attachment-{token}'

    monkeypatch.setattr(util, 'build_inline_attachment', fake_build_inline_attachment)

    body = (
        '<p>Hello</p>'
        f'<img src="https://example.test{util.IMAGE_URL_PREFIX}t1" />'
        f'<img src="https://example.test{util.IMAGE_URL_PREFIX}t2" />'
    )
    new_body, attachments = util.prepare_inline_images(body, user_id=42)

    assert 'cid:cid-t1' in new_body
    assert 'cid:cid-t2' in new_body
    assert attachments == ['attachment-t1', 'attachment-t2']
    assert calls == [('t1', 42), ('t2', 42)]


def test_prepare_inline_images_dedupes_tokens(monkeypatch):
    def fake_build_inline_attachment(token, user_id):
        return f'cid-{token}', f'attachment-{token}'

    monkeypatch.setattr(util, 'build_inline_attachment', fake_build_inline_attachment)

    body = (
        f'<img src="https://example.test{util.IMAGE_URL_PREFIX}dup" />'
        f'<img src="https://example.test{util.IMAGE_URL_PREFIX}dup" />'
    )
    new_body, attachments = util.prepare_inline_images(body, user_id=1)

    assert len(re.findall(r'cid:cid-dup', new_body)) == 2
    assert attachments == ['attachment-dup']


def test_prepare_inline_images_ignores_non_matching_imgs(monkeypatch):
    monkeypatch.setattr(util, 'build_inline_attachment', lambda *a, **k: ('cid-x', 'att-x'))

    body = '<p><img src="https://example.test/other.png" /></p>'
    new_body, attachments = util.prepare_inline_images(body, user_id=1)

    assert 'https://example.test/other.png' in new_body
    assert attachments == []


def test_prepare_inline_images_invalid_html_returns_original():
    body = '<p><img src="broken"'  # malformed HTML
    new_body, attachments = util.prepare_inline_images(body, user_id=1)

    assert 'broken' in new_body
    assert attachments == []


def test_token_roundtrip():
    token = util.make_image_token('uuid-123', 7)
    data = util.load_image_token(token, max_age=util.IMAGE_TOKEN_MAX_AGE)
    assert data['uuid'] == 'uuid-123'
    assert data['user_id'] == 7


@pytest.mark.parametrize(
    ('obj', 'path', 'expected'),
    (
        ({'a': {'b': 'c'}}, 'a.b', 'c'),
        ({'a': {'b': 3}}, 'a.b', '3'),
        ({'a': {'b': True}}, 'a.b', 'True'),
        ({'a': {'b': None}}, 'a.b', ''),
        ({'a': {'b': ['x', 'y']}}, 'a.b', 'x, y'),
        ({'a': {'b': [1, 2]}}, 'a.b', '1, 2'),
        ({'a': {'b': ['x', {'y': 'z'}]}}, 'a.b', ''),
        ({'a': ['x', 'y']}, 'a.1', 'y'),
        ({'a': ['x', 'y']}, 'a.-1', 'y'),
        ({'a': ['x']}, 'a.2', ''),
        ({'a': ['x']}, 'a.foo', ''),
        ({'a': {'b': {'c': 'd'}}}, 'a.b', ''),
        ({'a': {'b': {'c': 'd'}}}, 'a.b.c', 'd'),
    ),
)
def test_resolve_object_path(obj, path, expected):
    assert util.resolve_object_path(obj, path) == expected


def _create_affiliation(db, name):
    affiliation = Affiliation(name=name)
    db.session.add(affiliation)
    db.session.flush()
    return affiliation


def _create_contact(db, affiliation, name, emails):
    contact = AffiliationContactList(affiliation=affiliation, name=name, emails=emails)
    db.session.add(contact)
    db.session.flush()
    return contact


def test_populate_contacts_adds_new_contact_and_logs_summary(db):
    affiliation = _create_affiliation(db, 'CERN')

    changes, log_fields = util.populate_contacts(affiliation, [
        {'id': None, 'name': 'Ops', 'emails': ['ops@example.test']},
    ])

    assert [c.name for c in affiliation.contacts] == ['Ops']
    assert len(affiliation.contacts) == 1
    contact_id = affiliation.contacts[0].id
    assert changes == {
        'contacts': ([], ['Ops']),
        f'contacts_item_{contact_id}': ([], ['ops@example.test']),
    }
    assert log_fields == {
        f'contacts_item_{contact_id}': {'title': 'Contact list: Ops', 'type': 'list'},
    }


def test_populate_contacts_rename_only(db):
    affiliation = _create_affiliation(db, 'CERN')
    contact = _create_contact(db, affiliation, 'Old name', ['old@example.test'])

    changes, log_fields = util.populate_contacts(affiliation, [
        {'id': contact, 'name': 'New name', 'emails': ['old@example.test']},
    ])

    assert changes == {'contacts': (['Old name'], ['New name'])}
    assert log_fields == {}


def test_populate_contacts_emails_only(db):
    affiliation = _create_affiliation(db, 'CERN')
    contact = _create_contact(db, affiliation, 'Old name', ['old@example.test'])

    changes, log_fields = util.populate_contacts(affiliation, [
        {'id': contact, 'name': 'Old name', 'emails': ['new@example.test']},
    ])

    assert changes == {
        f'contacts_item_{contact.id}': (['old@example.test'], ['new@example.test']),
    }
    assert log_fields == {
        f'contacts_item_{contact.id}': {'title': 'Contact list: Old name', 'type': 'list'},
    }


def test_populate_contacts_rename_and_emails(db):
    affiliation = _create_affiliation(db, 'CERN')
    contact = _create_contact(db, affiliation, 'Old name', ['old@example.test'])

    changes, log_fields = util.populate_contacts(affiliation, [
        {'id': contact, 'name': 'New name', 'emails': ['new@example.test']},
    ])

    assert changes == {
        'contacts': (['Old name'], ['New name']),
        f'contacts_item_{contact.id}': (['old@example.test'], ['new@example.test']),
    }
    assert log_fields == {
        f'contacts_item_{contact.id}': {'title': 'Contact list: New name', 'type': 'list'},
    }


def test_populate_contacts_noop(db):
    affiliation = _create_affiliation(db, 'CERN')
    contact = _create_contact(db, affiliation, 'Old name', ['old@example.test'])

    changes, log_fields = util.populate_contacts(affiliation, [
        {'id': contact, 'name': 'Old name', 'emails': ['old@example.test']},
    ])

    assert changes == {}
    assert log_fields == {}


def test_populate_contacts_email_order_only(db):
    affiliation = _create_affiliation(db, 'CERN')
    contact = _create_contact(db, affiliation, 'Old name', ['a@example.test', 'b@example.test'])

    changes, log_fields = util.populate_contacts(affiliation, [
        {'id': contact, 'name': 'Old name', 'emails': ['b@example.test', 'a@example.test']},
    ])

    assert changes == {}
    assert log_fields == {}


def test_populate_contacts_deletes_omitted_contact(db):
    affiliation = _create_affiliation(db, 'CERN')
    contact = _create_contact(db, affiliation, 'Ops', ['ops@example.test'])
    payload = [{'id': None, 'name': 'New list', 'emails': ['new@example.test']}]

    changes, log_fields = util.populate_contacts(affiliation, payload)

    assert sorted(c.name for c in affiliation.contacts) == ['New list']
    new_contact = next(c for c in affiliation.contacts if c.name == 'New list')
    assert changes == {
        'contacts': (['Ops'], ['New list']),
        f'contacts_item_{contact.id}': (['ops@example.test'], []),
        f'contacts_item_{new_contact.id}': ([], ['new@example.test']),
    }
    assert log_fields == {
        f'contacts_item_{contact.id}': {'title': 'Contact list: Ops', 'type': 'list'},
        f'contacts_item_{new_contact.id}': {'title': 'Contact list: New list', 'type': 'list'},
    }


def test_populate_contacts_deletes_all_on_empty_payload(db):
    affiliation = _create_affiliation(db, 'CERN')
    contact = _create_contact(db, affiliation, 'Ops', ['ops@example.test'])

    changes, log_fields = util.populate_contacts(affiliation, [])

    assert affiliation.contacts == []
    assert changes == {
        'contacts': (['Ops'], []),
        f'contacts_item_{contact.id}': (['ops@example.test'], []),
    }
    assert log_fields == {
        f'contacts_item_{contact.id}': {'title': 'Contact list: Ops', 'type': 'list'},
    }


def test_populate_contacts_uses_unnamed_list_label_in_summary(db):
    affiliation = _create_affiliation(db, 'CERN')
    contact = _create_contact(db, affiliation, 'Named', ['ops@example.test'])

    changes, log_fields = util.populate_contacts(affiliation, [
        {'id': contact, 'name': '', 'emails': ['ops@example.test']},
    ])

    assert changes == {'contacts': (['Named'], ['(unnamed list)'])}
    assert log_fields == {}


def test_populate_contacts_mixed_add_remove_and_modify(db):
    affiliation = _create_affiliation(db, 'CERN')
    contact_keep = _create_contact(db, affiliation, 'Keep', ['keep@example.test'])
    contact_change = _create_contact(db, affiliation, 'Change', ['old@example.test'])
    contact_remove = _create_contact(db, affiliation, 'Remove', ['remove@example.test'])

    changes, log_fields = util.populate_contacts(affiliation, [
        {'id': contact_keep, 'name': 'Keep', 'emails': ['keep@example.test']},
        {'id': contact_change, 'name': 'Change renamed', 'emails': ['new@example.test']},
        {'id': None, 'name': 'Add', 'emails': ['add@example.test']},
    ])

    new_contact = next(c for c in affiliation.contacts if c.name == 'Add')
    assert changes == {
        'contacts': (['Change', 'Keep', 'Remove'], ['Add', 'Change renamed', 'Keep']),
        f'contacts_item_{contact_change.id}': (['old@example.test'], ['new@example.test']),
        f'contacts_item_{contact_remove.id}': (['remove@example.test'], []),
        f'contacts_item_{new_contact.id}': ([], ['add@example.test']),
    }
    assert log_fields == {
        f'contacts_item_{contact_change.id}': {'title': 'Contact list: Change renamed', 'type': 'list'},
        f'contacts_item_{contact_remove.id}': {'title': 'Contact list: Remove', 'type': 'list'},
        f'contacts_item_{new_contact.id}': {'title': 'Contact list: Add', 'type': 'list'},
    }


def test_populate_contacts_rejects_duplicate_ids(db):
    affiliation = _create_affiliation(db, 'CERN')
    contact = _create_contact(db, affiliation, 'Ops', ['ops@example.test'])

    with pytest.raises(UserValueError, match='unique'):
        util.populate_contacts(affiliation, [
            {'id': contact, 'name': 'Ops', 'emails': ['ops@example.test']},
            {'id': contact, 'name': 'Ops2', 'emails': ['ops2@example.test']},
        ])


def test_populate_contacts_rejects_contact_from_other_affiliation(db):
    affiliation = _create_affiliation(db, 'CERN')
    other_affiliation = _create_affiliation(db, 'Other')
    foreign_contact = _create_contact(db, other_affiliation, 'Ops', ['ops@example.test'])

    with pytest.raises(UserValueError, match='does not belong'):
        util.populate_contacts(affiliation, [
            {'id': foreign_contact, 'name': 'Ops', 'emails': ['ops@example.test']},
        ])


def test_populate_contacts_rejects_duplicate_names_in_db(db):
    affiliation = _create_affiliation(db, 'CERN')
    existing = _create_contact(db, affiliation, 'Ops', ['ops@example.test'])

    with pytest.raises(IntegrityError):
        util.populate_contacts(affiliation, [
            {'id': existing, 'name': 'Ops', 'emails': ['ops@example.test']},
            {'id': None, 'name': 'ops', 'emails': ['other@example.test']},
        ])
    db.session.rollback()
