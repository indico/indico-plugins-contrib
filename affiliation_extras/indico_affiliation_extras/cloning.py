# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from indico.modules.events.cloning import EventCloner
from indico.util.i18n import _

from indico_affiliation_extras.fields import RepresentationField
from indico_affiliation_extras.permissions import focal_point_management_enabled, set_focal_point_management_enabled
from indico_affiliation_extras.util import clone_affiliation_catalog, get_available_catalog


class RepresentationCatalogCloner(EventCloner):
    name = 'affiliation_extras_representation_catalogs'
    friendly_name = _('Representation catalogs')
    is_internal = True
    is_default = True
    uses = {'registration_forms', 'registrations'}

    def get_conflicts(self, target_event):
        return []

    def run(self, new_event, cloners, shared_data, event_exists=False):
        if 'registration_forms' not in shared_data:
            return
        catalogs = {}
        for old_form, new_form in shared_data['registration_forms']['form_map'].items():
            field_lists = {}
            for field in new_form.form_items:
                if field.input_type != RepresentationField.name or not (catalog_id := field.data.get('catalog_id')):
                    continue
                if get_available_catalog(new_event, catalog_id) is not None:
                    continue
                if catalog_id not in catalogs:
                    catalog = get_available_catalog(self.old_event, catalog_id)
                    if catalog is None:
                        continue
                    catalogs[catalog_id] = clone_affiliation_catalog(catalog, new_event)
                catalog, list_map = catalogs[catalog_id]
                field.data = {**field.data, 'catalog_id': catalog.id}
                field_lists[field.id] = list_map
            for registration in new_form.registrations:
                for value in registration.data:
                    list_map = field_lists.get(value.field_data.field_id, {})
                    if isinstance(value.data, dict) and (list_id := value.data.get('representation_id')) in list_map:
                        value.data = {**value.data, 'representation_id': list_map[list_id]}
            if focal_point_management_enabled(old_form):
                set_focal_point_management_enabled(new_form, True)
