# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import math

from flask import request

from indico.modules.users.controllers import RHUserBase

from indico_my_registrations.util import get_past_query, get_upcoming_query
from indico_my_registrations.views import WPMyRegistrations


def _paginate(query, page_arg):
    page = request.args.get(page_arg, 1, type=int)
    page = max(1, page)
    total = query.count()
    last_page = max(1, math.ceil(total / 25))
    page = min(page, last_page)
    return query.paginate(page=page)


class RHMyRegistrations(RHUserBase):
    """List a user's registrations, split into upcoming and past sections."""

    def _process(self):
        upcoming = _paginate(get_upcoming_query(self.user), 'upcoming_page')
        past = _paginate(get_past_query(self.user), 'past_page')
        return WPMyRegistrations.render_template(
            'dashboard.html',
            'my_registrations',
            user=self.user,
            upcoming=upcoming,
            past=past,
        )
