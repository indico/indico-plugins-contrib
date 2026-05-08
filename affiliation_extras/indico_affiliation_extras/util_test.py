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

from indico_affiliation_extras import util
from indico_affiliation_extras.models.contacts import AffiliationContactList


EMAIL_IMAGE_URL_PREFIX = '/files/123e4567-e89b-12d3-a456-426614174000/download?token='


@pytest.fixture(autouse=True)
def _app_context(app):
    with app.app_context():
        yield


def test_get_token_from_src():
    token = 'abc123'
    src = f'https://example.test{EMAIL_IMAGE_URL_PREFIX}{token}'
    assert util.get_token_from_src(src) == token
    assert util.get_token_from_src(src + '&x=1') == token
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
        f'<img src="https://example.test{EMAIL_IMAGE_URL_PREFIX}t1" />'
        f'<img src="https://example.test{EMAIL_IMAGE_URL_PREFIX}t2" />'
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
        f'<img src="https://example.test{EMAIL_IMAGE_URL_PREFIX}dup" />'
        f'<img src="https://example.test{EMAIL_IMAGE_URL_PREFIX}dup" />'
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

    changes, log_fields = util.populate_contacts(
        affiliation,
        [
            {'id': None, 'name': 'Ops', 'emails': ['ops@example.test']},
        ],
    )

    assert [c.name for c in affiliation.contact_lists] == ['Ops']
    assert len(affiliation.contact_lists) == 1
    contact_id = affiliation.contact_lists[0].id
    assert changes == {
        'contact_lists': ([], ['Ops']),
        f'contact_lists_item_{contact_id}': ([], ['ops@example.test']),
    }
    assert log_fields == {
        f'contact_lists_item_{contact_id}': {'title': 'Contact list: Ops', 'type': 'list'},
    }


def test_populate_contacts_rename_only(db):
    affiliation = _create_affiliation(db, 'CERN')
    contact = _create_contact(db, affiliation, 'Old name', ['old@example.test'])

    changes, log_fields = util.populate_contacts(
        affiliation,
        [
            {'id': contact, 'name': 'New name', 'emails': ['old@example.test']},
        ],
    )

    assert changes == {'contact_lists': (['Old name'], ['New name'])}
    assert log_fields == {}


def test_populate_contacts_emails_only(db):
    affiliation = _create_affiliation(db, 'CERN')
    contact = _create_contact(db, affiliation, 'Old name', ['old@example.test'])

    changes, log_fields = util.populate_contacts(
        affiliation,
        [
            {'id': contact, 'name': 'Old name', 'emails': ['new@example.test']},
        ],
    )

    assert changes == {
        f'contact_lists_item_{contact.id}': (['old@example.test'], ['new@example.test']),
    }
    assert log_fields == {
        f'contact_lists_item_{contact.id}': {'title': 'Contact list: Old name', 'type': 'list'},
    }


def test_populate_contacts_rename_and_emails(db):
    affiliation = _create_affiliation(db, 'CERN')
    contact = _create_contact(db, affiliation, 'Old name', ['old@example.test'])

    changes, log_fields = util.populate_contacts(
        affiliation,
        [
            {'id': contact, 'name': 'New name', 'emails': ['new@example.test']},
        ],
    )

    assert changes == {
        'contact_lists': (['Old name'], ['New name']),
        f'contact_lists_item_{contact.id}': (['old@example.test'], ['new@example.test']),
    }
    assert log_fields == {
        f'contact_lists_item_{contact.id}': {'title': 'Contact list: New name', 'type': 'list'},
    }


def test_populate_contacts_noop(db):
    affiliation = _create_affiliation(db, 'CERN')
    contact = _create_contact(db, affiliation, 'Old name', ['old@example.test'])

    changes, log_fields = util.populate_contacts(
        affiliation,
        [
            {'id': contact, 'name': 'Old name', 'emails': ['old@example.test']},
        ],
    )

    assert changes == {}
    assert log_fields == {}


def test_populate_contacts_email_order_only(db):
    affiliation = _create_affiliation(db, 'CERN')
    contact = _create_contact(db, affiliation, 'Old name', ['a@example.test', 'b@example.test'])

    changes, log_fields = util.populate_contacts(
        affiliation,
        [
            {'id': contact, 'name': 'Old name', 'emails': ['b@example.test', 'a@example.test']},
        ],
    )

    assert changes == {}
    assert log_fields == {}


