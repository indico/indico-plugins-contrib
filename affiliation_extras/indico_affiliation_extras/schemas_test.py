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
        schema.load({'contact_lists': [{'id': None, 'name': 'Ops', 'emails': [], 'inactive_emails': []}]})
    errors = excinfo.value.messages['contact_lists'][0]
    assert 'emails' in errors


def test_contact_list_emails_valid(affiliation_extra_attrs_args):
    data = affiliation_extra_attrs_args().load({
        'contact_lists': [{'id': None, 'name': 'Ops', 'emails': ['ops@example.test'], 'inactive_emails': []}]
    })
    assert data['contact_lists'][0]['emails'] == ['ops@example.test']


def test_contact_list_inactive_emails_required(affiliation_extra_attrs_args):
    schema = affiliation_extra_attrs_args()
    with pytest.raises(ValidationError) as excinfo:
        schema.load({'contact_lists': [{'id': None, 'name': 'Ops', 'emails': ['ops@example.test']}]})
    errors = excinfo.value.messages['contact_lists'][0]
    assert 'inactive_emails' in errors


def test_contact_list_inactive_emails_valid(affiliation_extra_attrs_args):
    data = affiliation_extra_attrs_args().load({
        'contact_lists': [
            {
                'id': None,
                'name': 'Ops',
                'emails': ['ops@example.test', 'off@example.test'],
                'inactive_emails': ['OFF@example.test'],
            }
        ]
    })
    assert data['contact_lists'][0]['inactive_emails'] == ['off@example.test']


def test_contact_list_all_emails_inactive_allowed(affiliation_extra_attrs_args):
    data = affiliation_extra_attrs_args().load({
        'contact_lists': [
            {
                'id': None,
                'name': 'Ops',
                'emails': ['off@example.test'],
                'inactive_emails': ['off@example.test'],
            }
        ]
    })
    assert data['contact_lists'][0]['emails'] == ['off@example.test']
    assert data['contact_lists'][0]['inactive_emails'] == ['off@example.test']


def test_contact_list_inactive_emails_must_belong_to_list(affiliation_extra_attrs_args):
    schema = affiliation_extra_attrs_args()
    with pytest.raises(ValidationError) as excinfo:
        schema.load({
            'contact_lists': [
                {
                    'id': None,
                    'name': 'Ops',
                    'emails': ['ops@example.test'],
                    'inactive_emails': ['off@example.test'],
                }
            ]
        })
    assert excinfo.value.messages == {'contact_lists': ['Inactive emails must belong to the contact list']}
