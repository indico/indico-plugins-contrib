# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from wtforms import BooleanField

from indico.util.i18n import _
from indico.web.forms.base import IndicoForm
from indico.web.forms.widgets import SwitchWidget


class SettingsForm(IndicoForm):
    """Plugin settings form."""

    enabled = BooleanField(
        _('Enable registration form prefilling'),
        widget=SwitchWidget(),
        description=_(
            'Automatically prefill custom registration form fields with data '
            "from the user's most recent completed registration. Fields are "
            'matched by internal name and field type across all events.'
        )
    )
