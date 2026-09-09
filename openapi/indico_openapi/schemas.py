# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from marshmallow import fields

from indico.modules.events.contributions.models.persons import SubContributionPersonLink
from indico.modules.events.contributions.schemas import (
    ContributionFieldValueSchema,
    ContributionPersonLinkSchema,
    ContributionTypeSchema,
)
from indico.modules.events.tracks.schemas import TrackSchema
from indico.modules.users.schemas import AffiliationSchema as CoreAffiliationSchema
from indico.modules.users.schemas import BasicUserSchema

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


class UserReferenceSchema(DescribedFieldsMixin, BasicUserSchema):
    class Meta(BasicUserSchema.Meta):
        descriptions = {
            'id': 'Numeric identifier of the user, unique across the whole instance.',
            'identifier': 'Identifier of the user as used by Indico ACLs, such as `User:42`.',
            'first_name': 'First name of the user.',
            'last_name': 'Last name of the user.',
            'full_name': 'Full name of the user, in display order.',
            'email': 'Primary email address of the user.',
            'affiliation': 'Affiliation as free text, which is what gets displayed.',
            'affiliation_meta': 'Predefined affiliation the text was taken from, or `null` when typed by hand.',
            'title': 'Personal title: `mr`, `ms`, `mrs`, `dr`, `prof` or `mx`, or `null` when there is none.',
            'avatar_url': 'URL of the profile picture, relative to the Indico instance.',
        }

    affiliation_meta = fields.Nested(AffiliationSchema, attribute='affiliation_link')


class CustomFieldValueSchema(DescribedFieldsMixin, ContributionFieldValueSchema):
    class Meta(ContributionFieldValueSchema.Meta):
        descriptions = {
            'id': 'Identifier of the custom field this value belongs to.',
            'name': 'Title of the custom field.',
            'value': 'Value stored for this object, in the shape defined by the field type.',
        }


class TrackReferenceSchema(DescribedFieldsMixin, TrackSchema):
    class Meta(TrackSchema.Meta):
        fields = ('id', 'title', 'code')
        descriptions = {
            'id': 'Numeric identifier of the track.',
            'title': 'Title of the track.',
            'code': 'Programme code assigned to the track.',
        }


class ContributionTypeReferenceSchema(DescribedFieldsMixin, ContributionTypeSchema):
    class Meta(ContributionTypeSchema.Meta):
        fields = ('id', 'name')
        descriptions = {
            'id': 'Numeric identifier of the contribution type.',
            'name': 'Name of the type, such as `Poster` or `Oral`.',
        }


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
