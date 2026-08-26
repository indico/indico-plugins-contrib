# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from indico.util.countries import get_countries
from indico.web.util import jsonify


class CountriesListMixin:
    """Mixin providing a country list endpoint.
    XXX: To delete when https://github.com/indico/indico/pull/7429 is merged.
    """

    def _process(self):
        return jsonify(list(get_countries().items()))
