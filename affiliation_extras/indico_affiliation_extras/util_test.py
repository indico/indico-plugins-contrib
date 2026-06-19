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
from indico.modules.categories.models.categories import Category
from indico.modules.users.models.affiliations import Affiliation

from indico_affiliation_extras import util
from indico_affiliation_extras.models.catalogs import AffiliationCatalog
from indico_affiliation_extras.models.contacts import AffiliationContactList
from indico_affiliation_extras.models.groups import AffiliationGroup
from indico_affiliation_extras.models.lists import AffiliationList
from indico_affiliation_extras.models.tags import AffiliationTag
from indico_affiliation_extras.settings import category_settings, event_settings


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


def _create_group(db, name, code=None):
    group = AffiliationGroup(name=name, code=code or name.lower())
    db.session.add(group)
    db.session.flush()
    return group


def _create_tag(db, name, code=None, color='red'):
    tag = AffiliationTag(name=name, code=code or name.lower(), color=color)
    db.session.add(tag)
    db.session.flush()
    return tag


def _create_catalog(db, *, category=None, event=None, name='Catalog'):
    if category is None and event is None:
        category = Category.get_root()
    catalog = AffiliationCatalog(name=name, category=category, event=event)
    db.session.add(catalog)
    db.session.flush()
    return catalog


def _create_catalog_list(db, catalog, *, name='List', position=1, is_enabled=True, groups=(), tags=(), affiliations=()):
    list_obj = AffiliationList(
        catalog=catalog,
        name=name,
        position=position,
        is_enabled=is_enabled,
        groups=set(groups),
        tags=set(tags),
        affiliations=set(affiliations),
    )
    db.session.add(list_obj)
    db.session.flush()
    return list_obj


def _catalog_list_payload(
    *,
    list_link=None,
    name='List',
    position=1,
    is_enabled=True,
    groups=(),
    tags=(),
    affiliations=(),
):
    return {
        'list_link': list_link,
        'name': name,
        'position': position,
        'is_enabled': is_enabled,
        'groups': set(groups),
        'tags': set(tags),
        'affiliations': set(affiliations),
    }


_CATALOG_LIST_LOG_FIELD_META = {
    'name': ('Name', 'string'),
    'is_enabled': ('Enabled', 'bool'),
    'position': ('Position', 'number'),
    'groups': ('Groups', 'list'),
    'tags': ('Tags', 'list'),
    'affiliations': ('Affiliations', 'list'),
}


def _catalog_list_key(list_id, attr):
    return f'lists_item_{list_id}_{attr}'


def _catalog_list_log_fields(list_id, list_name, *attrs):
    return {
        _catalog_list_key(list_id, attr): {
            'title': f'List: {list_name} - {_CATALOG_LIST_LOG_FIELD_META[attr][0]}',
            'type': _CATALOG_LIST_LOG_FIELD_META[attr][1],
        }
        for attr in attrs
    }


def test_resolve_affiliations_includes_groups_and_tags(db):
    alpha = _create_affiliation(db, 'Alpha')
    beta = _create_affiliation(db, 'beta')
    delta = _create_affiliation(db, 'delta')

    group = _create_group(db, 'Group A', 'group-a')
    group.affiliations.add(beta)

    group_tag = _create_tag(db, 'Group tag', 'group-tag')
    group_tag.affiliations.add(_create_affiliation(db, 'Gamma'))
    group.tags.add(group_tag)

    direct_tag = _create_tag(db, 'Direct tag', 'direct-tag')
    direct_tag.affiliations.add(delta)

    resolved = util.resolve_affiliations({group}, {direct_tag}, {alpha})

    assert [affiliation.name for affiliation in resolved] == ['Alpha', 'beta', 'delta']


def test_resolve_affiliations_dedupes_sources(db):
    shared = _create_affiliation(db, 'Shared')
    other = _create_affiliation(db, 'Other')

    group = _create_group(db, 'Group B', 'group-b')
    tag = _create_tag(db, 'Tag B', 'tag-b')

    group.affiliations.add(shared)
    tag.affiliations.update({shared, other})
    group.tags.add(tag)

    resolved = util.resolve_affiliations({group}, {tag}, {shared})

    assert [affiliation.name for affiliation in resolved] == ['Other', 'Shared']


