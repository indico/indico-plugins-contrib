# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

# Import every model so that importing the package registers all SQLAlchemy mappers,
# regardless of which module triggered the import (relationships reference each other
# by name, so a partial import leaves mappers unresolvable).
from indico_affiliation_extras.models.catalogs import AffiliationCatalog
from indico_affiliation_extras.models.contacts import AffiliationContactList
from indico_affiliation_extras.models.focal_points import FocalPoint
from indico_affiliation_extras.models.groups import AffiliationGroup
from indico_affiliation_extras.models.lists import AffiliationList
from indico_affiliation_extras.models.tags import AffiliationTag


__all__ = (
    'AffiliationCatalog',
    'AffiliationContactList',
    'AffiliationGroup',
    'AffiliationList',
    'AffiliationTag',
    'FocalPoint',
)
