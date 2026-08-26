# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

# Focal-point access model: while enabled (opt-in per form, off by default), Indico grants the
# equivalent of `registration_edit` and `registration_moderation` to every focal point of a catalog
# affiliation via `acl.can_manage`, then bounds it with blacklist signals. The grant is dynamic (no
# per-user ACL) and a genuine grant always prevails; a manager turns it on or off per form.

from indico.util.user import iter_acl

from indico_affiliation_extras.fields import RepresentationField
from indico_affiliation_extras.focal_points import focal_affiliations_for_event
from indico_affiliation_extras.settings import event_settings


FOCAL_POINT_PERMISSIONS = ('registration_edit', 'registration_moderation')


def focal_point_management_enabled(regform):
    """Whether focal-point management is enabled on ``regform`` (off by default, opt-in per form)."""
    if not regform_has_representation_field(regform):
        return False
    enabled = event_settings.get(regform.event, 'focal_point_enabled_regform_ids')
    return regform.id in enabled


def set_focal_point_management_enabled(regform, enabled):
    """Turn focal-point management on or off for ``regform`` (persisted on its event)."""
    enabled_ids = set(event_settings.get(regform.event, 'focal_point_enabled_regform_ids'))
    if enabled:
        enabled_ids.add(regform.id)
    else:
        enabled_ids.discard(regform.id)
    event_settings.set(regform.event, 'focal_point_enabled_regform_ids', sorted(enabled_ids))


def regform_has_representation_field(regform):
    """Whether ``regform`` has an active representation field (the trigger for focal management)."""
    return any(field.input_type == RepresentationField.name for field in regform.active_fields)


def event_has_focal_managed_regform(event):
    """Whether the event has a non-deleted form with focal-point management enabled."""
    return any(
        focal_point_management_enabled(regform) for regform in event.registration_forms if not regform.is_deleted
    )


def has_genuine_registration_management(event, user):
    """Whether ``user`` holds a real registration grant (not the dynamic focal-point one)."""
    if user is None:
        return False
    if event.can_manage(user):
        return True
    return any(
        user in entry.principal
        and any(entry.has_management_permission(permission, explicit=True) for permission in FOCAL_POINT_PERMISSIONS)
        for entry in iter_acl(event.acl_entries)
    )


def is_scoped_focal_point(event, user):
    """Whether ``user`` manages this event's registrations only as an affiliation focal point."""
    if not focal_affiliations_for_event(user, event):
        return False
    if has_genuine_registration_management(event, user):
        return False
    return event_has_focal_managed_regform(event)
