# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from flask import request, session
from marshmallow import fields
from werkzeug.exceptions import Forbidden

from indico.modules.events.abstracts.models.abstracts import Abstract
from indico.modules.events.abstracts.schemas import AbstractFileSchema as CoreAbstractFileSchema
from indico.modules.events.abstracts.schemas import AbstractPersonLinkSchema
from indico.modules.events.abstracts.schemas import AbstractSchema as CoreAbstractSchema
from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase
from indico_openapi.schemas import (
    AffiliationSchema,
    ContributionTypeReferenceSchema,
    CustomFieldValueSchema,
    TrackReferenceSchema,
    UserReferenceSchema,
)


class AbstractPersonSchema(DescribedFieldsMixin, AbstractPersonLinkSchema):
    class Meta(AbstractPersonLinkSchema.Meta):
        descriptions = {
            'id': 'Numeric identifier of the link between the person and the abstract.',
            'person_id': 'Identifier of the person within the event, shared by everything they take part in.',
            'email': 'Email address of the person.',
            'first_name': 'First name of the person.',
            'last_name': 'Last name of the person.',
            'title': 'Personal title as displayed, such as `Dr` or `Prof.`, or an empty string when there is none.',
            'affiliation': 'Affiliation as free text, which is what gets displayed.',
            'affiliation_link': 'Predefined affiliation the text was taken from, or `null` when typed by hand.',
            'address': 'Postal address of the person.',
            'phone': 'Phone number of the person.',
            'is_speaker': 'Whether the person presents the abstract.',
            'author_type': 'Role as author: `none`, `primary` or `secondary`.',
        }

    affiliation_link = fields.Nested(AffiliationSchema)


class AbstractFileSchema(DescribedFieldsMixin, CoreAbstractFileSchema):
    class Meta(CoreAbstractFileSchema.Meta):
        fields = ('id', 'filename', 'content_type', 'md5', 'download_url')
        descriptions = {
            'id': 'Numeric identifier of the file.',
            'filename': 'Name of the file as uploaded.',
            'content_type': 'MIME type of the file, such as `application/pdf`.',
            'md5': 'MD5 hash of the contents, so a client can tell whether its copy is current.',
            'download_url': 'Absolute URL the file is downloaded from.',
        }


class AbstractSchema(DescribedFieldsMixin, CoreAbstractSchema):
    class Meta(CoreAbstractSchema.Meta):
        fields = ('id', 'friendly_id', 'title', 'content', 'state', 'submitted_dt', 'modified_dt', 'judgment_dt',
                  'submitter', 'modified_by', 'judge', 'submission_comment', 'judgment_comment',
                  'submitted_contrib_type', 'accepted_contrib_type', 'accepted_track', 'submitted_for_tracks',
                  'reviewed_for_tracks', 'duplicate_of_id', 'merged_into_id', 'persons', 'custom_fields', 'files')
        descriptions = {
            'id': 'Numeric identifier of the abstract, unique across the whole instance.',
            'friendly_id': 'Number shown to users, unique within the event and stable once assigned.',
            'title': 'Title of the abstract.',
            'content': 'Body of the abstract, as plain text.',
            'state': 'Where the abstract stands: `submitted`, `withdrawn`, `accepted`, `rejected`, `merged`, '
                     '`duplicate` or `invited`.',
            'submitted_dt': 'Moment the abstract was submitted, in UTC.',
            'modified_dt': 'Moment the abstract was last edited, in UTC, or `null` when never edited.',
            'judgment_dt': 'Moment the abstract was judged, in UTC, or `null` when it has not been judged.',
            'submitter': 'User who submitted the abstract.',
            'modified_by': 'User who last edited the abstract, or `null` when never edited.',
            'judge': 'User who judged the abstract, or `null` when it has not been judged.',
            'submission_comment': 'Comment the submitter left for the organisers.',
            'judgment_comment': 'Comment the judge left when accepting or rejecting the abstract.',
            'submitted_contrib_type': 'Contribution type the submitter asked for, or `null` when none was chosen.',
            'accepted_contrib_type': 'Contribution type the abstract was accepted as, or `null`.',
            'accepted_track': 'Track the abstract was accepted for, or `null`.',
            'submitted_for_tracks': 'Tracks the abstract was submitted for.',
            'reviewed_for_tracks': 'Tracks the abstract is being reviewed for.',
            'duplicate_of_id': 'Identifier of the abstract this one duplicates, set only in state `duplicate`.',
            'merged_into_id': 'Identifier of the abstract this one was merged into, set only in state `merged`.',
            'persons': 'Speakers and authors of the abstract.',
            'custom_fields': 'Values of the custom fields defined by the call for abstracts.',
            'files': 'Files attached to the abstract by the submitter.',
        }

    submitter = fields.Nested(UserReferenceSchema)
    modified_by = fields.Nested(UserReferenceSchema)
    judge = fields.Nested(UserReferenceSchema)
    submitted_contrib_type = fields.Nested(ContributionTypeReferenceSchema)
    accepted_contrib_type = fields.Nested(ContributionTypeReferenceSchema)
    accepted_track = fields.Nested(TrackReferenceSchema)
    submitted_for_tracks = fields.Nested(TrackReferenceSchema, many=True)
    reviewed_for_tracks = fields.Nested(TrackReferenceSchema, many=True)
    persons = fields.Nested(AbstractPersonSchema, attribute='person_links', many=True)
    custom_fields = fields.Nested(CustomFieldValueSchema, attribute='field_values', many=True)
    files = fields.Nested(AbstractFileSchema, many=True)


class AbstractMixin:
    """Access checks shared by the abstract endpoints.

    An abstract is readable by its submitter, by the people listed on it, by
    the abstract managers and by the conveners and reviewers of the tracks it
    is being reviewed for. The reviews, ratings and comments written about it
    follow their own rules and are not exposed.
    """

    EVENT_FEATURE = 'abstracts'

    @property
    def management(self):
        # the abstract URLs exist twice, in the management area and in the display one,
        # and Indico picks between them from the request handler, so the links we serve
        # are the ones the caller would follow in the interface
        return self.event.can_manage(session.user, permission='abstracts')

    def _abstract_query(self):
        return Abstract.query.with_parent(self.event).filter_by(is_deleted=False).order_by(Abstract.friendly_id)


@json_errors
class RHAbstract(AbstractMixin, RHProtectedEventBase):
    def _process_args(self):
        RHProtectedEventBase._process_args(self)
        self.abstract = self._abstract_query().filter_by(id=request.view_args['abstract_id']).first_or_404()

    def _check_access(self):
        RHProtectedEventBase._check_access(self)
        if not self.abstract.can_access(session.user):
            raise Forbidden

    def _process_GET(self):
        return AbstractSchema().jsonify(self.abstract)


@json_errors
class RHAbstractList(AbstractMixin, RHListBase, RHProtectedEventBase):
    schema = AbstractSchema

    def _query(self):
        return self._abstract_query()


ENDPOINTS = [
    Endpoint(rule='/events/<int:event_id>/abstracts', name='abstracts', rh=RHAbstractList, schema=AbstractSchema,
             many=True, summary='List the abstracts of an event', tag='Abstracts'),
    Endpoint(rule='/events/<int:event_id>/abstracts/<int:abstract_id>', name='abstract', rh=RHAbstract,
             schema=AbstractSchema, summary='Abstract details', tag='Abstracts'),
]
