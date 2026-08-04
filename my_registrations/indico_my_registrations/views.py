# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from indico.core.plugins import WPJinjaMixinPlugin
from indico.modules.users.views import WPUser


class WPMyRegistrations(WPJinjaMixinPlugin, WPUser):
    pass
