# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from werkzeug.exceptions import NotFound

from indico.modules.events.registration.controllers.display import RHRegistrationFormFieldActionBase
from indico.modules.events.registration.controllers.management import RHManageRegistrationFieldActionBase
from indico.modules.users.util import SearchAffiliationsMixin
from indico.util.marshmallow import ModelField
from indico.web.args import use_kwargs

from indico_affiliation_extras.models.lists import AffiliationList
from indico_affiliation_extras.util import get_default_catalog


class SearchRepresentationAffiliationsMixin(SearchAffiliationsMixin):
    """Shared search context for representation affiliation RHs."""

    normalize_url_spec = {
        'locators': {
            lambda self: self.field,
            lambda self: {'affiliation_list_id': self.affiliation_list.id},
        },
        'skipped_args': {'section_id'},
    }

    @use_kwargs(
        {'affiliation_list': ModelField(AffiliationList, required=True, data_key='affiliation_list_id')},
        location='view_args',
    )
    def _process_args(self, affiliation_list):
        super()._process_args()
        self.affiliation_list = affiliation_list
        catalog = get_default_catalog(self.event)
        if not catalog or self.affiliation_list.catalog_id != catalog.id or not self.affiliation_list.is_enabled:
            raise NotFound

    @property
    def context(self):
        return {
            'event': self.event,
            'registration_form': self.regform,
            'field': self.field,
            'affiliation_list': self.affiliation_list,
        }


class RHSearchRepresentationAffiliation(SearchRepresentationAffiliationsMixin, RHRegistrationFormFieldActionBase):
    """Public representation affiliation search for registrants."""


class RHManageSearchRepresentationAffiliation(
    SearchRepresentationAffiliationsMixin, RHManageRegistrationFieldActionBase
):
    """Management representation affiliation search for registration managers."""
