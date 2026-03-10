# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from flask import g, session

from indico.core import signals
from indico.core.plugins import IndicoPlugin
from indico.modules.logs import AppLogRealm, LogKind
from indico.modules.logs.util import make_diff_log
from indico.modules.users.schemas import AffiliationArgs, AffiliationSchema
from indico.modules.users.views import WPAffiliationsDashboard

from indico_affiliations.blueprint import blueprint
from indico_affiliations.schemas import (AffiliationContactListSchema, AffiliationExtraAttrsArgs,
                                         AffiliationGroupSchema, AffiliationTagSchema)
from indico_affiliations.util import populate_contacts, populate_memberships


AFFILIATION_EXTRA_FIELDS = {
    'contacts': {'title': 'Contact lists', 'type': 'list'},
    'groups': {'title': 'Groups', 'type': 'list'},
    'tags': {'title': 'Tags', 'type': 'list'}
}


@signals.core.get_placeholders.connect_via('affiliation-representation-email')
def _get_email_placeholders(sender, affiliation=None, **kwargs):
    from indico_affiliations import placeholders as p
    yield p.AffiliationNamePlaceholder
    yield p.AffiliationStreetPlaceholder
    yield p.AffiliationCityPlaceholder
    yield p.AffiliationPostcodePlaceholder
    yield p.AffiliationCountryPlaceholder
    yield p.AffiliationMetadataPlaceholder


class AffiliationsPlugin(IndicoPlugin):
    """Extended Affiliations"""

    def init(self):
        super().init()
        self.connect(signals.affiliations.affiliation_created, self._set_affiliation_extra_attrs)
        self.connect(signals.affiliations.affiliation_updated, self._set_affiliation_extra_attrs)
        self.connect(signals.plugin.schema_post_dump, self._extend_affiliation_schema, sender=AffiliationSchema)
        self.connect(signals.plugin.schema_pre_load, self._capture_affiliation_extra_attrs, sender=AffiliationArgs)
        self.inject_bundle('main.js', WPAffiliationsDashboard)
        self.inject_bundle('main.css', WPAffiliationsDashboard)

    def get_blueprints(self):
        return blueprint

    def _extend_affiliation_schema(self, sender, data, orig, **kwargs):
        group_schema = AffiliationGroupSchema(many=True, exclude=('meta',))
        tag_schema = AffiliationTagSchema(many=True)
        contact_list_schema = AffiliationContactListSchema(many=True)
        for dump_data, affiliation in zip(data, orig, strict=True):
            groups = sorted(affiliation.groups, key=lambda item: item.code.lower())
            tags = sorted(affiliation.tags, key=lambda item: item.code.lower())
            contacts = sorted(affiliation.contacts, key=lambda item: item.name.lower())
            dump_data['contacts'] = contact_list_schema.dump(contacts)
            dump_data['groups'] = group_schema.dump(groups)
            dump_data['tags'] = tag_schema.dump(tags)

    def _capture_affiliation_extra_attrs(self, sender, data, **kwargs):
        g.affiliations_extra_attrs = AffiliationExtraAttrsArgs().load(data)

    def _set_affiliation_extra_attrs(self, affiliation, **kwargs):
        pending = g.pop('affiliations_extra_attrs', {})
        log_fields = dict(AFFILIATION_EXTRA_FIELDS)
        if 'contacts' in pending:
            changes, extra_log_fields = populate_contacts(affiliation, pending.pop('contacts'))
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
                data={'Changes': make_diff_log(changes, log_fields)}
            )
