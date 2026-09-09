# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from marshmallow import fields

from indico.modules.events.contributions.models.persons import SubContributionPersonLink
from indico.modules.events.contributions.schemas import ContributionPersonLinkSchema
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


class ContributionPersonSchema(DescribedFieldsMixin, ContributionPersonLinkSchema):
    class Meta(ContributionPersonLinkSchema.Meta):
        descriptions = {
            'id': 'Numeric identifier of the link between the person and the contribution.',
            'person_id': 'Identifier of the person within the event, shared by every contribution they take part in.',
            'email': 'Email address. Only present for users who can manage the contribution.',
            'email_hash': 'MD5 hash of the email address, so an avatar can be fetched without exposing the address.',
            'first_name': 'First name of the person.',
            'last_name': 'Last name of the person.',
            'full_name': 'Full name of the person, in display order.',
            'title': 'Personal title, such as `Dr` or `Prof`.',
            'affiliation': 'Affiliation as free text, which is what gets displayed.',
            'affiliation_link': 'Predefined affiliation the text was taken from, or `null` when it was typed by hand.',
            'address': 'Postal address. Only present for users who can manage the contribution.',
            'phone': 'Phone number. Only present for users who can manage the contribution.',
            'is_speaker': 'Whether the person speaks in the contribution.',
            'author_type': 'Role as author: `none`, `primary` or `secondary`.',
        }

    affiliation_link = fields.Nested(AffiliationSchema)


class SubContributionPersonSchema(ContributionPersonSchema):
    class Meta(ContributionPersonSchema.Meta):
        model = SubContributionPersonLink
        fields = ('id', 'person_id', 'email', 'email_hash', 'first_name', 'last_name', 'full_name', 'title',
                  'affiliation', 'affiliation_link', 'address', 'phone')
