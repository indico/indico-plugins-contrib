# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

# Category-level catalog controllers for affiliations.

import re

from flask import jsonify, session
from werkzeug.exceptions import Forbidden

from indico.core.db import db
from indico.modules.categories.controllers.base import RHManageCategoryBase
from indico.modules.logs.models.entries import AppLogRealm, LogKind
from indico.modules.logs.util import make_diff_log
from indico.modules.users.models.affiliations import Affiliation
from indico.util.marshmallow import ModelField, ModelList
from indico.web.args import use_args, use_kwargs

from indico_affiliation_extras.models.catalogs import AffiliationCatalog
from indico_affiliation_extras.models.groups import AffiliationGroup
from indico_affiliation_extras.models.tags import AffiliationTag
from indico_affiliation_extras.schemas import (
    AffiliationCatalogArgs,
    AffiliationCatalogSchema,
    ExtendedAffiliationSchema,
)
from indico_affiliation_extras.settings import category_settings
from indico_affiliation_extras.util import (
    get_default_catalog_on_category,
    get_explicit_default_catalog_on_category,
    get_inherited_catalogs,
    populate_catalog_lists,
    resolve_affiliations,
)
from indico_affiliation_extras.views import WPCategoryAffiliations


TITLE_ENUM_RE = re.compile(r'^(.*) \((\d+)\)$')


class RHManageCategoryAffiliations(RHManageCategoryBase):
    def _process(self):
        own_catalogs = AffiliationCatalogSchema(many=True).dump(self.category.affiliation_catalogs)
        inherited_catalogs = AffiliationCatalogSchema(many=True, only={'id', 'name', 'owner'}).dump(
            get_inherited_catalogs(self.category)
        )
        default_catalog = get_default_catalog_on_category(self.category)
        explicit_default = get_explicit_default_catalog_on_category(self.category)
        return WPCategoryAffiliations.render_template(
            'manage_category.html',
            self.category,
            'affiliations',
            own_catalogs=own_catalogs,
            inherited_catalogs=inherited_catalogs,
            default_catalog_id=default_catalog.id if default_catalog else None,
            explicit_default_catalog_id=explicit_default.id if explicit_default else None,
            target_locator=self.category.locator,
        )


class RHAffiliationCatalogMixin:
    """Mixin that loads an affiliation catalog and validates ownership."""

    ALLOW_INHERITED = False

    @use_kwargs(
        {'catalog': ModelField(AffiliationCatalog, filter_deleted=True, required=True, data_key='catalog_id')},
        location='view_args',
    )
    def _process_args(self, catalog):
        super()._process_args()
        self.catalog = catalog
        if self.ALLOW_INHERITED:
            chain_ids = {categ['id'] for categ in self.category.chain}
            if self.catalog.category_id not in chain_ids:
                raise Forbidden
        elif self.catalog.category_id != self.category.id:
            raise Forbidden


class RHCreateAffiliationCatalog(RHManageCategoryBase):
    @use_args(AffiliationCatalogArgs)
    def _process(self, data):
        lists = data.pop('lists')
        catalog = AffiliationCatalog(category=self.category, **data)
        db.session.add(catalog)
        db.session.flush()
        list_changes, list_log_fields = populate_catalog_lists(catalog, lists)
        log_fields = {'name': 'Name', 'lists': {'title': 'Lists', 'type': 'list'}}
        log_fields.update(list_log_fields)
        catalog.log(
            AppLogRealm.admin,
            LogKind.positive,
            'Affiliation Catalogs',
            f'Affiliation catalog "{catalog.name}" created',
            session.user,
            data={'Changes': make_diff_log(list_changes, log_fields)} if list_changes else None,
        )
        return AffiliationCatalogSchema().jsonify(catalog), 201


class RHEditAffiliationCatalog(RHAffiliationCatalogMixin, RHManageCategoryBase):
    @use_args(AffiliationCatalogArgs)
    def _process(self, data):
        lists = data.pop('lists')
        changes = self.catalog.populate_from_dict(data)
        list_changes, list_log_fields = populate_catalog_lists(self.catalog, lists)
        if list_changes:
            changes.update(list_changes)
        if changes:
            log_fields = {'name': 'Name', 'lists': {'title': 'Lists', 'type': 'list'}}
            log_fields.update(list_log_fields)
            self.catalog.log(
                AppLogRealm.admin,
                LogKind.change,
                'Affiliation Catalogs',
                f'Affiliation catalog "{self.catalog.name}" modified',
                session.user,
                data={'Changes': make_diff_log(changes, log_fields)},
            )
        db.session.flush()
        return AffiliationCatalogSchema().jsonify(self.catalog)


