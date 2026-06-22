# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from flask import g, has_request_context, request, session

from indico.core import signals
from indico.core.errors import UserValueError
from indico.core.plugins import IndicoPlugin, url_for_plugin
from indico.modules.events.models.events import Event
from indico.modules.events.registration.fields.base import RegistrationFormFieldBase
from indico.modules.events.registration.views import (
    WPDisplayRegistrationFormConference,
    WPDisplayRegistrationFormSimpleEvent,
    WPManageRegistration,
)
from indico.modules.logs import AppLogRealm, LogKind
from indico.modules.logs.util import make_diff_log
from indico.modules.users.schemas import AffiliationArgs, AffiliationSchema
from indico.modules.users.views import WPAffiliationsDashboard
from indico.util.i18n import _
from indico.web.menu import SideMenuItem

from indico_affiliation_extras.blueprint import blueprint
from indico_affiliation_extras.fields import RepresentationField, iter_representation_reglist_items
from indico_affiliation_extras.focal_points import (
    RegisteredByListItem,
    focal_affiliations_for_event,
    focal_event_ids,
    focal_list_criterion,
    get_focal_affiliation_ids,
    get_submitted_affiliation_ids,
)
from indico_affiliation_extras.permissions import is_scoped_focal_point
from indico_affiliation_extras.schemas import AffiliationExtraAttrsArgs, AffiliationExtraAttrsSchema
from indico_affiliation_extras.util import (
    get_extended_affiliation_filters,
    get_representation_affiliation_filters,
    populate_contacts,
    populate_memberships,
)
from indico_affiliation_extras.views import WPCategoryAffiliations, WPEventAffiliations


AFFILIATION_EXTRA_FIELDS = {
    'contact_lists': {'title': 'Contact lists', 'type': 'list'},
    'groups': {'title': 'Groups', 'type': 'list'},
    'tags': {'title': 'Tags', 'type': 'list'},
}


