# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from indico.core.plugins import IndicoPluginBlueprint

from indico_affiliation_extras.controllers.admin import (
    RHAffiliationGroup,
    RHAffiliationGroups,
    RHAffiliationTag,
    RHAffiliationTags,
    RHContactListNames,
    RHEmailRepresentativesImageUpload,
    RHEmailRepresentativesMetadata,
    RHEmailRepresentativesPreview,
    RHEmailRepresentativesSend,
)
from indico_affiliation_extras.controllers.category import (
    RHCreateAffiliationPreset,
    RHDeleteAffiliationPreset,
    RHEditAffiliationPreset,
    RHManageCategoryAffiliations,
    RHResolveAffiliations,
)


blueprint = IndicoPluginBlueprint('affiliation_extras', __name__)

_admin_prefix = '/api/admin/plugins/affiliation_extras'
_category_prefix = '/category/<int:category_id>/manage/affiliations'

blueprint.add_url_rule(
    f'{_admin_prefix}/representatives/email/metadata',
    'email_representatives_metadata',
    RHEmailRepresentativesMetadata,
    methods=('POST',),
)
blueprint.add_url_rule(
    f'{_admin_prefix}/representatives/email/preview',
    'email_representatives_preview',
    RHEmailRepresentativesPreview,
    methods=('POST',),
)
blueprint.add_url_rule(
    f'{_admin_prefix}/representatives/email/send',
    'email_representatives_send',
    RHEmailRepresentativesSend,
    methods=('POST',),
)
blueprint.add_url_rule(
    f'{_admin_prefix}/representatives/email/image',
    'email_representatives_image_upload',
    RHEmailRepresentativesImageUpload,
    methods=('POST',),
)

blueprint.add_url_rule(
    f'{_admin_prefix}/groups', 'api_affiliation_groups', RHAffiliationGroups, methods=('GET', 'POST')
)
blueprint.add_url_rule(
    f'{_admin_prefix}/groups/<int:group_id>',
    'api_affiliation_group',
    RHAffiliationGroup,
    methods=('GET', 'PATCH', 'DELETE'),
)
blueprint.add_url_rule(f'{_admin_prefix}/tags', 'api_affiliation_tags', RHAffiliationTags, methods=('GET', 'POST'))
blueprint.add_url_rule(
    f'{_admin_prefix}/tags/<int:tag_id>',
    'api_affiliation_tag',
    RHAffiliationTag,
    methods=('GET', 'PATCH', 'DELETE'),
)
blueprint.add_url_rule(f'{_admin_prefix}/contact-lists/names', 'api_contact_list_names', RHContactListNames)

# SPA page routes (React Router handles display)
blueprint.add_url_rule(f'{_category_prefix}/', 'manage_category_affiliations', RHManageCategoryAffiliations)
blueprint.add_url_rule(f'{_category_prefix}/new/', 'create_category_preset', RHManageCategoryAffiliations)
blueprint.add_url_rule(f'{_category_prefix}/<int:preset_id>/', 'category_preset_detail', RHManageCategoryAffiliations)

# Preset API
blueprint.add_url_rule(
    f'{_category_prefix}/api/presets', 'api_create_preset', RHCreateAffiliationPreset, methods=('POST',)
)
blueprint.add_url_rule(
    f'{_category_prefix}/api/presets/<int:preset_id>', 'api_edit_preset', RHEditAffiliationPreset, methods=('PATCH',)
)
blueprint.add_url_rule(
    f'{_category_prefix}/api/presets/<int:preset_id>',
    'api_delete_preset',
    RHDeleteAffiliationPreset,
    methods=('DELETE',),
)
blueprint.add_url_rule(
    f'{_category_prefix}/api/resolve-affiliations',
    'api_resolve_affiliations',
    RHResolveAffiliations,
    methods=('POST',),
)
