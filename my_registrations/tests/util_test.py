# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from datetime import timedelta

import pytest

from indico.modules.events.registration.models.registrations import Registration, RegistrationState
from indico.util.date_time import now_utc

from indico_my_registrations.util import get_past_query, get_upcoming_query


@pytest.fixture
def make_reg(db, dummy_user, create_event, create_regform):
    """Create a registration whose event ends at a given offset from now."""

    def _make(
        end_offset,
        *,
        start_offset=None,
        state=RegistrationState.complete,
        event_deleted=False,
        reg_deleted=False,
        title='evt',
    ):
        now = now_utc(exact=False)
        end_dt = now + end_offset
        start_dt = end_dt - timedelta(hours=1) if start_offset is None else now + start_offset
        event = create_event(start_dt=start_dt, end_dt=end_dt, title=title)
        if event_deleted:
            event.is_deleted = True
        regform = create_regform(event)
        reg = Registration(
            registration_form=regform,
            first_name='Guinea',
            last_name='Pig',
            currency='USD',
            email=dummy_user.email,
            user=dummy_user,
            state=state,
        )
        event.registrations.append(reg)
        if reg_deleted:
            reg.is_deleted = True
        db.session.flush()
        return reg

    return _make


def test_event_ending_in_future_is_upcoming(db, dummy_user, make_reg):
    reg = make_reg(timedelta(hours=1))
    upcoming = get_upcoming_query(dummy_user).all()
    past = get_past_query(dummy_user).all()
    assert reg in upcoming
    assert reg not in past


def test_event_ending_in_past_is_past(db, dummy_user, make_reg):
    reg = make_reg(-timedelta(hours=1))
    upcoming = get_upcoming_query(dummy_user).all()
    past = get_past_query(dummy_user).all()
    assert reg in past
    assert reg not in upcoming


def test_in_progress_event_is_upcoming(db, dummy_user, make_reg):
    # Event started yesterday, ends in 1h: still ongoing → upcoming
    reg = make_reg(timedelta(hours=1), start_offset=-timedelta(days=1))
    assert reg in get_upcoming_query(dummy_user).all()


def test_upcoming_ordered_ascending_by_start_dt(db, dummy_user, make_reg):
    far = make_reg(timedelta(days=10), title='far')
    soon = make_reg(timedelta(days=1), title='soon')
    upcoming = get_upcoming_query(dummy_user).all()
    assert upcoming.index(soon) < upcoming.index(far)


def test_past_ordered_descending_by_start_dt(db, dummy_user, make_reg):
    older = make_reg(-timedelta(days=10), title='older')
    recent = make_reg(-timedelta(days=1), title='recent')
    past = get_past_query(dummy_user).all()
    assert past.index(recent) < past.index(older)


def test_excludes_deleted_event(db, dummy_user, make_reg):
    reg = make_reg(timedelta(hours=1), event_deleted=True)
    assert reg not in get_upcoming_query(dummy_user).all()
    assert reg not in get_past_query(dummy_user).all()


def test_excludes_deleted_registration(db, dummy_user, make_reg):
    reg = make_reg(timedelta(hours=1), reg_deleted=True)
    assert reg not in get_upcoming_query(dummy_user).all()
    assert reg not in get_past_query(dummy_user).all()


@pytest.mark.parametrize('state', list(RegistrationState))
def test_includes_all_states(db, dummy_user, make_reg, state):
    reg = make_reg(timedelta(hours=1), state=state)
    assert reg in get_upcoming_query(dummy_user).all()
