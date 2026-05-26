# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from sqlalchemy.orm import joinedload

from indico.modules.events import Event
from indico.modules.events.registration.models.registrations import Registration
from indico.util.date_time import now_utc


def _base_query(user):
    return (
        user.registrations
        .filter(~Registration.is_deleted)
        .join(Registration.event)
        .filter(~Event.is_deleted)
        .options(
            joinedload(Registration.event).load_only(
                'id',
                'title',
                'start_dt',
                'end_dt',
                'timezone',
                'category_id',
                'protection_mode',
            ),
            joinedload(Registration.registration_form).load_only('id', 'title'),
        )
    )


def get_upcoming_query(user):
    """Return query for the user's upcoming (ongoing or future) registrations."""
    return _base_query(user).filter(Event.end_dt >= now_utc(False)).order_by(Event.start_dt.asc(), Event.id.asc())


def get_past_query(user):
    """Return query for the user's past registrations."""
    return _base_query(user).filter(Event.end_dt < now_utc(False)).order_by(Event.start_dt.desc(), Event.id.desc())
