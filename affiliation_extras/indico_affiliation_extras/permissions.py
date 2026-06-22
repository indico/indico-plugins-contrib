# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

# Focal-point access model: focal-point management is enabled by default on every event that has a
# registration form with a representation field. While enabled, Indico grants the equivalent of
# `registration_edit` through the `acl.can_manage` signal to every focal point of an affiliation in
# the event's catalog, so the native registration management UI lights up with no per-handler gates.
# The catalog is what ties affiliations to an event: a focal point has reach only over the
# affiliations the catalog exposes. The grant is then *bounded* by blacklist signals (list,
# per-registration, search, create).
#
# A full event manager can turn focal-point management off per event from the event Affiliations
# page. There is no per-user permission to grant: who is a focal point is resolved dynamically from
# the affiliation focal-point assignments (managed centrally by admins on the affiliation dashboard).
#
# A genuine `registration_edit` always prevails (so a real manager who also happens to be a focal
# point is never restricted): every check here, and every blacklist restriction, is gated on
# `is_scoped_focal_point`, which is False as soon as the user has a real grant.

from indico.util.user import iter_acl

from indico_affiliation_extras.fields import RepresentationField
from indico_affiliation_extras.focal_points import focal_affiliations_for_event
from indico_affiliation_extras.settings import event_settings


def focal_point_management_enabled(event):
    """Whether focal-point management is enabled on ``event`` (the default)."""
    return event_settings.get(event, 'focal_point_management_enabled')


def _regform_has_representation_field(regform):
    return any(field.input_type == RepresentationField.name for field in regform.active_fields)


def event_has_representation_regform(event):
    """Whether the event has a non-deleted registration form with a representation field."""
    return any(_regform_has_representation_field(regform)
               for regform in event.registration_forms if not regform.is_deleted)


def has_genuine_registration_edit(event, user):
    """Whether ``user`` holds ``registration_edit`` from a real grant (ACL entry, full access, admin, inherited).

    This deliberately excludes the dynamic focal-point grant: ``event.can_manage(user)`` (full
    management, no permission) is never granted by the focal-point hook, which only ever grants
    ``registration_edit``, and the ACL scan checks the stored permissions explicitly. So a genuine
    manager who is also a focal point is detected here and never restricted by the blacklist.
    """
    if user is None:
        return False
    if event.can_manage(user):
        return True
    return any(user in entry.principal and entry.has_management_permission('registration_edit', explicit=True)
               for entry in iter_acl(event.acl_entries))


def is_scoped_focal_point(event, user):
    """Whether ``user`` manages this event's registrations *only* as an affiliation focal point.

    True when the user is a focal point for at least one affiliation in the event's catalog,
    focal-point management is enabled on the event (the default), the event has a
    representation-bearing registration form, and they do not already hold a genuine
    ``registration_edit`` (which would prevail). This single gate drives both the dynamic grant and
    every blacklist restriction.
    """
    if not focal_affiliations_for_event(user, event):
        return False
    if has_genuine_registration_edit(event, user):
        return False
    if not focal_point_management_enabled(event):
        return False
    return event_has_representation_regform(event)
