# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from indico.core.plugins import IndicoPlugin


class AffiliationsPlugin(IndicoPlugin):
    """Extended Affiliations"""  # noqa: D400 Plugin name comes from docstring and it should not contain a period

    def init(self):
        super().init()