def test_resolve_affiliations_includes_tag_groups(db):
    tag_aff = _create_affiliation(db, 'Tag Only')
    group_aff = _create_affiliation(db, 'Group Only')

    group = _create_group(db, 'Group C', 'group-c')
    group.affiliations.add(group_aff)

    tag = _create_tag(db, 'Tag C', 'tag-c')
    tag.affiliations.add(tag_aff)
    tag.groups.add(group)

    resolved = util.resolve_affiliations(set(), {tag}, set())

    assert [affiliation.name for affiliation in resolved] == ['Group Only', 'Tag Only']


def test_resolve_affiliations_uses_constant_number_of_queries(db, count_queries):
    group_ids, tag_ids = [], []
    for i in range(4):
        group = _create_group(db, f'Group {i}', f'g{i}')
        group.affiliations.add(_create_affiliation(db, f'GAff {i}'))
        group_ids.append(group.id)
        tag = _create_tag(db, f'Tag {i}', f't{i}')
        tag.affiliations.add(_create_affiliation(db, f'TAff {i}'))
        tag_ids.append(tag.id)
    db.session.flush()
    db.session.expire_all()
    groups = set(AffiliationGroup.query.filter(AffiliationGroup.id.in_(group_ids)))
    tags = set(AffiliationTag.query.filter(AffiliationTag.id.in_(tag_ids)))

    with count_queries() as count:
        util.resolve_affiliations(groups, tags, set())

    # constant regardless of how many groups/tags are passed (no per-object lazy loads)
    assert count() <= 6


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


def test_populate_catalog_lists_adds_new_list_and_logs_details(db):
    catalog = _create_catalog(db, name='Catalog')
    affiliation = _create_affiliation(db, 'CERN')
    group = _create_group(db, 'Group A', 'group-a')
    tag = _create_tag(db, 'Tag A', 'tag-a')

    changes, log_fields = util.populate_catalog_lists(
        catalog,
        [
            _catalog_list_payload(
                name=' Representatives ',
                position=2,
                groups={group},
                tags={tag},
                affiliations={affiliation},
            ),
        ],
    )

    assert [lst.name for lst in catalog.lists] == ['Representatives']
    list_id = catalog.lists[0].id
    assert changes == {
        'lists': ([], ['Representatives']),
        _catalog_list_key(list_id, 'name'): ('', 'Representatives'),
        _catalog_list_key(list_id, 'is_enabled'): (None, True),
        _catalog_list_key(list_id, 'position'): (None, 2),
        _catalog_list_key(list_id, 'groups'): ([], ['group-a']),
        _catalog_list_key(list_id, 'tags'): ([], ['tag-a']),
        _catalog_list_key(list_id, 'affiliations'): ([], ['CERN']),
    }
    assert log_fields == _catalog_list_log_fields(
        list_id, 'Representatives', 'name', 'is_enabled', 'position', 'groups', 'tags', 'affiliations'
    )


def test_populate_catalog_lists_updates_existing_list_and_logs_details(db):
    catalog = _create_catalog(db, name='Catalog')
    old_affiliation = _create_affiliation(db, 'Alpha')
    new_affiliation = _create_affiliation(db, 'Beta')
    old_group = _create_group(db, 'Group A', 'group-a')
    new_group = _create_group(db, 'Group B', 'group-b')
    old_tag = _create_tag(db, 'Tag A', 'tag-a')
    new_tag = _create_tag(db, 'Tag B', 'tag-b')
    list_obj = _create_catalog_list(
        db,
        catalog,
        name='Representatives',
        position=1,
        is_enabled=True,
        groups={old_group},
        tags={old_tag},
        affiliations={old_affiliation},
    )

    changes, log_fields = util.populate_catalog_lists(
        catalog,
        [
            _catalog_list_payload(
                list_link=list_obj,
                name='Representatives',
                position=2,
                is_enabled=False,
                groups={new_group},
                tags={new_tag},
                affiliations={new_affiliation},
            ),
        ],
    )

    assert list_obj.position == 2
    assert not list_obj.is_enabled
    assert changes == {
        _catalog_list_key(list_obj.id, 'is_enabled'): (True, False),
        _catalog_list_key(list_obj.id, 'position'): (1, 2),
        _catalog_list_key(list_obj.id, 'groups'): (['group-a'], ['group-b']),
        _catalog_list_key(list_obj.id, 'tags'): (['tag-a'], ['tag-b']),
        _catalog_list_key(list_obj.id, 'affiliations'): (['Alpha'], ['Beta']),
    }
    assert log_fields == _catalog_list_log_fields(
        list_obj.id, 'Representatives', 'is_enabled', 'position', 'groups', 'tags', 'affiliations'
    )


