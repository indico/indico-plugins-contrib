# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from marshmallow import fields

from indico.modules.users.schemas import AffiliationSchema as CoreAffiliationSchema

from indico_openapi.resources.base import DescribedFieldsMixin


class AffiliationSchema(DescribedFieldsMixin, CoreAffiliationSchema):
    class Meta(CoreAffiliationSchema.Meta):
        fields = (*CoreAffiliationSchema.Meta.fields, 'country_name')
        descriptions = {
            'id': 'Numeric identifier of the predefined affiliation.',
            'name': 'Name of the organisation.',
            'code': 'Short code of the organisation, such as `CERN`.',
            'alt_names': 'Other names the organisation is also known by.',
            'street': 'Street of the postal address.',
            'postcode': 'Postal code of the address.',
            'city': 'City of the address.',
            'country_code': 'ISO 3166-1 alpha-2 code of the country, such as `CH`.',
            'country_name': 'Name of the country in English, derived from `country_code`.',
            'meta': 'Extra data attached to the affiliation by the instance administrators.',
        }

    country_name = fields.String()
