# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from flask import g, has_request_context, request, session

from indico.core import signals
from indico.core.plugins import IndicoPlugin
from indico.modules.logs import AppLogRealm, LogKind
from indico.modules.logs.util import make_diff_log
from indico.modules.users.schemas import AffiliationArgs, AffiliationSchema
from indico.modules.users.views import WPAffiliationsDashboard

from indico_affiliation_extras.blueprint import blueprint
from indico_affiliation_extras.schemas import AffiliationExtraAttrsArgs, AffiliationExtraAttrsSchema
from indico_affiliation_extras.util import populate_contacts, populate_memberships


AFFILIATION_EXTRA_FIELDS = {
    'contact_lists': {'title': 'Contact lists', 'type': 'list'},
    'groups': {'title': 'Groups', 'type': 'list'},
    'tags': {'title': 'Tags', 'type': 'list'},
}


class AffiliationExtrasPlugin(IndicoPlugin):
    """Affiliation Extras"""

    def init(self):
        super().init()
        self.inject_bundle('main.js', WPAffiliationsDashboard)
        self.inject_bundle('main.css', WPAffiliationsDashboard)
        self.connect(signals.plugin.schema_post_dump, self._extend_affiliation_schema, sender=AffiliationSchema)
        self.connect(signals.plugin.schema_pre_load, self._capture_affiliation_extra_attrs, sender=AffiliationArgs)
        self.connect(signals.affiliations.affiliation_created, self._set_affiliation_extra_attrs)
        self.connect(signals.affiliations.affiliation_updated, self._set_affiliation_extra_attrs)
        self.connect(
            signals.core.get_placeholders, self._get_email_placeholders, sender='affiliation-representation-email'
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
