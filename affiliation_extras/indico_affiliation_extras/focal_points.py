# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from indico.core.db import db
from indico.modules.events import Event
from indico.modules.events.models.settings import EventSetting
from indico.modules.events.registration.models.form_fields import RegistrationFormField, RegistrationFormFieldData
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.registrations import Registration, RegistrationData
from indico.modules.users.models.users import User

from indico_affiliation_extras.fields import RepresentationField
from indico_affiliation_extras.models.focal_points import FocalPoint
from indico_affiliation_extras.settings import event_settings
from indico_affiliation_extras.util import get_representation_affiliation_lists, get_representation_affiliations


def get_submitted_affiliation_ids(regform, data):
    """Return the affiliation ids referenced by raw submitted registration ``data`` (create time)."""
    ids = set()
    for field in regform.active_fields:
        value = data.get(field.html_field_name)
        if not isinstance(value, dict):
            continue
        if field.input_type != RepresentationField.name:
            continue
        affiliation_id = (value.get('affiliation') or {}).get('id')
        if affiliation_id is not None:
            ids.add(affiliation_id)
    return ids


def get_focal_points(affiliation):
    return {entry.user for entry in affiliation.focal_point_entries}


def set_focal_points(affiliation, users):
    entries = {entry.user: entry for entry in affiliation.focal_point_entries}
    for user in users - entries.keys():
        affiliation.focal_point_entries.add(FocalPoint(user=user))
    for user, entry in entries.items():
        if user not in users:
            affiliation.focal_point_entries.discard(entry)


def merge_focal_points(target, source):
    target_affiliations = {entry.affiliation for entry in target.focal_point_entries}
    for entry in source.focal_point_entries:
        if entry.affiliation not in target_affiliations:
            target.focal_point_entries.add(FocalPoint(affiliation=entry.affiliation))
    source.focal_point_entries.clear()


def get_focal_affiliation_ids(user):
    """Return the affiliation ids ``user`` is centrally a focal point for (excluding deleted)."""
    if user is None:
        return set()
    return {entry.affiliation.id for entry in user.focal_point_entries if not entry.affiliation.is_deleted}


def get_event_catalog_affiliation_ids(event):
    """Return the affiliation ids reachable through the event's affiliation catalog."""
    ids = set()
    for affiliation_list in get_representation_affiliation_lists(event):
        ids.update(affiliation.id for affiliation in get_representation_affiliations(affiliation_list))
    return ids


def get_event_catalog_focal_points(event, affiliation_ids=None):
    """Return users who are focal points for affiliations in the event's affiliation catalog."""
    if affiliation_ids is None:
        affiliation_ids = get_event_catalog_affiliation_ids(event)
    if not affiliation_ids:
        return set()
    return set(
        User.query.join(FocalPoint, FocalPoint.user_id == User.id).filter(
            FocalPoint.affiliation_id.in_(affiliation_ids), ~User.is_deleted
        )
    )


def focal_affiliations_for_event(user, event):
    """Return ``user``'s focal affiliations that are also in this event's catalog."""
    focal_ids = get_focal_affiliation_ids(user)
    if not focal_ids:
        return set()
    return focal_ids & get_event_catalog_affiliation_ids(event)


def _focal_match_criterion(focal_ids):
    """Build the SQL criterion selecting registrations that represent one of ``focal_ids`` (none matches nothing)."""
    if not focal_ids:
        return db.false()
    representation_id = db.cast(RegistrationData.data['affiliation']['id'].astext, db.Integer)
    return db.exists().where(
        db.and_(
            RegistrationData.registration_id == Registration.id,
            RegistrationData.field_data_id == RegistrationFormFieldData.id,
            RegistrationFormFieldData.field_id == RegistrationFormField.id,
            ~RegistrationFormField.is_deleted,
            RegistrationFormField.is_enabled,
            RegistrationFormField.input_type == RepresentationField.name,
            representation_id.in_(focal_ids),
        )
    )


def focal_list_criterion(user, event):
    """Select the registrations ``user`` may manage as a focal point on ``event``."""
    return _focal_match_criterion(focal_affiliations_for_event(user, event))


def focal_event_ids(user, dt=None):
    """Ids of non-deleted events ending on/after ``dt`` with a focal-managed form matching ``user``'s affiliations.

    A superset: the per-event catalog scope is applied later by the caller (via ``is_scoped_focal_point``).
    """
    focal_ids = get_focal_affiliation_ids(user)
    if not focal_ids:
        return set()
    enabled = (
        EventSetting.query
        .join(Event, Event.id == EventSetting.event_id)
        .filter(
            EventSetting.module == event_settings.module,
            EventSetting.name == 'focal_point_enabled_regform_ids',
            ~Event.is_deleted,
            Event.ends_after(dt),
        )
        .with_entities(EventSetting.value)
    )
    regform_ids = {regform_id for (value,) in enabled for regform_id in value}
    if not regform_ids:
        return set()
    query = db.session.query(RegistrationForm.event_id).filter(
        RegistrationForm.id.in_(regform_ids),
        ~RegistrationForm.is_deleted,
        Registration.query.filter(
            Registration.registration_form_id == RegistrationForm.id,
            ~Registration.is_deleted,
            _focal_match_criterion(focal_ids),
        ).exists(),
    )
    return {event_id for (event_id,) in query}
