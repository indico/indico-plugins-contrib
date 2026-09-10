# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from datetime import datetime
from operator import itemgetter

import pytest
import pytz

from indico.core.config import config
from indico.modules.users.models.affiliations import Affiliation


pytest_plugins = ['indico.testing.fixtures.oauth', 'indico.testing.fixtures.contribution',
                  'indico.testing.fixtures.person', 'indico.testing.fixtures.session',
                  'indico.testing.fixtures.timetable', 'indico.testing.fixtures.storage',
                  'indico.testing.fixtures.rb', 'indico.testing.fixtures.abstract',
                  'indico.testing.fixtures.paper',
                  'indico.modules.events.registration.testing.fixtures']

SCOPES = ['read:everything', 'read:legacy_api', 'registrants']


@pytest.fixture
def token_headers(dummy_personal_token):
    dummy_personal_token.scopes = SCOPES
    return {'Authorization': f'Bearer {dummy_personal_token._plaintext_token}'}


@pytest.fixture
def dummy_affiliation(db, dummy_user):
    affiliation = Affiliation(name='ACME', code='ACM', alt_names=['Acme Inc'], street='1 Main street',
                              postcode='1211', city='Geneva', country_code='CH', meta={'source': 'test'})
    db.session.add(affiliation)
    dummy_user.affiliation_link = affiliation
    dummy_user.affiliation = affiliation.name
    db.session.flush()
    return affiliation


@pytest.fixture
def outsider(create_user):
    return create_user(42)


@pytest.fixture
def outsider_headers(db, dummy_personal_token, outsider):
    dummy_personal_token.user = outsider
    dummy_personal_token.scopes = SCOPES
    db.session.flush()
    return {'Authorization': f'Bearer {dummy_personal_token._plaintext_token}'}


@pytest.fixture
def indico_api(test_client, token_headers):
    def _get(url):
        resp = test_client.get(url, headers=token_headers)
        assert resp.status_code == 200
        return resp.json

    return _get


@pytest.fixture
def as_legacy_date():
    tz = pytz.timezone(config.DEFAULT_TIMEZONE)

    def _convert(value):
        if value is None:
            return None
        local = datetime.fromisoformat(value).astimezone(tz)
        return {'date': str(local.date()), 'time': str(local.time()), 'tz': str(local.tzinfo)}

    return _convert


MISSING = '<not served by the current API>'


def _reduce(mine, theirs):
    if isinstance(mine, dict) and isinstance(theirs, dict):
        return {key: (_reduce(value, theirs[key]) if key in theirs else MISSING) for key, value in mine.items()}
    if isinstance(mine, list) and isinstance(theirs, list) and len(mine) == len(theirs):
        return [_reduce(value, other) for value, other in zip(mine, theirs, strict=True)]
    return theirs


def _spec(renamed, key):
    spec = renamed.get(key, key)
    return spec if isinstance(spec, tuple) else (spec, None)


def _compare(ours, theirs, same, renamed, derived):
    assert set(ours) == set(same) | set(renamed) | set(derived)
    mine, expected = {}, {}
    for key in same:
        mine[key] = ours[key]
        expected[key] = theirs.get(key, MISSING)
    for key in renamed:
        their_key, convert = _spec(renamed, key)
        mine[key] = convert(ours[key]) if convert else ours[key]
        expected[key] = theirs.get(their_key, MISSING)
    for key, compute in derived.items():
        mine[key] = ours[key]
        expected[key] = compute(theirs)
    assert mine == {key: _reduce(mine[key], value) for key, value in expected.items()}


@pytest.fixture
def same_json():
    def _same(ours, theirs, same=(), renamed=None, derived=None):
        _compare(ours, theirs, same, renamed or {}, derived or {})

    return _same


def _key_getters(renamed, key):
    if callable(key):
        return key, key
    their_key, convert = _spec(renamed, key)
    ours = (lambda obj: convert(obj[key])) if convert else itemgetter(key)
    return ours, itemgetter(their_key)


@pytest.fixture
def same_json_list():
    def _same(ours, theirs, same=(), renamed=None, derived=None, key='id'):
        renamed = renamed or {}
        our_key, their_key = _key_getters(renamed, key)
        theirs_by_key = {their_key(obj): obj for obj in theirs}
        assert len(theirs_by_key) == len(theirs) == len(ours)
        for obj in ours:
            _compare(obj, theirs_by_key[our_key(obj)], same, renamed, derived or {})

    return _same


@pytest.fixture
def rename_keys():
    def _rename(mapping):
        def convert(value):
            if isinstance(value, list):
                return [convert(item) for item in value]
            return {mapping.get(key, key): item for key, item in value.items()}

        return convert

    return _rename