def test_populate_catalog_lists_noop(db):
    catalog = _create_catalog(db, name='Catalog')
    affiliation = _create_affiliation(db, 'CERN')
    group = _create_group(db, 'Group A', 'group-a')
    tag = _create_tag(db, 'Tag A', 'tag-a')
    list_obj = _create_catalog_list(
        db,
        catalog,
        name='Representatives',
        position=1,
        is_enabled=True,
        groups={group},
        tags={tag},
        affiliations={affiliation},
    )

    changes, log_fields = util.populate_catalog_lists(
        catalog,
        [
            _catalog_list_payload(
                list_link=list_obj,
                name='Representatives',
                position=1,
                is_enabled=True,
                groups={group},
                tags={tag},
                affiliations={affiliation},
            ),
        ],
    )

    assert changes == {}
    assert log_fields == {}


def test_populate_catalog_lists_deletes_omitted_list(db):
    catalog = _create_catalog(db, name='Catalog')
    affiliation = _create_affiliation(db, 'CERN')
    list_obj = _create_catalog_list(db, catalog, name='Representatives', affiliations={affiliation})

    changes, log_fields = util.populate_catalog_lists(catalog, [])

    assert db.session.get(AffiliationList, list_obj.id) is None
    assert changes == {
        'lists': (['Representatives'], []),
        _catalog_list_key(list_obj.id, 'name'): ('Representatives', ''),
        _catalog_list_key(list_obj.id, 'is_enabled'): (True, None),
        _catalog_list_key(list_obj.id, 'position'): (1, None),
        _catalog_list_key(list_obj.id, 'affiliations'): (['CERN'], []),
    }
    assert log_fields == _catalog_list_log_fields(
        list_obj.id, 'Representatives', 'name', 'is_enabled', 'position', 'affiliations'
    )


def test_populate_catalog_lists_rejects_list_from_other_catalog(db):
    catalog = _create_catalog(db, name='Catalog')
    other_catalog = _create_catalog(db, name='Other catalog')
    affiliation = _create_affiliation(db, 'CERN')
    foreign_list = _create_catalog_list(db, other_catalog, name='Representatives', affiliations={affiliation})

    with pytest.raises(UserValueError, match='does not belong'):
        util.populate_catalog_lists(
            catalog,
            [
                _catalog_list_payload(list_link=foreign_list, name='Representatives', affiliations={affiliation}),
            ],
        )


def test_get_inherited_catalogs_on_event_excludes_own_catalogs(db, create_category, create_event):
    parent = create_category(title='Parent')
    child = create_category(title='Child', parent=parent)
    event = create_event(category=child)

    parent_catalog = _create_catalog(db, category=parent, name='Parent catalog')
    child_catalog = _create_catalog(db, category=child, name='Child catalog')
    _create_catalog(db, event=event, name='Event catalog')

    inherited_ids = {catalog.id for catalog in util.get_inherited_catalogs(event)}
    assert inherited_ids == {parent_catalog.id, child_catalog.id}


