# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from indico.modules.categories.settings import CategorySettingsProxy
from indico.modules.events.settings import EventSettingsProxy


category_settings = CategorySettingsProxy(
    'plugin_affiliation_extras',
    {
        'default_catalog_id': None,
    },
)

event_settings = EventSettingsProxy(
    'plugin_affiliation_extras',
    {
        'default_catalog_id': None,
        # Registration forms on which focal-point management has been turned off. Management is
        # enabled by default on every representation-bearing form; a full registration manager can
        # disable it per form from the form's management page, which adds its id here.
        'focal_point_disabled_regform_ids': [],
    },
)
