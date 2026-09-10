# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from datetime import datetime

import pytest
import pytz
from parity import compare, compare_list
from parity import rename_keys as _rename_keys

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


@pytest.fixture
def same_json():
    return compare


@pytest.fixture
def same_json_list():
    return compare_list


@pytest.fixture
def rename_keys():
    return _rename_keys
