# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import re

from flask import jsonify, request, session
from werkzeug.exceptions import Forbidden

from indico.core.db import db
from indico.modules.categories.controllers.base import RHManageCategoryBase
from indico.modules.categories.models.categories import Category
from indico.modules.events.management.controllers import RHManageEventBase
from indico.modules.events.models.events import Event
from indico.modules.events.util import check_event_locked
from indico.modules.logs.models.entries import LogKind
from indico.modules.logs.util import make_diff_log
from indico.modules.users.models.affiliations import Affiliation
from indico.util.marshmallow import ModelField, ModelList
from indico.web.args import use_args, use_kwargs
from indico.web.rh import RHProtected

from indico_affiliation_extras.models.catalogs import AffiliationCatalog
from indico_affiliation_extras.models.groups import AffiliationGroup
from indico_affiliation_extras.models.tags import AffiliationTag
from indico_affiliation_extras.schemas import (
    AffiliationCatalogArgs,
    AffiliationCatalogSchema,
    ExtendedAffiliationSchema,
)
from indico_affiliation_extras.settings import category_settings, event_settings
from indico_affiliation_extras.util import (
    get_all_catalogs,
    get_default_catalog,
    get_explicit_default_catalog,
    get_inherited_catalogs,
    populate_catalog_lists,
    resolve_affiliations,
)
from indico_affiliation_extras.views import WPCategoryAffiliations, WPEventAffiliations


TITLE_ENUM_RE = re.compile(r'^(.*) \((\d+)\)$')


class AffiliationCatalogListMixin:
    @property
    def target(self):
        return self.event if hasattr(self, 'event') else self.category

    def _process(self):
        own_catalogs = AffiliationCatalogSchema(many=True).dump(self.target.affiliation_catalogs)
        inherited_catalogs = AffiliationCatalogSchema(many=True, only={'id', 'name', 'owner'}).dump(
            get_inherited_catalogs(self.target)
        )
        default_catalog = get_default_catalog(self.target)
        explicit_default = get_explicit_default_catalog(self.target)
        view_class = WPEventAffiliations if isinstance(self.target, Event) else WPCategoryAffiliations
        return view_class.render_template(
            'manage_affiliations.html',
            self.target,
            'affiliation_extras',
            own_catalogs=own_catalogs,
            inherited_catalogs=inherited_catalogs,
            default_catalog_id=default_catalog.id if default_catalog else None,
            explicit_default_catalog_id=explicit_default.id if explicit_default else None,
            target_locator=self.target.locator,
        )


class RHManageCategoryAffiliations(AffiliationCatalogListMixin, RHManageCategoryBase):
    pass


class RHManageEventAffiliations(AffiliationCatalogListMixin, RHManageEventBase):
    pass


class AffiliationAreaMixin:
    @property
    def object_type(self):
        return request.view_args['object_type']

    @property
    def target(self):
        event_id = request.view_args.get('event_id')
        category_id = request.view_args.get('category_id')
        return Event.get_or_404(event_id) if self.object_type == 'event' else Category.get_or_404(category_id)

    @property
    def target_dict(self):
        return {'event': self.target} if self.object_type == 'event' else {'category': self.target}

    @property
    def settings_proxy(self):
        return event_settings if isinstance(self.target, Event) else category_settings

    def _check_access(self):
        if not self.target.can_manage(session.user):
            raise Forbidden
        if isinstance(self.target, Event):
            check_event_locked(self, self.target)


class RHAffiliationCatalogsManagementBase(RHProtected):
    DENY_FRAMES = True


class RHAffiliationCatalogMixin(AffiliationAreaMixin):
    """Mixin that loads an affiliation catalog and validates ownership."""

    ALLOW_INHERITED = False

    @use_kwargs(
        {'catalog': ModelField(AffiliationCatalog, filter_deleted=True, required=True, data_key='catalog_id')},
        location='view_args',
    )
    def _process_args(self, catalog):
        super()._process_args()
        self.catalog = catalog
        allowed_catalogs = (
            get_all_catalogs(self.target) if self.ALLOW_INHERITED else set(self.target.affiliation_catalogs)
        )
        if self.catalog.id not in {item.id for item in allowed_catalogs}:
            raise Forbidden


