# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from sqlalchemy.orm import selectinload

from indico.core.db import db
from indico.modules.events import Event
from indico.modules.events.models.settings import EventSetting
from indico.modules.events.registration.models.form_fields import RegistrationFormField, RegistrationFormFieldData
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.registrations import Registration, RegistrationData
from indico.modules.users.models.affiliations import Affiliation
from indico.modules.users.models.users import User
from indico.util.caching import memoize_request

from indico_affiliation_extras.fields import RepresentationField
from indico_affiliation_extras.models.focal_points import FocalPoint
from indico_affiliation_extras.settings import event_settings
from indico_affiliation_extras.util import get_representation_affiliation_lists, get_representation_affiliations


def get_submitted_affiliation_ids(regform, data):
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
    if user is None:
        return set()
    return {entry.affiliation.id for entry in user.focal_point_entries if not entry.affiliation.is_deleted}


def get_event_catalog_affiliation_ids(event):
    ids = set()
    for affiliation_list in get_representation_affiliation_lists(event):
        ids.update(affiliation.id for affiliation in get_representation_affiliations(affiliation_list))
    return ids


def get_event_catalog_focal_points(event, affiliation_ids=None):
    if affiliation_ids is None:
        affiliation_ids = get_event_catalog_affiliation_ids(event)
    if not affiliation_ids:
        return set()
    return set(
        User.query
        .join(FocalPoint, FocalPoint.user_id == User.id)
        .options(
            selectinload('focal_point_entries').joinedload('affiliation'),
        )
        .filter(FocalPoint.affiliation_id.in_(affiliation_ids), ~User.is_deleted)
    )


def focal_affiliations_for_event(user, event):
    focal_ids = get_focal_affiliation_ids(user)
    if not focal_ids:
        return set()
    return focal_ids & get_event_catalog_affiliation_ids(event)


def _representation_data_query():
    return (
        RegistrationData.query
        .join(RegistrationData.field_data)
        .join(RegistrationFormFieldData.field)
        .filter(
            RegistrationFormField.is_visible,
            RegistrationFormField.input_type == RepresentationField.name,
        )
    )


@memoize_request
def get_registrations_focal_points(regform, registration_ids):
    affiliation_ids = get_event_catalog_affiliation_ids(regform.event)
    if not affiliation_ids:
        return {}
    representation_id = db.cast(RegistrationData.data['affiliation']['id'].astext, db.Integer)
    query = (
        _representation_data_query()
        .with_entities(RegistrationData.registration_id, User)
        .join(RegistrationData.registration)
        .join(Affiliation, Affiliation.id == representation_id)
        .join(FocalPoint, FocalPoint.affiliation_id == Affiliation.id)
        .join(FocalPoint.user)
        .filter(
            Registration.registration_form_id == regform.id,
            Registration.id.in_(registration_ids),
            ~Registration.is_deleted,
            Affiliation.id.in_(affiliation_ids),
            ~Affiliation.is_deleted,
            ~User.is_deleted,
        )
        .distinct()
    )
    focal_points = {}
    for registration_id, user in query:
        focal_points.setdefault(registration_id, set()).add(user)
    return focal_points


def _focal_match_criterion(focal_ids):
    if not focal_ids:
        return db.false()
    representation_id = db.cast(RegistrationData.data['affiliation']['id'].astext, db.Integer)
    return (
        _representation_data_query()
        .filter(
            RegistrationData.registration_id == Registration.id,
            representation_id.in_(focal_ids),
        )
        .exists()
    )


def focal_list_criterion(user, event):
    return _focal_match_criterion(focal_affiliations_for_event(user, event))


def focal_event_ids(user, dt=None):
    """A superset: the caller still applies the per-event catalog scope (``is_scoped_focal_point``)."""
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
