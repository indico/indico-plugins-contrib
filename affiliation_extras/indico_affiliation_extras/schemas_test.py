# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest
from marshmallow import ValidationError

from indico.modules.users.models.affiliations import Affiliation


@pytest.fixture(autouse=True)
def _app_context(app):
    with app.app_context():
        yield


@pytest.fixture
def schemas(app):
    # Imported lazily so the full model registry is configured before the
    # SQLAlchemyAutoSchema definitions in this module introspect their models.
    from indico_affiliation_extras import schemas as module

    return module


def test_contact_lists_missing_allowed(schemas):
    data = schemas.AffiliationExtraAttrsArgs().load({})
    assert 'contact_lists' not in data


def test_contact_lists_empty_allowed(schemas):
    data = schemas.AffiliationExtraAttrsArgs().load({'contact_lists': []})
    assert data['contact_lists'] == []


def test_contact_list_emails_required(schemas):
    with pytest.raises(ValidationError) as excinfo:
        schemas.AffiliationExtraAttrsArgs().load({'contact_lists': [{'id': None, 'name': 'Ops', 'emails': []}]})
    assert 'emails' in excinfo.value.messages['contact_lists'][0]


def test_contact_list_emails_valid(schemas):
    data = schemas.AffiliationExtraAttrsArgs().load({
        'contact_lists': [{'id': None, 'name': 'Ops', 'emails': ['ops@example.test']}]
    })
    assert data['contact_lists'][0]['emails'] == ['ops@example.test']


def test_contact_lists_reject_duplicate_names(schemas):
    with pytest.raises(ValidationError, match='Contact list names must be unique'):
        schemas.AffiliationExtraAttrsArgs().load({'contact_lists': [
            {'id': None, 'name': 'Ops', 'emails': ['a@example.test']},
            {'id': None, 'name': 'ops', 'emails': ['b@example.test']},
        ]})


def test_catalog_requires_at_least_one_list(schemas):
    with pytest.raises(ValidationError):
        schemas.AffiliationCatalogArgs().load({'name': 'Catalog', 'lists': []})


def test_catalog_list_requires_members(schemas):
    with pytest.raises(ValidationError, match='at least one group, tag, or affiliation'):
        schemas.AffiliationCatalogArgs().load(
            {'name': 'Catalog', 'lists': [{'id': None, 'name': 'Empty', 'position': 1}]}
        )


def test_catalog_rejects_duplicate_list_names(schemas, db):
    affiliation = Affiliation(name='CERN')
    db.session.add(affiliation)
    db.session.flush()
    with pytest.raises(ValidationError, match='List names must be unique'):
        schemas.AffiliationCatalogArgs().load({
            'name': 'Catalog',
            'lists': [
                {'id': None, 'name': 'Members', 'position': 1, 'affiliations': [affiliation.id]},
                {'id': None, 'name': 'members', 'position': 2, 'affiliations': [affiliation.id]},
            ],
        })
