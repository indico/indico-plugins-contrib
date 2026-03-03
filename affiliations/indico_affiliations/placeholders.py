# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from indico.util.countries import get_country
from indico.util.i18n import _
from indico.util.placeholders import ParametrizedPlaceholder, Placeholder

from indico_affiliations.util import resolve_object_path


class AffiliationNamePlaceholder(Placeholder):
    name = 'name'
    description = _('Name of the affiliation')

    @classmethod
    def render(cls, affiliation):
        return affiliation.name


class AffiliationStreetPlaceholder(Placeholder):
    name = 'street'
    description = _('Street of the affiliation')

    @classmethod
    def render(cls, affiliation):
        return affiliation.street


class AffiliationCityPlaceholder(Placeholder):
    name = 'city'
    description = _('City of the affiliation')

    @classmethod
    def render(cls, affiliation):
        return affiliation.city


class AffiliationPostcodePlaceholder(Placeholder):
    name = 'postcode'
    description = _('Postcode of the affiliation')

    @classmethod
    def render(cls, affiliation):
        return affiliation.postcode


class AffiliationCountryPlaceholder(Placeholder):
    name = 'country'
    description = _('Country of the affiliation')

    @classmethod
    def render(cls, affiliation):
        return get_country(affiliation.country_code) or affiliation.country_code


class AffiliationMetadataPlaceholder(ParametrizedPlaceholder):
    name = 'metadata'
    description = None
    param_friendly_name = 'key'
    param_required = True

    @classmethod
    def iter_param_info(cls, **kwargs):
        yield ('key', _("Value in the affiliation's metadata. Supports nested keys like "
                        '"foo.bar" and list indices like "items.0".'))

    @classmethod
    def render(cls, param, affiliation):
        return resolve_object_path(affiliation.meta, param)
