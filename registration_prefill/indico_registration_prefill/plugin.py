# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from flask import session

from indico.core import signals
from indico.core.plugins import IndicoPlugin
from indico.modules.events.registration.util import get_initial_form_values
from indico.util.signals import interceptable_sender

from indico_registration_prefill.forms import SettingsForm
from indico_registration_prefill.util import get_previous_registration_data


class RegistrationPrefillPlugin(IndicoPlugin):
    """Registration Prefill

    Automatically prefills registration form fields with data from
    the user's most recent completed registration.
    Fields are matched by internal name and field type across all events.
    """

    configurable = True
    settings_form = SettingsForm
    default_settings = {'enabled': True}

    def init(self):
        super().init()
        self.connect(
            signals.plugin.interceptable_function,
            self._inject_prefill_data,
            sender=interceptable_sender(get_initial_form_values),
        )

    def _inject_prefill_data(self, sender, func, args, ctx, **kwargs):
        """Intercept ``get_initial_form_values`` to merge prefill data.

        If the plugin is enabled and not in management mode, calls the original
        function and overlays values from the user's latest completed registration.
        For file/picture fields, forwards metadata via ``file_data`` when available.
        """
        if not self.settings.get('enabled') or args.arguments.get('management'):
            return
        original = func(*args.args, **args.kwargs)
        file_data = args.arguments.get('kwargs', {}).get('file_data')
        extra = get_previous_registration_data(args.arguments['regform'], session.user, file_data=file_data)
        return {**original, **extra}