class RHCreateAffiliationCatalog(AffiliationAreaMixin, RHAffiliationCatalogsManagementBase):
    @use_args(AffiliationCatalogArgs)
    def _process(self, data):
        lists = data.pop('lists')
        catalog = AffiliationCatalog(**self.target_dict, **data)
        db.session.add(catalog)
        db.session.flush()
        populate_catalog_lists(catalog, lists)
        catalog.owner.log(
            catalog.log_realm,
            LogKind.positive,
            'Affiliation Catalogs',
            f'Affiliation catalog "{catalog.name}" created',
            session.user,
            meta={'affiliation_catalog_id': catalog.id},
        )
        return AffiliationCatalogSchema().jsonify(catalog), 201


class RHEditAffiliationCatalog(RHAffiliationCatalogMixin, RHAffiliationCatalogsManagementBase):
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
            self.catalog.owner.log(
                self.catalog.log_realm,
                LogKind.change,
                'Affiliation Catalogs',
                f'Affiliation catalog "{self.catalog.name}" modified',
                session.user,
                data={'Changes': make_diff_log(changes, log_fields)},
                meta={'affiliation_catalog_id': self.catalog.id},
            )
        db.session.flush()
        return AffiliationCatalogSchema().jsonify(self.catalog)


class RHDeleteAffiliationCatalog(RHAffiliationCatalogMixin, RHAffiliationCatalogsManagementBase):
    def _process(self):
        self.catalog.is_deleted = True
        if self.settings_proxy.get(self.target, 'default_catalog_id') == self.catalog.id:
            self.settings_proxy.set(self.target, 'default_catalog_id', None)
        db.session.flush()
        self.catalog.owner.log(
            self.catalog.log_realm,
            LogKind.negative,
            'Affiliation Catalogs',
            f'Affiliation catalog "{self.catalog.name}" deleted',
            session.user,
            meta={'affiliation_catalog_id': self.catalog.id},
        )
        return '', 204


class RHCloneAffiliationCatalog(RHAffiliationCatalogMixin, RHAffiliationCatalogsManagementBase):
    """Clone an affiliation catalog into the current category/event."""

    ALLOW_INHERITED = True

    def _process(self):
        name = self.catalog.name
        max_index = 0

        if m := TITLE_ENUM_RE.match(name):
            name = m.group(1)
            max_index = int(m.group(2))

        matches = {tpl for tpl in self.target.affiliation_catalogs if tpl.name.startswith(name)}
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

        new_catalog = AffiliationCatalog(**self.target_dict, name=name)
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
        new_catalog.owner.log(
            new_catalog.log_realm,
            LogKind.positive,
            'Affiliation Catalogs',
            f'Affiliation catalog "{new_catalog.name}" created',
            session.user,
            data={'Cloned from': self.catalog.name},
            meta={'affiliation_catalog_id': new_catalog.id},
        )
        return AffiliationCatalogSchema().jsonify(new_catalog)


class RHToggleDefaultCatalog(AffiliationAreaMixin, RHAffiliationCatalogsManagementBase):
    """Toggle the default catalog for a category/event target."""

    @use_kwargs(
        {'catalog': ModelField(AffiliationCatalog, filter_deleted=True, required=True, data_key='catalog_id')},
        location='view_args',
    )
    def _process(self, catalog):
        if catalog.id not in {item.id for item in get_all_catalogs(self.target)}:
            raise Forbidden

        explicit_default = get_explicit_default_catalog(self.target)
        inherited_default = get_default_catalog(self.target, only_inherited=True)
        if explicit_default and explicit_default.id == catalog.id:
            self.settings_proxy.set(self.target, 'default_catalog_id', None)
        elif inherited_default and inherited_default.id == catalog.id:
            self.settings_proxy.set(self.target, 'default_catalog_id', None)
        else:
            self.settings_proxy.set(self.target, 'default_catalog_id', catalog.id)

        default_catalog = get_default_catalog(self.target)
        explicit_default = get_explicit_default_catalog(self.target)
        return jsonify({
            'default_catalog_id': default_catalog.id if default_catalog else None,
            'explicit_default_catalog_id': explicit_default.id if explicit_default else None,
        })


class RHResolveAffiliations(AffiliationAreaMixin, RHAffiliationCatalogsManagementBase):
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