class RHDeleteAffiliationCatalog(RHAffiliationCatalogMixin, RHManageCategoryBase):
    def _process(self):
        self.catalog.is_deleted = True
        if category_settings.get(self.category, 'default_catalog_id') == self.catalog.id:
            category_settings.set(self.category, 'default_catalog_id', None)
        db.session.flush()
        self.catalog.log(
            AppLogRealm.admin,
            LogKind.negative,
            'Affiliation Catalogs',
            f'Affiliation catalog "{self.catalog.name}" deleted',
            session.user,
        )
        return '', 204


class RHCloneAffiliationCatalog(RHAffiliationCatalogMixin, RHManageCategoryBase):
    """Clone an affiliation catalog into the current category."""

    ALLOW_INHERITED = True

    def _process(self):
        name = self.catalog.name
        max_index = 0

        if m := TITLE_ENUM_RE.match(name):
            name = m.group(1)
            max_index = int(m.group(2))

        matches = {tpl for tpl in self.category.affiliation_catalogs if tpl.name.startswith(name)}
        found = False
        for match in matches:
            if m := TITLE_ENUM_RE.match(match.name):
                found = True
                index = int(m.group(2))
                max_index = max(index, max_index)
            elif match.name == name:
                found = True
        if found:
            name = f'{name} ({max_index + 1})'

        new_catalog = AffiliationCatalog(category=self.category, name=name)
        db.session.add(new_catalog)
        db.session.flush()
        lists = [
            {
                'name': lst.name,
                'position': lst.position,
                'is_enabled': lst.is_enabled,
                'groups': lst.groups,
                'tags': lst.tags,
                'affiliations': lst.affiliations,
            }
            for lst in self.catalog.lists
        ]
        populate_catalog_lists(new_catalog, lists)
        new_catalog.log(
            AppLogRealm.admin,
            LogKind.positive,
            'Affiliation Catalogs',
            f'Affiliation catalog "{new_catalog.name}" created',
            session.user,
            data={'Cloned from': self.catalog.name},
        )
        return AffiliationCatalogSchema().jsonify(new_catalog)


class RHCategoryToggleDefaultCatalog(RHManageCategoryBase):
    """Toggle the default catalog for a category."""

    @use_kwargs(
        {'catalog': ModelField(AffiliationCatalog, filter_deleted=True, required=True, data_key='catalog_id')},
        location='view_args',
    )
    def _process(self, catalog):
        chain_ids = {categ['id'] for categ in self.category.chain}
        if catalog.category_id not in chain_ids:
            raise Forbidden

        explicit_default = get_explicit_default_catalog_on_category(self.category)
        inherited_default = get_default_catalog_on_category(self.category, only_inherited=True)
        if explicit_default and explicit_default.id == catalog.id:
            category_settings.set(self.category, 'default_catalog_id', None)
        elif inherited_default and inherited_default.id == catalog.id:
            category_settings.set(self.category, 'default_catalog_id', None)
        else:
            category_settings.set(self.category, 'default_catalog_id', catalog.id)

        default_catalog = get_default_catalog_on_category(self.category)
        explicit_default = get_explicit_default_catalog_on_category(self.category)
        return jsonify({
            'default_catalog_id': default_catalog.id if default_catalog else None,
            'explicit_default_catalog_id': explicit_default.id if explicit_default else None,
        })


class RHResolveAffiliations(RHManageCategoryBase):
    """Resolve affiliations from groups/tags/affiliations."""

    @use_kwargs(
        {
            'groups': ModelList(AffiliationGroup, collection_class=set, filter_deleted=True, load_default=set),
            'tags': ModelList(AffiliationTag, collection_class=set, load_default=set),
            'affiliations': ModelList(Affiliation, collection_class=set, filter_deleted=True, load_default=set),
        },
        location='json',
    )
    def _process(self, groups, tags, affiliations):
        resolved = resolve_affiliations(groups, tags, affiliations)
        return ExtendedAffiliationSchema(
            many=True, only=('id', 'name', 'city', 'country_code', 'groups', 'tags', 'group_tags')
        ).jsonify(resolved)