def test_populate_contacts_deletes_omitted_contact(db):
    affiliation = _create_affiliation(db, 'CERN')
    contact = _create_contact(db, affiliation, 'Ops', ['ops@example.test'])
    payload = [{'id': None, 'name': 'New list', 'emails': ['new@example.test']}]

    changes, log_fields = util.populate_contacts(affiliation, payload)

    assert sorted(c.name for c in affiliation.contact_lists) == ['New list']
    new_contact = next(c for c in affiliation.contact_lists if c.name == 'New list')
    assert changes == {
        'contact_lists': (['Ops'], ['New list']),
        f'contact_lists_item_{contact.id}': (['ops@example.test'], []),
        f'contact_lists_item_{new_contact.id}': ([], ['new@example.test']),
    }
    assert log_fields == {
        f'contact_lists_item_{contact.id}': {'title': 'Contact list: Ops', 'type': 'list'},
        f'contact_lists_item_{new_contact.id}': {'title': 'Contact list: New list', 'type': 'list'},
    }


def test_populate_contacts_deletes_all_on_empty_payload(db):
    affiliation = _create_affiliation(db, 'CERN')
    contact = _create_contact(db, affiliation, 'Ops', ['ops@example.test'])

    changes, log_fields = util.populate_contacts(affiliation, [])

    assert affiliation.contact_lists == []
    assert changes == {
        'contact_lists': (['Ops'], []),
        f'contact_lists_item_{contact.id}': (['ops@example.test'], []),
    }
    assert log_fields == {
        f'contact_lists_item_{contact.id}': {'title': 'Contact list: Ops', 'type': 'list'},
    }


def test_populate_contacts_uses_unnamed_list_label_in_summary(db):
    affiliation = _create_affiliation(db, 'CERN')
    contact = _create_contact(db, affiliation, 'Named', ['ops@example.test'])

    changes, log_fields = util.populate_contacts(
        affiliation,
        [
            {'id': contact, 'name': '', 'emails': ['ops@example.test']},
        ],
    )

    assert changes == {'contact_lists': (['Named'], ['(unnamed list)'])}
    assert log_fields == {}


def test_populate_contacts_mixed_add_remove_and_modify(db):
    affiliation = _create_affiliation(db, 'CERN')
    contact_keep = _create_contact(db, affiliation, 'Keep', ['keep@example.test'])
    contact_change = _create_contact(db, affiliation, 'Change', ['old@example.test'])
    contact_remove = _create_contact(db, affiliation, 'Remove', ['remove@example.test'])

    changes, log_fields = util.populate_contacts(
        affiliation,
        [
            {'id': contact_keep, 'name': 'Keep', 'emails': ['keep@example.test']},
            {'id': contact_change, 'name': 'Change renamed', 'emails': ['new@example.test']},
            {'id': None, 'name': 'Add', 'emails': ['add@example.test']},
        ],
    )

    new_contact = next(c for c in affiliation.contact_lists if c.name == 'Add')
    assert changes == {
        'contact_lists': (['Change', 'Keep', 'Remove'], ['Add', 'Change renamed', 'Keep']),
        f'contact_lists_item_{contact_change.id}': (['old@example.test'], ['new@example.test']),
        f'contact_lists_item_{contact_remove.id}': (['remove@example.test'], []),
        f'contact_lists_item_{new_contact.id}': ([], ['add@example.test']),
    }
    assert log_fields == {
        f'contact_lists_item_{contact_change.id}': {'title': 'Contact list: Change renamed', 'type': 'list'},
        f'contact_lists_item_{contact_remove.id}': {'title': 'Contact list: Remove', 'type': 'list'},
        f'contact_lists_item_{new_contact.id}': {'title': 'Contact list: Add', 'type': 'list'},
    }


def test_populate_contacts_rejects_duplicate_ids(db):
    affiliation = _create_affiliation(db, 'CERN')
    contact = _create_contact(db, affiliation, 'Ops', ['ops@example.test'])

    with pytest.raises(UserValueError, match='unique'):
        util.populate_contacts(
            affiliation,
            [
                {'id': contact, 'name': 'Ops', 'emails': ['ops@example.test']},
                {'id': contact, 'name': 'Ops2', 'emails': ['ops2@example.test']},
            ],
        )


def test_populate_contacts_rejects_contact_from_other_affiliation(db):
    affiliation = _create_affiliation(db, 'CERN')
    other_affiliation = _create_affiliation(db, 'Other')
    foreign_contact = _create_contact(db, other_affiliation, 'Ops', ['ops@example.test'])

    with pytest.raises(UserValueError, match='does not belong'):
        util.populate_contacts(
            affiliation,
            [
                {'id': foreign_contact, 'name': 'Ops', 'emails': ['ops@example.test']},
            ],
        )


def test_populate_contacts_rejects_duplicate_names_in_db(db):
    affiliation = _create_affiliation(db, 'CERN')
    existing = _create_contact(db, affiliation, 'Ops', ['ops@example.test'])

    with pytest.raises(IntegrityError):
        util.populate_contacts(
            affiliation,
            [
                {'id': existing, 'name': 'Ops', 'emails': ['ops@example.test']},
                {'id': None, 'name': 'ops', 'emails': ['other@example.test']},
            ],
        )
    db.session.rollback()
