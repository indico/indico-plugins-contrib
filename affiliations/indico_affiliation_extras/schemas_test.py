# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import importlib
import sys
import types

import pytest
from marshmallow import ValidationError


@pytest.fixture
def affiliation_extra_attrs_args(monkeypatch):
    dummy = types.ModuleType('indico.modules.users.schemas')

    class DummyAffiliationSchema:
        def __init__(self, *args, **kwargs):
            pass

        class Meta:
            fields = ()

    dummy.AffiliationSchema = DummyAffiliationSchema
    monkeypatch.setitem(sys.modules, 'indico.modules.users.schemas', dummy)
    sys.modules.pop('indico_affiliation_extras.schemas', None)
    schemas = importlib.import_module('indico_affiliation_extras.schemas')
    yield schemas.AffiliationExtraAttrsArgs
    sys.modules.pop('indico_affiliation_extras.schemas', None)


def test_contact_lists_missing_allowed(affiliation_extra_attrs_args):
    data = affiliation_extra_attrs_args().load({})
    assert 'contact_lists' not in data


def test_contact_lists_empty_allowed(affiliation_extra_attrs_args):
    data = affiliation_extra_attrs_args().load({'contact_lists': []})
    assert data['contact_lists'] == []


def test_contact_list_emails_required(affiliation_extra_attrs_args):
    schema = affiliation_extra_attrs_args()
    with pytest.raises(ValidationError) as excinfo:
        schema.load({'contact_lists': [{'id': None, 'name': 'Ops', 'emails': []}]})
    errors = excinfo.value.messages['contact_lists'][0]
    assert 'emails' in errors


def test_contact_list_emails_valid(affiliation_extra_attrs_args):
    data = affiliation_extra_attrs_args().load({
        'contact_lists': [{'id': None, 'name': 'Ops', 'emails': ['ops@example.test']}]
    })
    assert data['contact_lists'][0]['emails'] == ['ops@example.test']
