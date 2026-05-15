# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from flask import g, has_request_context, request, session

from indico.core import signals
from indico.core.plugins import IndicoPlugin, url_for_plugin
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
from indico_affiliation_extras.schemas import AffiliationExtraAttrsArgs, AffiliationExtraAttrsSchema
from indico_affiliation_extras.util import (
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
        self.connect(signals.affiliations.get_affiliation_filters, self._restrict_affiliations_for_representation)
        self.connect(signals.event.registrant_list_items, self._get_registrant_list_items)
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

    def _get_fields(self, sender, **kwargs):
        yield RepresentationField

    def _get_registrant_list_items(self, sender, **kwargs):
        yield from iter_representation_reglist_items(sender)

    def _restrict_affiliations_for_representation(self, sender, context, **kwargs):
        return get_representation_affiliation_filters(context)
