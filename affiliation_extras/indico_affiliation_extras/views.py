# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from indico.core.plugins import WPJinjaMixinPlugin
from indico.modules.categories.views import WPCategoryManagement
from indico.web.flask.util import url_for


class WPCategoryAffiliations(WPJinjaMixinPlugin, WPCategoryManagement):
    def _get_parent_category_breadcrumb_url(self, category, management=False):
        if not management:
            return category.url
        return url_for('plugin_affiliation_extras.manage_category_affiliations', category)
