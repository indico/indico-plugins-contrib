# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

# Focal-point access model: while enabled (the default on any event with a representation-bearing
# form), Indico grants the equivalent of `registration_edit` to every focal point of a catalog
# affiliation via `acl.can_manage`, then bounds it with blacklist signals. The grant is dynamic (no
# per-user ACL) and a genuine `registration_edit` always prevails; a manager can disable it per form.

from indico.util.user import iter_acl

from indico_affiliation_extras.fields import RepresentationField
from indico_affiliation_extras.focal_points import focal_affiliations_for_event
from indico_affiliation_extras.settings import event_settings


def focal_point_management_enabled(regform):
    """Whether focal-point management is enabled on ``regform`` (the default)."""
    disabled = event_settings.get(regform.event, 'focal_point_disabled_regform_ids')
    return regform.id not in disabled


def set_focal_point_management_enabled(regform, enabled):
    """Turn focal-point management on or off for ``regform`` (persisted on its event)."""
    disabled = set(event_settings.get(regform.event, 'focal_point_disabled_regform_ids'))
    if enabled:
        disabled.discard(regform.id)
    else:
        disabled.add(regform.id)
    event_settings.set(regform.event, 'focal_point_disabled_regform_ids', sorted(disabled))


def regform_has_representation_field(regform):
    """Whether ``regform`` has an active representation field (the trigger for focal management)."""
    return any(field.input_type == RepresentationField.name for field in regform.active_fields)


def event_has_focal_managed_regform(event):
    """Whether the event has a non-deleted representation form with focal-point management enabled."""
    return any(regform_has_representation_field(regform) and focal_point_management_enabled(regform)
               for regform in event.registration_forms if not regform.is_deleted)


def has_genuine_registration_edit(event, user):
    """Whether ``user`` holds a real ``registration_edit`` grant (not the dynamic focal-point one)."""
    if user is None:
        return False
    if event.can_manage(user):
        return True
    return any(user in entry.principal and entry.has_management_permission('registration_edit', explicit=True)
               for entry in iter_acl(event.acl_entries))


def is_scoped_focal_point(event, user):
    """Whether ``user`` manages this event's registrations only as an affiliation focal point."""
    if not focal_affiliations_for_event(user, event):
        return False
    if has_genuine_registration_edit(event, user):
        return False
    return event_has_focal_managed_regform(event)
