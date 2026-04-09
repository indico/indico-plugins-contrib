# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

# Category-level preset controllers for affiliations.

import re

from flask import session
from werkzeug.exceptions import Forbidden

from indico.core.db import db
from indico.modules.categories.controllers.base import RHManageCategoryBase
from indico.modules.logs.models.entries import AppLogRealm, LogKind
from indico.modules.logs.util import make_diff_log
from indico.modules.users.models.affiliations import Affiliation
from indico.util.marshmallow import ModelField, ModelList
from indico.web.args import use_args, use_kwargs

from indico_affiliation_extras.models.groups import AffiliationGroup
from indico_affiliation_extras.models.presets import AffiliationPresets
from indico_affiliation_extras.models.tags import AffiliationTag
from indico_affiliation_extras.schemas import AffiliationPresetArgs, AffiliationPresetSchema, ExtendedAffiliationSchema
from indico_affiliation_extras.util import get_inherited_presets, populate_preset_lists, resolve_affiliations
from indico_affiliation_extras.views import WPCategoryAffiliations


TITLE_ENUM_RE = re.compile(r'^(.*) \((\d+)\)$')


class RHManageCategoryAffiliations(RHManageCategoryBase):
    def _process(self):
        own_presets = AffiliationPresetSchema(many=True).dump(self.category.affiliation_presets)
        inherited_presets = AffiliationPresetSchema(many=True, only={'id', 'name', 'owner'}).dump(
            get_inherited_presets(self.category)
        )
        return WPCategoryAffiliations.render_template(
            'manage_category.html',
            self.category,
            'affiliations',
            own_presets=own_presets,
            inherited_presets=inherited_presets,
            target_locator=self.category.locator,
        )


class RHAffiliationPresetMixin:
    """Mixin that loads an affiliation preset and validates ownership."""

    ALLOW_INHERITED = False

    @use_kwargs(
        {'preset': ModelField(AffiliationPresets, filter_deleted=True, required=True, data_key='preset_id')},
        location='view_args',
    )
    def _process_args(self, preset):
        super()._process_args()
        self.preset = preset
        if self.ALLOW_INHERITED:
            chain_ids = {categ['id'] for categ in self.category.chain}
            if self.preset.category_id not in chain_ids:
                raise Forbidden
        elif self.preset.category_id != self.category.id:
            raise Forbidden


class RHCreateAffiliationPreset(RHManageCategoryBase):
    @use_args(AffiliationPresetArgs)
    def _process(self, data):
        lists = data.pop('lists')
        preset = AffiliationPresets(category=self.category, **data)
        db.session.add(preset)
        db.session.flush()
        list_changes, list_log_fields = populate_preset_lists(preset, lists)
        log_fields = {'name': 'Name', 'lists': {'title': 'Lists', 'type': 'list'}}
        log_fields.update(list_log_fields)
        preset.log(
            AppLogRealm.admin,
            LogKind.positive,
            'Affiliation Presets',
            f'Affiliation preset "{preset.name}" created',
            session.user,
            data={'Changes': make_diff_log(list_changes, log_fields)} if list_changes else None,
        )
        return AffiliationPresetSchema().jsonify(preset), 201


class RHEditAffiliationPreset(RHAffiliationPresetMixin, RHManageCategoryBase):
    @use_args(AffiliationPresetArgs)
    def _process(self, data):
        lists = data.pop('lists')
        changes = self.preset.populate_from_dict(data)
        list_changes, list_log_fields = populate_preset_lists(self.preset, lists)
        if list_changes:
            changes.update(list_changes)
        if changes:
            log_fields = {'name': 'Name', 'lists': {'title': 'Lists', 'type': 'list'}}
            log_fields.update(list_log_fields)
            self.preset.log(
                AppLogRealm.admin,
                LogKind.change,
                'Affiliation Presets',
                f'Affiliation preset "{self.preset.name}" modified',
                session.user,
                data={'Changes': make_diff_log(changes, log_fields)},
            )
        db.session.flush()
        return AffiliationPresetSchema().jsonify(self.preset)


class RHDeleteAffiliationPreset(RHAffiliationPresetMixin, RHManageCategoryBase):
    def _process(self):
        self.preset.is_deleted = True
        db.session.flush()
        self.preset.log(
            AppLogRealm.admin,
            LogKind.negative,
            'Affiliation Presets',
            f'Affiliation preset "{self.preset.name}" deleted',
            session.user,
        )
        return '', 204


class RHCloneAffiliationPreset(RHAffiliationPresetMixin, RHManageCategoryBase):
    """Clone an affiliation preset into the current category."""

    ALLOW_INHERITED = True

    def _process(self):
        name = self.preset.name
        max_index = 0

        if m := TITLE_ENUM_RE.match(name):
            name = m.group(1)
            max_index = int(m.group(2))

        matches = {tpl for tpl in self.category.affiliation_presets if tpl.name.startswith(name)}
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

        new_preset = AffiliationPresets(category=self.category, name=name)
        db.session.add(new_preset)
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
            for lst in self.preset.lists
        ]
        populate_preset_lists(new_preset, lists)
        new_preset.log(
            AppLogRealm.admin,
            LogKind.positive,
            'Affiliation Presets',
            f'Affiliation preset "{new_preset.name}" created',
            session.user,
            data={'Cloned from': self.preset.name},
        )
        return AffiliationPresetSchema().jsonify(new_preset)


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
