# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from sqlalchemy.orm import contains_eager

from indico.modules.events import Event
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.registrations import Registration
from indico.util.date_time import now_utc


def _base_query(user):
    return (
        user.registrations
        .filter(~Registration.is_deleted)
        .join(Registration.event)
        .join(Registration.registration_form)
        .filter(~Event.is_deleted)
        .filter(~RegistrationForm.is_deleted)
        .options(
            contains_eager(Registration.event).load_only(
                'id',
                'title',
                'start_dt',
                'end_dt',
                'timezone',
                'category_id',
                'protection_mode',
            ),
            contains_eager(Registration.registration_form).load_only('id', 'title'),
        )
    )


def get_upcoming_query(user):
    """Return query for the user's upcoming (ongoing or future) registrations."""
    return _base_query(user).filter(Event.end_dt >= now_utc(False)).order_by(Event.start_dt.asc(), Event.id.asc())


def get_past_query(user):
    """Return query for the user's past registrations."""
    return _base_query(user).filter(Event.end_dt < now_utc(False)).order_by(Event.start_dt.desc(), Event.id.desc())
