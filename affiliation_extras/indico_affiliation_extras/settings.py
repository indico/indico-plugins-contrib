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
        # Whether affiliation focal points may manage the registrations of their own affiliations on
        # this event. Enabled by default; a full event manager can turn it off per event.
        'focal_point_management_enabled': True,
    },
)