def test_get_default_catalog_on_event_uses_explicit_override(db, create_category, create_event):
    category = create_category(title='Child')
    event = create_event(category=category)

    category_default = _create_catalog(db, category=category, name='Category default')
    event_default = _create_catalog(db, event=event, name='Event default')
    category_settings.set(category, 'default_catalog_id', category_default.id)
    event_settings.set(event, 'default_catalog_id', event_default.id)

    assert util.get_default_catalog(event).id == event_default.id


def test_get_default_catalog_on_event_falls_back_to_category(db, create_category, create_event):
    category = create_category(title='Child')
    event = create_event(category=category)

    category_default = _create_catalog(db, category=category, name='Category default')
    category_settings.set(category, 'default_catalog_id', category_default.id)
    event_settings.set(event, 'default_catalog_id', None)

    assert util.get_default_catalog(event).id == category_default.id


def test_get_default_catalog_on_event_only_inherited_ignores_event_default(db, create_category, create_event):
    category = create_category(title='Child')
    event = create_event(category=category)

    category_default = _create_catalog(db, category=category, name='Category default')
    event_default = _create_catalog(db, event=event, name='Event default')
    category_settings.set(category, 'default_catalog_id', category_default.id)
    event_settings.set(event, 'default_catalog_id', event_default.id)

    assert util.get_default_catalog(event, only_inherited=True).id == category_default.id


def test_get_representation_affiliation_lists_uses_effective_default_catalog(db, create_category, create_event):
    category = create_category(title='Category')
    event = create_event(category=category)
    category_catalog = _create_catalog(db, category=category, name='Category default')
    event_catalog = _create_catalog(db, event=event, name='Event default')
    event_settings.set(event, 'default_catalog_id', event_catalog.id)
    category_settings.set(category, 'default_catalog_id', category_catalog.id)
    _create_catalog_list(db, event_catalog, name='Enabled event list', position=2, is_enabled=True)
    _create_catalog_list(db, event_catalog, name='Disabled event list', position=1, is_enabled=False)
    _create_catalog_list(db, category_catalog, name='Category list', position=1, is_enabled=True)

    affiliation_lists = util.get_representation_affiliation_lists(event, enabled_only=True)

    assert [item.name for item in affiliation_lists] == ['Enabled event list']


def test_get_representation_affiliation_list_rejects_disabled_or_missing(db, create_category, create_event):
    category = create_category(title='Category')
    event = create_event(category=category)
    catalog = _create_catalog(db, category=category, name='Default')
    category_settings.set(category, 'default_catalog_id', catalog.id)
    enabled_list = _create_catalog_list(db, catalog, name='Enabled', is_enabled=True)
    disabled_list = _create_catalog_list(db, catalog, name='Disabled', is_enabled=False)

    assert util.get_representation_affiliation_list(event, enabled_list.id).id == enabled_list.id
    assert util.get_representation_affiliation_list(event, disabled_list.id) is None
    assert util.get_representation_affiliation_list(event, 999999) is None


def test_get_representation_affiliations_resolves_groups_tags_and_direct_members(db):
    alpha = _create_affiliation(db, 'Alpha')
    beta = _create_affiliation(db, 'Beta')
    gamma = _create_affiliation(db, 'Gamma')
    group = _create_group(db, 'Group', 'group')
    tag = _create_tag(db, 'Tag', 'tag')
    group.affiliations.add(beta)
    tag.affiliations.add(gamma)
    tag.groups.add(group)
    catalog = _create_catalog(db, name='Catalog')
    affiliation_list = _create_catalog_list(
        db,
        catalog,
        name='Representatives',
        groups={group},
        tags={tag},
        affiliations={alpha},
    )

    resolved = util.get_representation_affiliations(affiliation_list)

    assert [item.name for item in resolved] == ['Alpha', 'Beta', 'Gamma']


def test_get_representation_affiliation_filters_limits_to_affiliation_list(db):
    allowed = _create_affiliation(db, 'Allowed')
    blocked = _create_affiliation(db, 'Blocked')
    catalog = _create_catalog(db, name='Catalog')
    affiliation_list = _create_catalog_list(db, catalog, affiliations={allowed})

    filters = util.get_representation_affiliation_filters({'affiliation_list': affiliation_list})
    results = Affiliation.query.filter(Affiliation.id.in_([allowed.id, blocked.id]), *filters).all()

    assert {item.id for item in results} == {allowed.id}


