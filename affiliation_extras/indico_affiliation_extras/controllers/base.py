# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from marshmallow import fields
from sqlalchemy.orm import subqueryload

from indico.core.db import db
from indico.modules.users.util import SearchAffiliationsMixin
from indico.web.args import use_kwargs

from indico_affiliation_extras.models.groups import AffiliationGroup
from indico_affiliation_extras.models.tags import AffiliationTag
from indico_affiliation_extras.schemas import (
    AffiliationGroupSchema,
    AffiliationGroupWithAffiliationsSchema,
    AffiliationTagSchema,
    AffiliationTagWithAffiliationsSchema,
)
from indico_affiliation_extras.util import get_users_by_affiliation


class AffiliationGroupsMixin:
    """Return non-deleted affiliation groups."""

    def _process_GET(self):
        groups = AffiliationGroup.query.filter(~AffiliationGroup.is_deleted).order_by(
            db.func.indico.indico_unaccent(db.func.lower(AffiliationGroup.name))
        )
        return AffiliationGroupSchema(many=True).jsonify(groups)


class AffiliationTagsMixin:
    """Return affiliation tags."""

    def _process_GET(self):
        tags = AffiliationTag.query.order_by(db.func.indico.indico_unaccent(db.func.lower(AffiliationTag.name)))
        return AffiliationTagSchema(many=True).jsonify(tags)


class AffiliationGroupsWithUsersMixin:
    """Return non-deleted affiliation groups with their affiliations and users."""

    def _process_GET(self):
        groups = (
            AffiliationGroup.query
            .filter(~AffiliationGroup.is_deleted)
            .options(subqueryload('affiliations'))
            .order_by(db.func.indico.indico_unaccent(db.func.lower(AffiliationGroup.name)))
            .all()
        )
        affiliations = {aff for group in groups for aff in group.affiliations}
        context = {'users_by_affiliation': get_users_by_affiliation(affiliations)}
        return AffiliationGroupWithAffiliationsSchema(many=True, context=context).jsonify(groups)


class AffiliationTagsWithUsersMixin:
    """Return affiliation tags with their affiliations and users."""

    def _process_GET(self):
        tags = (
            AffiliationTag.query
            .options(subqueryload('affiliations'))
            .order_by(db.func.indico.indico_unaccent(db.func.lower(AffiliationTag.name)))
            .all()
        )
        affiliations = {aff for tag in tags for aff in tag.affiliations}
        context = {'users_by_affiliation': get_users_by_affiliation(affiliations)}
        return AffiliationTagWithAffiliationsSchema(many=True, context=context).jsonify(tags)


class SearchAffiliationsExtendedMixin(SearchAffiliationsMixin):
    """Affiliation search with optional group/tag/country filters."""

    @use_kwargs(
        {
            'group_ids': fields.List(fields.Integer(), load_default=list),
            'tag_ids': fields.List(fields.Integer(), load_default=list),
            'country_code': fields.String(load_default=''),
        },
        location='query',
    )
    def _process_args(self, group_ids, tag_ids, country_code):
        super()._process_args()
        self.group_ids = group_ids
        self.tag_ids = tag_ids
        self.country_code = country_code

    @property
    def context(self):
        return {'group_ids': self.group_ids, 'tag_ids': self.tag_ids, 'country_code': self.country_code}