class AffiliationExtrasPlugin(IndicoPlugin):
    """Affiliation Extras"""

    def init(self):
        super().init()
        wps = (
            WPAffiliationsDashboard,
            WPCategoryAffiliations,
            WPEventAffiliations,
            WPManageRegistration,
            WPDisplayRegistrationFormConference,
            WPDisplayRegistrationFormSimpleEvent,
        )
        self.inject_bundle('main.js', wps)
        self.inject_bundle('main.css', wps)
        self.connect(signals.core.get_fields, self._get_fields, sender=RegistrationFormFieldBase)
        self.connect(signals.plugin.schema_post_dump, self._extend_affiliation_schema, sender=AffiliationSchema)
        self.connect(signals.plugin.schema_pre_load, self._capture_affiliation_extra_attrs, sender=AffiliationArgs)
        self.connect(signals.affiliations.affiliation_created, self._set_affiliation_extra_attrs)
        self.connect(signals.affiliations.affiliation_updated, self._set_affiliation_extra_attrs)
        self.connect(signals.affiliations.get_affiliation_filters, self._get_affiliation_filters)
        self.connect(signals.event.registrant_list_items, self._get_registrant_list_items)
        self.connect(signals.event.filter_registration_list, self._filter_registration_list)
        self.connect(signals.event.registration_pre_create, self._check_registration_pre_create)
        self.connect(signals.users.filter_user_search_results, self._filter_user_search_results)
        self.connect(signals.users.extra_linked_events, self._extra_linked_events)
        self.connect(signals.acl.can_manage, self._grant_focal_point_registration_edit, sender=Event)
        self.connect(signals.menu.items, self._category_sidemenu_items, sender='category-management-sidemenu')
        self.connect(signals.menu.items, self._event_sidemenu_items, sender='event-management-sidemenu')
        self.connect(
            signals.core.get_placeholders,
            self._get_email_placeholders,
            sender='affiliation-representation-email',
        )

    def get_blueprints(self):
        return blueprint

    def _extend_affiliation_schema(self, sender, data, orig, **kwargs):
        if not has_request_context() or request.endpoint != 'users.api_admin_affiliations':
            return
        for dump_data, affiliation in zip(data, orig, strict=True):
            dump_data.update(AffiliationExtraAttrsSchema().dump(affiliation))

    def _capture_affiliation_extra_attrs(self, sender, data, **kwargs):
        g.affiliations_extra_attrs = AffiliationExtraAttrsArgs().load(data)

    def _set_affiliation_extra_attrs(self, affiliation, **kwargs):
        pending = g.pop('affiliations_extra_attrs', {})
        log_fields = dict(AFFILIATION_EXTRA_FIELDS)
        if 'contact_lists' in pending:
            changes, extra_log_fields = populate_contacts(affiliation, pending.pop('contact_lists'))
            log_fields.update(extra_log_fields)
        else:
            changes = {}
        if changes := populate_memberships(affiliation, pending, changes=changes):
            affiliation.log(
                AppLogRealm.admin,
                LogKind.change,
                'Affiliations',
                f'Extended attributes of affiliation "{affiliation.name}" modified',
                session.user,
                data={'Changes': make_diff_log(changes, log_fields)},
            )

    def _get_email_placeholders(self, sender, affiliation=None, **kwargs):
        from indico_affiliation_extras import placeholders as p

        yield p.AffiliationNamePlaceholder
        yield p.AffiliationStreetPlaceholder
        yield p.AffiliationCityPlaceholder
        yield p.AffiliationPostcodePlaceholder
        yield p.AffiliationCountryPlaceholder
        yield p.AffiliationMetadataPlaceholder

    def _category_sidemenu_items(self, sender, category, **kwargs):
        if category.can_manage(session.user):
            return SideMenuItem(
                'affiliation_extras',
                _('Affiliations'),
                url_for_plugin('affiliation_extras.manage_affiliations', category),
                sui_icon='university',
                weight=15,
            )

    def _event_sidemenu_items(self, sender, event, **kwargs):
        if event.can_manage(session.user):
            return SideMenuItem(
                'affiliation_extras',
                _('Affiliations'),
                url_for_plugin('affiliation_extras.manage_affiliations', event),
                section='customization',
            )

    def _extra_linked_events(self, user, dt=None, **kwargs):
        # Surface focal-point events on the user's dashboard (and personal calendar feed). Focal
        # points hold no ACL entry on these events (access is dynamic), so Indico's own linked-event
        # lookup never finds them. We contribute the events the user has focal-point reach over,
        # tagged with a management role so the dashboard shows the management indicator.
        event_ids = focal_event_ids(user)
        if not event_ids:
            return None
        events = Event.query.filter(Event.id.in_(event_ids)).all()
        return {event.id: {'conference_manager'}
                for event in events
                if is_scoped_focal_point(event, user) and (dt is None or event.start_dt >= dt)}

    def _get_fields(self, sender, **kwargs):
        yield RepresentationField

    def _get_registrant_list_items(self, sender, **kwargs):
        yield from iter_representation_reglist_items(sender)
        yield RegisteredByListItem

    def _filter_registration_list(self, regform, user, **kwargs):
        # Scope a focal point's management view to the registrations of their own affiliations. This
        # criterion is what bounds the event-wide `registration_edit` grant: core applies it to the
        # list, the managed count and the per-registration `Registration.can_manage` check. Genuine
        # managers and non-focal users are not scoped (None), so their access stays unrestricted.
        if not is_scoped_focal_point(regform.event, user):
            return None
        return focal_list_criterion(user, regform.event)

    def _check_registration_pre_create(self, regform, user, data, management, **kwargs):
        # Guardrail: a scoped focal point may only create registrations for affiliations they
        # manage. Self-service (`management` is False) is a person registering THEMSELVES through
        # the public form; that must never be blocked, even for an affiliation they do not manage,
        # so we return immediately. Only management creation (registering ANOTHER person) is bounded.
        # Genuine managers and non-focal users are not scoped, so stock Indico is unaffected.
        if not management or not is_scoped_focal_point(regform.event, user):
            return
        if not (get_submitted_affiliation_ids(regform, data) & focal_affiliations_for_event(user, regform.event)):
            raise UserValueError(_('As a focal point you may only register people for your own affiliations.'))

    def _grant_focal_point_registration_edit(self, sender, obj, user=None, permission=None, **kwargs):
        # Dynamically grant a focal point the equivalent of `registration_edit` on an opted-in event
        # (see `is_scoped_focal_point`). Returning True grants; returning None defers to the regular
        # ACL. We never return False here (that would deny a legitimate manager); the per-registration
        # and list bounding is done separately by the blacklist signals.
        if permission == 'registration_edit' and is_scoped_focal_point(obj, user):
            return True

    def _filter_user_search_results(self, sender, user, results, **kwargs):
        # Bound a focal point's user search to people of their own affiliations, so they can only
        # pick registrants they are allowed to manage. Entries without a matching affiliation id
        # (including external users, whose id is None or -1) are dropped.
        #
        # Dual-hat limitation: a user who is both a focal point and a full event manager gets even
        # their generic user searches bounded here. That is acceptable for now; the focal-point role
        # is the more restrictive one and we honor it.
        focal_ids = get_focal_affiliation_ids(user)
        if not focal_ids:
            return None
        return [entry for entry in results if entry.get('affiliation_id') in focal_ids]

    def _get_affiliation_filters(self, sender, context, **kwargs):
        return get_representation_affiliation_filters(context) + get_extended_affiliation_filters(context)
