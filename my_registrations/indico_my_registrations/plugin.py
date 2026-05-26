# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from flask import session

from indico.core import signals
from indico.core.plugins import IndicoPlugin, url_for_plugin
from indico.web.menu import SideMenuItem

from indico_my_registrations import _
from indico_my_registrations.blueprint import blueprint
from indico_my_registrations.views import WPMyRegistrations


class MyRegistrationsPlugin(IndicoPlugin):
    """My Registrations

    Adds a user-profile dashboard listing the user's past and upcoming event
    registrations, paginated independently per section.
    """

    configurable = False

    def init(self):
        super().init()
        self.connect(signals.menu.items, self._extend_sidemenu, sender='user-profile-sidemenu')
        self.inject_bundle('main.css', WPMyRegistrations)

    def get_blueprints(self):
        return blueprint

    def _extend_sidemenu(self, sender, user, **kwargs):
        if not session.user or user.is_system:
            return
        yield SideMenuItem(
            'my_registrations',
            _('My Registrations'),
            url_for_plugin('my_registrations.list', user_id=user.id),
            45,
        )
