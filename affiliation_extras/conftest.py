# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest

from indico.core.plugins import IndicoPlugin


@pytest.fixture(autouse=True)
def _plugin_manifest(mocker):
    """Mock the plugin's webpack manifest.

    Plugin assets are not built when running tests, so ``IndicoPlugin.manifest``
    returns ``None`` and any page that injects a plugin bundle raises a
    ``RuntimeError``. Indico core mocks its own manifest the same way in
    ``make_test_client``; we do the same for plugin bundles here.
    """
    mocker.patch.object(IndicoPlugin, 'manifest')
