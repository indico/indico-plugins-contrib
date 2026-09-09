# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from datetime import datetime

import pytest
import pytz

from indico.core.config import config


pytest_plugins = ['indico.testing.fixtures.oauth', 'indico.testing.fixtures.contribution',
                  'indico.testing.fixtures.person', 'indico.testing.fixtures.session',
                  'indico.testing.fixtures.timetable', 'indico.testing.fixtures.storage']

SCOPES = ['read:everything', 'read:legacy_api']


@pytest.fixture
def token_headers(dummy_personal_token):
    dummy_personal_token.scopes = SCOPES
    return {'Authorization': f'Bearer {dummy_personal_token._plaintext_token}'}


@pytest.fixture
def outsider_headers(db, dummy_personal_token, create_user):
    dummy_personal_token.user = create_user(42)
    dummy_personal_token.scopes = SCOPES
    db.session.flush()
    return {'Authorization': f'Bearer {dummy_personal_token._plaintext_token}'}


@pytest.fixture
def legacy_api(test_client, token_headers):
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