def test_get_representation_affiliation_filters_ignores_context_without_affiliation_list():
    assert util.get_representation_affiliation_filters({}) == []


def test_get_representation_affiliation_filters_returns_no_matches_for_empty_affiliation_list(db):
    affiliation = _create_affiliation(db, 'CERN')
    catalog = _create_catalog(db, name='Catalog')
    affiliation_list = _create_catalog_list(db, catalog)

    filters = util.get_representation_affiliation_filters({'affiliation_list': affiliation_list})
    results = Affiliation.query.filter(Affiliation.id == affiliation.id, *filters).all()

    assert results == []


def _create_affiliation_in(db, name, country_code):
    affiliation = _create_affiliation(db, name)
    affiliation.country_code = country_code
    db.session.flush()
    return affiliation


def test_get_extended_affiliation_filters_by_country(db):
    de = _create_affiliation_in(db, 'Berlin Uni', 'DE')
    fr = _create_affiliation_in(db, 'Paris Uni', 'FR')

    filters = util.get_extended_affiliation_filters({'country_code': 'DE'})
    results = Affiliation.query.filter(Affiliation.id.in_([de.id, fr.id]), *filters).all()

    assert {item.id for item in results} == {de.id}


def test_get_extended_affiliation_filters_by_tag(db):
    tagged = _create_affiliation(db, 'Tagged')
    other = _create_affiliation(db, 'Other')
    tag = _create_tag(db, 'Tag', 'tag')
    tag.affiliations.add(tagged)
    db.session.flush()

    filters = util.get_extended_affiliation_filters({'tag_ids': [tag.id]})
    results = Affiliation.query.filter(Affiliation.id.in_([tagged.id, other.id]), *filters).all()

    assert {item.id for item in results} == {tagged.id}


def test_get_extended_affiliation_filters_by_group_tag(db):
    grouped = _create_affiliation(db, 'Grouped')
    tagged = _create_affiliation(db, 'Tagged')
    other = _create_affiliation(db, 'Other')
    group = _create_group(db, 'Group', 'group')
    tag = _create_tag(db, 'Tag', 'tag')
    group.affiliations.add(grouped)
    group.tags.add(tag)
    tag.affiliations.add(tagged)
    db.session.flush()

    filters = util.get_extended_affiliation_filters({'tag_ids': [tag.id]})
    results = Affiliation.query.filter(Affiliation.id.in_([grouped.id, tagged.id, other.id]), *filters).all()

    assert {item.id for item in results} == {grouped.id, tagged.id}


def test_get_extended_affiliation_filters_by_group(db):
    grouped = _create_affiliation(db, 'Grouped')
    other = _create_affiliation(db, 'Other')
    group = _create_group(db, 'Group', 'group')
    group.affiliations.add(grouped)
    db.session.flush()

    filters = util.get_extended_affiliation_filters({'group_ids': [group.id]})
    results = Affiliation.query.filter(Affiliation.id.in_([grouped.id, other.id]), *filters).all()

    assert {item.id for item in results} == {grouped.id}


def test_get_extended_affiliation_filters_combines_filters_with_and(db):
    match = _create_affiliation_in(db, 'Match', 'DE')
    wrong_country = _create_affiliation_in(db, 'Wrong country', 'FR')
    untagged = _create_affiliation_in(db, 'Untagged', 'DE')
    tag = _create_tag(db, 'Tag', 'tag')
    tag.affiliations.update({match, wrong_country})
    db.session.flush()

    filters = util.get_extended_affiliation_filters({'country_code': 'DE', 'tag_ids': [tag.id]})
    ids = [match.id, wrong_country.id, untagged.id]
    results = Affiliation.query.filter(Affiliation.id.in_(ids), *filters).all()

    assert {item.id for item in results} == {match.id}


def test_get_extended_affiliation_filters_ignores_empty_context():
    assert util.get_extended_affiliation_filters({}) == []
