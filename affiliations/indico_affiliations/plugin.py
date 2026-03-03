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
from indico_affiliations.schemas import AffiliationExtraAttrsArgs, AffiliationGroupSchema, AffiliationTagSchema
from indico_affiliations.util import populate_memberships


AFFILIATION_EXTRA_FIELDS = {
    'contact_emails': {'title': 'Contact Emails', 'type': 'list'},
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
        for dump_data, affiliation in zip(data, orig, strict=True):
            groups = sorted(affiliation.groups, key=lambda item: item.code.lower())
            tags = sorted(affiliation.tags, key=lambda item: item.code.lower())
            dump_data['contact_emails'] = affiliation.contact_emails
            dump_data['groups'] = group_schema.dump(groups)
            dump_data['tags'] = tag_schema.dump(tags)

    def _capture_affiliation_extra_attrs(self, sender, data, **kwargs):
        extra_attrs = AFFILIATION_EXTRA_FIELDS.keys() & data.keys()
        if not extra_attrs:
            return
        extra_data = {k: data.pop(k) for k in extra_attrs}
        g.affiliations_extra_attrs = AffiliationExtraAttrsArgs().load(extra_data)

    def _set_affiliation_extra_attrs(self, affiliation, **kwargs):
        pending = g.pop('affiliations_extra_attrs', {})
        if 'contact_emails' in pending:
            changes = affiliation.populate_from_dict({'contact_emails': pending.pop('contact_emails')})
        else:
            changes = {}
        if changes := populate_memberships(affiliation, pending, changes=changes):
            affiliation.log(
                AppLogRealm.admin,
                LogKind.change,
                'Affiliations',
                f'Extended attributes of affiliation "{affiliation.name}" modified',
                session.user,
                data={'Changes': make_diff_log(changes, AFFILIATION_EXTRA_FIELDS)}
            )
