# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from indico.core.plugins import IndicoPluginBlueprint

from indico_affiliations.controllers import (RHAffiliationGroup, RHAffiliationGroups, RHAffiliationTag,
                                             RHAffiliationTags, RHEmailRepresentativesImage,
                                             RHEmailRepresentativesImageUpload, RHEmailRepresentativesMetadata,
                                             RHEmailRepresentativesPreview, RHEmailRepresentativesSend)


blueprint = IndicoPluginBlueprint('affiliations', __name__, url_prefix='/api/admin/plugins/affiliations')

blueprint.add_url_rule('/representatives/email/metadata', 'email_representatives_metadata',
                       RHEmailRepresentativesMetadata, methods=('POST',))
blueprint.add_url_rule('/representatives/email/preview', 'email_representatives_preview', RHEmailRepresentativesPreview,
                       methods=('POST',))
blueprint.add_url_rule('/representatives/email/send', 'email_representatives_send', RHEmailRepresentativesSend,
                       methods=('POST',))
blueprint.add_url_rule('/representatives/email/image', 'email_representatives_image_upload',
                       RHEmailRepresentativesImageUpload, methods=('POST',))
blueprint.add_url_rule('/representatives/email/image/<token>', 'email_representatives_image',
                       RHEmailRepresentativesImage, methods=('GET',))

blueprint.add_url_rule('/groups', 'api_affiliation_groups', RHAffiliationGroups, methods=('GET', 'POST'))
blueprint.add_url_rule('/groups/<int:group_id>', 'api_affiliation_group', RHAffiliationGroup,
                       methods=('GET', 'PATCH', 'DELETE'))
blueprint.add_url_rule('/tags', 'api_affiliation_tags', RHAffiliationTags, methods=('GET', 'POST'))
blueprint.add_url_rule('/tags/<int:tag_id>', 'api_affiliation_tag', RHAffiliationTag,
                       methods=('GET', 'PATCH', 'DELETE'))
