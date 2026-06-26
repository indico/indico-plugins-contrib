# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from flask import g, has_request_context, request, session

from indico.core import signals
from indico.core.config import config
from indico.core.db import db
from indico.core.errors import UserValueError
from indico.core.plugins import IndicoPlugin, render_plugin_template, url_for_plugin
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
    focal_affiliations_for_event,
    focal_event_ids,
    focal_list_criterion,
    get_focal_affiliation_ids,
    get_submitted_affiliation_ids,
)
from indico_affiliation_extras.permissions import (
    focal_point_management_enabled,
    is_scoped_focal_point,
    regform_has_representation_field,
)
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
        self.template_hook('extra-regform-settings', self._render_regform_focal_point_setting)

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

    def _render_regform_focal_point_setting(self, regform=None, **kwargs):
        if regform is None or regform.is_deleted or not regform_has_representation_field(regform):
            return ''
        return render_plugin_template(
            'regform_focal_point_setting.html',
            regform=regform,
            focal_point_management_enabled=focal_point_management_enabled(regform),
        )

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
        # Focal points hold no ACL entry (access is dynamic), so Indico's linked-event lookup misses
        # their events; contribute them, tagged as managed for the dashboard indicator.
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

    def _filter_registration_list(self, regform, user, **kwargs):
        # Bounds the event-wide grant to the focal point's own affiliations (None leaves managers and
        # non-focal users unscoped). On a form with management off, deny (match nothing) rather than
        # abstain, since the event-wide grant would otherwise stay unbounded there.
        if not is_scoped_focal_point(regform.event, user):
            return None
        if not focal_point_management_enabled(regform):
            return db.false()
        return focal_list_criterion(user, regform.event)

    def _check_registration_pre_create(self, regform, user, data, management, **kwargs):
        # Self-service (`management` is False) is someone registering themselves and must never be
        # blocked; only management creation is bounded to the focal point's own affiliations.
        if not management or not is_scoped_focal_point(regform.event, user):
            return
        if not focal_point_management_enabled(regform):
            raise UserValueError(_('Focal-point registration management is turned off for this form.'))
        if not (get_submitted_affiliation_ids(regform, data) & focal_affiliations_for_event(user, regform.event)):
            raise UserValueError(_('As a focal point you may only register people for your own affiliations.'))

    def _grant_focal_point_registration_edit(self, sender, obj, user=None, permission=None, **kwargs):
        # Dynamically grant `registration_edit` to a scoped focal point (True grants, None defers).
        # Never return False, which would deny a legitimate manager; bounding is done by the blacklist signals.
        if permission == 'registration_edit' and is_scoped_focal_point(obj, user):
            return True

    def _filter_user_search_results(self, sender, user, results, **kwargs):
        # Bound a focal point's user search to their own affiliations. Skipped when public user search
        # is allowed: the bound is pointless there and would hinder a dual-hat focal point/manager.
        if config.ALLOW_PUBLIC_USER_SEARCH:
            return None
        focal_ids = get_focal_affiliation_ids(user)
        if not focal_ids:
            return None
        return [entry for entry in results if entry.get('affiliation_id') in focal_ids]

    def _get_affiliation_filters(self, sender, context, **kwargs):
        return get_representation_affiliation_filters(context) + get_extended_affiliation_filters(context)
