# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from indico.core.plugins import IndicoPluginBlueprint
from indico.util.caching import memoize
from indico.web.flask.util import make_view_func

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
from indico_affiliation_extras.controllers.catalogs import (
    RHCloneAffiliationCatalog,
    RHCreateAffiliationCatalog,
    RHDeleteAffiliationCatalog,
    RHEditAffiliationCatalog,
    RHManageCategoryAffiliations,
    RHManageEventAffiliations,
    RHResolveAffiliations,
    RHToggleDefaultCatalog,
)


blueprint = IndicoPluginBlueprint('affiliation_extras', __name__)

_admin_prefix = '/api/admin/plugins/affiliation_extras'


@memoize
def _dispatch(event_rh, category_rh):
    event_view = make_view_func(event_rh)
    category_view = make_view_func(category_rh)

    def view_func(**kwargs):
        return category_view(**kwargs) if kwargs['object_type'] == 'category' else event_view(**kwargs)

    return view_func


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
    f'{_admin_prefix}/tags/<int:tag_id>', 'api_affiliation_tag', RHAffiliationTag, methods=('GET', 'PATCH', 'DELETE')
)
blueprint.add_url_rule(f'{_admin_prefix}/contact-lists/names', 'api_contact_list_names', RHContactListNames)

# SPA page routes (React Router handles display)
_management_page = _dispatch(RHManageEventAffiliations, RHManageCategoryAffiliations)

for object_type in ('event', 'category'):
    if object_type == 'category':
        prefix = '/category/<int:category_id>'
    else:
        prefix = '/event/<int:event_id>'
    prefix += '/manage/affiliations'
    defaults = {'object_type': object_type}

    # SPA page routes (React Router handles display)
    blueprint.add_url_rule(f'{prefix}/', 'manage_affiliations', _management_page, defaults=defaults)
    blueprint.add_url_rule(f'{prefix}/new/', 'create_catalog', _management_page, defaults=defaults)
    blueprint.add_url_rule(f'{prefix}/<int:catalog_id>/', 'catalog_detail', _management_page, defaults=defaults)

    # Catalog API
    blueprint.add_url_rule(
        f'{prefix}/api/affiliations/catalogs',
        'api_create_catalog',
        RHCreateAffiliationCatalog,
        defaults=defaults,
        methods=('POST',),
    )
    blueprint.add_url_rule(
        f'{prefix}/api/affiliations/catalogs/<int:catalog_id>',
        'api_edit_catalog',
        RHEditAffiliationCatalog,
        defaults=defaults,
        methods=('PATCH',),
    )
    blueprint.add_url_rule(
        f'{prefix}/api/affiliations/catalogs/<int:catalog_id>',
        'api_delete_catalog',
        RHDeleteAffiliationCatalog,
        defaults=defaults,
        methods=('DELETE',),
    )
    blueprint.add_url_rule(
        f'{prefix}/api/affiliations/catalogs/<int:catalog_id>/clone',
        'api_clone_catalog',
        RHCloneAffiliationCatalog,
        defaults=defaults,
        methods=('POST',),
    )
    blueprint.add_url_rule(
        f'{prefix}/api/affiliations/catalogs/<int:catalog_id>/toggle-default',
        'api_toggle_default_catalog',
        RHToggleDefaultCatalog,
        defaults=defaults,
        methods=('POST',),
    )
    blueprint.add_url_rule(
        f'{prefix}/api/affiliations/resolve',
        'api_resolve_affiliations',
        RHResolveAffiliations,
        defaults=defaults,
        methods=('POST',),
    )
