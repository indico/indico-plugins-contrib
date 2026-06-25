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
from indico.modules.events.registration.models.form_fields import RegistrationFormField, RegistrationFormFieldData
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.registrations import Registration, RegistrationData

from indico_affiliation_extras.fields import RepresentationField
from indico_affiliation_extras.util import get_representation_affiliation_lists, get_representation_affiliations


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
    """Return the affiliation ids ``user`` is a focal point for (excluding deleted ones).

    This is the *central* designation, independent of any event. Event-scoped reach is given by
    :func:`focal_affiliations_for_event`, which intersects this with the event's catalog.
    """
    if user is None:
        return set()
    return {affiliation.id for affiliation in user.focal_point_affiliations if not affiliation.is_deleted}


def get_event_catalog_affiliation_ids(event):
    """Return the affiliation ids reachable through the event's affiliation catalog.

    These are the affiliations a registration on the event can represent, resolved from the
    representation lists of the event's default catalog. They define the scope within which focal
    points operate: only affiliations present in the catalog are managed by their focal points.
    """
    ids = set()
    for affiliation_list in get_representation_affiliation_lists(event):
        ids.update(affiliation.id for affiliation in get_representation_affiliations(affiliation_list))
    return ids


def focal_affiliations_for_event(user, event):
    """Return the affiliation ids ``user`` is a focal point for *within this event's catalog*.

    A focal point's reach on an event is bounded by the event's affiliation catalog: they manage
    only the affiliations that are both in the catalog and ones they are centrally designated for.
    Outside the catalog they have no reach, even when designated centrally. Empty when the event
    has no catalog or the user is a focal point for none of its affiliations.
    """
    focal_ids = get_focal_affiliation_ids(user)
    if not focal_ids:
        return set()
    return focal_ids & get_event_catalog_affiliation_ids(event)


def can_manage_registration(user, registration):
    """Whether ``user`` is a focal point for at least one of the registration's affiliations.

    Scoped to the registration's event catalog (see :func:`focal_affiliations_for_event`). This is
    the focal-point-specific check only; callers combine it with the regular ``event.can_manage``
    so that full managers are never restricted.
    """
    focal_ids = focal_affiliations_for_event(user, registration.event)
    if not focal_ids:
        return False
    return bool(focal_ids & get_registration_affiliation_ids(registration))


def _focal_match_criterion(focal_ids):
    """Build the SQL criterion selecting registrations that represent one of ``focal_ids``.

    A registration matches when its representation field points to one of the affiliations. The
    matching runs entirely in the database, so it stays efficient on events with many
    registrations. With no ids it matches nothing.
    """
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


def focal_list_criterion(user, event):
    """Select the registrations ``user`` may manage as a focal point on ``event``.

    A registration matches when its representation field points to an affiliation the user is a
    focal point for *and* that affiliation is in the event's catalog.
    """
    return _focal_match_criterion(focal_affiliations_for_event(user, event))


def focal_event_ids(user, limit=FOCAL_EVENT_LIMIT):
    """Return the ids of non-deleted events with a registration matching one of ``user``'s focal affiliations.

    This is a cheap cross-event prefilter keyed on the user's central designation (one ``EXISTS``
    query, no registrations loaded into Python). It is intentionally a superset: the event's
    catalog scope is applied per event by ``is_scoped_focal_point`` where these events are consumed
    (the dashboard), so an event whose catalog excludes the user's affiliations is dropped there.
    """
    focal_ids = get_focal_affiliation_ids(user)
    if not focal_ids:
        return set()
    criterion = _focal_match_criterion(focal_ids)
    query = (db.session.query(Event.id)
             .filter(~Event.is_deleted,
                     RegistrationForm.query
                     .filter(RegistrationForm.event_id == Event.id,
                             ~RegistrationForm.is_deleted,
                             Registration.query
                             .filter(Registration.registration_form_id == RegistrationForm.id,
                                     ~Registration.is_deleted,
                                     criterion)
                             .exists())
                     .exists())
             .limit(limit))
    return {event_id for (event_id,) in query}
