# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

# Focal-point matching: deciding which registrations a focal point may manage, based on the
# representation field(s) on the registration, which carry the affiliation being represented.

from indico.core.db import db
from indico.modules.events import Event
from indico.modules.events.registration.custom import CustomRegistrationListItem, RegistrationListColumn
from indico.modules.events.registration.models.form_fields import RegistrationFormField, RegistrationFormFieldData
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.registrations import Registration, RegistrationData
from indico.util.i18n import _

from indico_affiliation_extras.fields import RepresentationField


# Max number of events to show on a focal point's personal "Focal-point events" page.
FOCAL_EVENT_LIMIT = 25


def get_registration_affiliation_ids(registration):
    """Return the affiliation ids a registration represents.

    Scans the representation field(s) in the form, the only ones that carry the semantic of
    representing an affiliation. Free-text values (no affiliation ``id``) are ignored.
    """
    ids = set()
    for field in registration.registration_form.form_items:
        if (
            not field.is_field
            or field.is_deleted
            or (field.parent is not None and field.parent.is_deleted)
        ):
            continue
        registration_data = registration.data_by_field.get(field.id)
        if registration_data is None or not registration_data.data:
            continue
        if field.input_type != RepresentationField.name:
            continue
        affiliation_id = (registration_data.data.get('affiliation') or {}).get('id')
        if affiliation_id is not None:
            ids.add(affiliation_id)
    return ids


def get_submitted_affiliation_ids(regform, data):
    """Return the affiliation ids referenced by raw submitted registration ``data``.

    Mirrors :func:`get_registration_affiliation_ids` but reads the unsaved ``data`` dict (keyed by
    each field's ``html_field_name``) instead of a stored registration. Used at create time, before
    any registration exists. Free-text values (no affiliation ``id``) are ignored.
    """
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


def get_focal_affiliation_ids(user):
    """Return the affiliation ids ``user`` is a focal point for (excluding deleted ones)."""
    if user is None:
        return set()
    return {affiliation.id for affiliation in user.focal_point_affiliations if not affiliation.is_deleted}


def can_manage_registration(user, registration):
    """Whether ``user`` is a focal point for at least one of the registration's affiliations.

    This is the focal-point-specific check only; callers combine it with the regular
    ``event.can_manage`` so that full managers are never restricted.
    """
    focal_ids = get_focal_affiliation_ids(user)
    if not focal_ids:
        return False
    return bool(focal_ids & get_registration_affiliation_ids(registration))


def focal_list_criterion(user):
    """Build a filter that selects the registrations a user may manage as a focal point.

    A registration matches when its representation field points to an affiliation the user is a
    focal point for. The matching runs entirely in the database, so it stays efficient on events
    with many registrations.
    """
    focal_ids = get_focal_affiliation_ids(user)
    if not focal_ids:
        return db.false()
    representation_id = db.cast(RegistrationData.data['affiliation']['id'].astext, db.Integer)
    return db.exists().where(db.and_(
        RegistrationData.registration_id == Registration.id,
        RegistrationData.field_data_id == RegistrationFormFieldData.id,
        RegistrationFormFieldData.field_id == RegistrationFormField.id,
        ~RegistrationFormField.is_deleted,
        RegistrationFormField.input_type == RepresentationField.name,
        representation_id.in_(focal_ids),
    ))


def focal_event_ids(user, limit=FOCAL_EVENT_LIMIT):
    """Return the ids of non-deleted events with a registration matching one of ``user``'s focal affiliations.

    These are the events whose registrations :func:`focal_list_criterion` would let the user manage,
    used to populate the focal point's personal "Focal-point events" page. The whole thing is one
    ``EXISTS`` query (no registrations are loaded into Python).
    """
    focal_ids = get_focal_affiliation_ids(user)
    if not focal_ids:
        return set()
    query = (db.session.query(Event.id)
             .filter(~Event.is_deleted,
                     RegistrationForm.query
                     .filter(RegistrationForm.event_id == Event.id,
                             ~RegistrationForm.is_deleted,
                             Registration.query
                             .filter(Registration.registration_form_id == RegistrationForm.id,
                                     ~Registration.is_deleted,
                                     focal_list_criterion(user))
                             .exists())
                     .exists())
             .limit(limit))
    return {event_id for (event_id,) in query}


class RegisteredByListItem(CustomRegistrationListItem):
    """Reglist column showing who created each registration."""

    name = 'affiliation_extras_registered_by'
    title = _('Registered by')

    def load_data(self, registrations):
        rv = {}
        for registration in registrations:
            creator = registration.created_by
            if creator is None:
                continue
            rv[registration] = RegistrationListColumn(creator.full_name, creator.full_name)
        return rv
