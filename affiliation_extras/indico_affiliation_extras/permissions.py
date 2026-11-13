# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

# Focal points get the enabled `FOCAL_POINT_PERMISSIONS` dynamically via `acl.can_manage` (no ACL entry),
# bounded by the blacklist signals; any genuine registration grant prevails. The permissions are toggled
# per event because core grants and bounds them event-wide: the bounding filter is not permission-aware,
# so a per-form toggle of one permission would leak the other onto that form.

from indico.modules.events.registration import REGISTRATION_PERMISSIONS
from indico.util.user import iter_acl

from indico_affiliation_extras.fields import RepresentationField
from indico_affiliation_extras.focal_points import focal_affiliations_for_event
from indico_affiliation_extras.settings import event_settings


FOCAL_POINT_PERMISSIONS = ('registration_edit', 'registration_moderation')


def focal_point_management_enabled(regform):
    if not regform_has_representation_field(regform):
        return False
    enabled = event_settings.get(regform.event, 'focal_point_enabled_regform_ids')
    return regform.id in enabled


def set_focal_point_management_enabled(regform, enabled):
    enabled_ids = set(event_settings.get(regform.event, 'focal_point_enabled_regform_ids'))
    if enabled:
        enabled_ids.add(regform.id)
    else:
        enabled_ids.discard(regform.id)
    event_settings.set(regform.event, 'focal_point_enabled_regform_ids', sorted(enabled_ids))


def get_focal_point_permissions(event):
    permissions = set()
    if not event_settings.get(event, 'focal_point_editing_disabled'):
        permissions.add('registration_edit')
    if not event_settings.get(event, 'focal_point_moderation_disabled'):
        permissions.add('registration_moderation')
    return permissions


def set_focal_point_permissions(event, *, editing=None, moderation=None):
    """Turn focal-point permissions on or off for ``event``; ``None`` leaves one unchanged."""
    values = {'focal_point_editing_disabled': editing, 'focal_point_moderation_disabled': moderation}
    event_settings.set_multi(event, {name: not enabled for name, enabled in values.items() if enabled is not None})


def regform_has_representation_field(regform):
    return any(field.input_type == RepresentationField.name for field in regform.active_fields)


def event_has_focal_managed_regform(event):
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
        and any(entry.has_management_permission(permission, explicit=True) for permission in REGISTRATION_PERMISSIONS)
        for entry in iter_acl(event.acl_entries)
    )


def is_scoped_focal_point(event, user):
    if not focal_affiliations_for_event(user, event):
        return False
    if has_genuine_registration_management(event, user):
        return False
    return event_has_focal_managed_regform(event)
