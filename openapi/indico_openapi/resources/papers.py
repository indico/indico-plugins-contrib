# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from flask import request, session
from marshmallow import fields, pre_dump
from werkzeug.exceptions import Forbidden

from indico.modules.events.contributions.models.contributions import Contribution
from indico.modules.events.contributions.schemas import BasicContributionSchema
from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.modules.events.papers.models.revisions import PaperRevisionState
from indico.modules.events.papers.schemas import PaperFileSchema as CorePaperFileSchema
from indico.modules.events.papers.schemas import PaperRevisionSchema as CorePaperRevisionSchema
from indico.modules.events.papers.schemas import PaperSchema as CorePaperSchema
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase
from indico_openapi.schemas import UserReferenceSchema


class ContributionReferenceSchema(DescribedFieldsMixin, BasicContributionSchema):
    class Meta(BasicContributionSchema.Meta):
        descriptions = {
            'id': 'Numeric identifier of the contribution, unique across the whole instance.',
            'title': 'Title of the contribution.',
            'friendly_id': 'Number shown to users, unique within the event.',
            'code': 'Programme code assigned to the contribution.',
        }


class PaperFileSchema(DescribedFieldsMixin, CorePaperFileSchema):
    class Meta(CorePaperFileSchema.Meta):
        fields = ('id', 'revision_id', 'filename', 'content_type', 'download_url')
        descriptions = {
            'id': 'Numeric identifier of the file.',
            'revision_id': 'Identifier of the revision the file was uploaded with.',
            'filename': 'Name of the file as uploaded.',
            'content_type': 'MIME type of the file, such as `application/pdf`.',
            'download_url': 'URL the file is downloaded from, relative to the Indico instance.',
        }


class PaperRevisionSchema(DescribedFieldsMixin, CorePaperRevisionSchema):
    class Meta(CorePaperRevisionSchema.Meta):
        fields = ('id', 'number', 'state', 'submitted_dt', 'submitter', 'judgment_dt', 'judge', 'judgment_comment',
                  'is_last_revision', 'files', 'spotlight_file')
        descriptions = {
            'id': 'Numeric identifier of the revision, unique across the whole instance.',
            'number': 'Position of the revision among the revisions of the paper, starting at `1`.',
            'state': 'Where the revision stands: `submitted`, `accepted`, `rejected` or `to_be_corrected`.',
            'submitted_dt': 'Moment the revision was submitted, in UTC.',
            'submitter': 'User who submitted the revision.',
            'judgment_dt': 'Moment the revision was judged, in UTC, or `null` when it has not been judged.',
            'judge': 'User who judged the revision, or `null` when it has not been judged.',
            'judgment_comment': 'Comment the judge left when accepting or rejecting the revision.',
            'is_last_revision': 'Whether this is the most recent revision of the paper.',
            'files': 'Files uploaded with the revision.',
            'spotlight_file': 'The single publishable PDF of the revision, or `null` when there is not exactly one.',
        }

    submitter = fields.Nested(UserReferenceSchema)
    judge = fields.Nested(UserReferenceSchema)
    files = fields.List(fields.Nested(PaperFileSchema))
    spotlight_file = fields.Nested(PaperFileSchema)


class PaperSchema(DescribedFieldsMixin, CorePaperSchema):
    class Meta:
        fields = ('contribution', 'state', 'is_in_final_state', 'revision_count', 'last_revision')
        descriptions = {
            'contribution': 'Contribution the paper was submitted for.',
            'state': 'State of the most recent revision: `submitted`, `accepted`, `rejected` or `to_be_corrected`.',
            'is_in_final_state': 'Whether the paper was accepted or rejected, so no further revision is expected.',
            'revision_count': 'Number of revisions submitted so far.',
            'last_revision': 'Most recent revision of the paper.',
            'revisions': 'Every revision of the paper, oldest first.',
        }

    contribution = fields.Nested(ContributionReferenceSchema)
    state = fields.Enum(PaperRevisionState)
    last_revision = fields.Nested(PaperRevisionSchema)
    revisions = fields.List(fields.Nested(PaperRevisionSchema))

    @pre_dump
    def _get_paper(self, contrib, **kwargs):
        # a paper is a view over its contribution, which is what the queries return
        return contrib.paper


class PaperDetailsSchema(PaperSchema):
    class Meta(PaperSchema.Meta):
        fields = ('contribution', 'state', 'is_in_final_state', 'revision_count', 'revisions')


class PaperMixin:
    """Access checks shared by the paper endpoints.

    A paper is readable by the people listed on its contribution, by whoever
    may submit it, by the paper managers and by the judges and reviewers
    assigned to it. The reviews, ratings and comments written about it follow
    their own rules and are not exposed.
    """

    EVENT_FEATURE = 'papers'

    def _contribution_query(self):
        return (Contribution.query.with_parent(self.event)
                .filter(~Contribution.is_deleted, Contribution._paper_last_revision.has())
                .order_by(Contribution.friendly_id))

    def _can_see(self, contrib):
        paper = contrib.paper
        return (contrib.is_user_associated(session.user, check_abstract=True) or
                contrib.can_submit_proceedings(session.user) or
                self.event.cfp.is_manager(session.user) or
                paper.can_review(session.user) or
                paper.can_judge(session.user))


@json_errors
class RHPaper(PaperMixin, RHProtectedEventBase):
    def _process_args(self):
        RHProtectedEventBase._process_args(self)
        self.contrib = (self._contribution_query()
                        .filter(Contribution.id == request.view_args['contrib_id']).first_or_404())

    def _check_access(self):
        RHProtectedEventBase._check_access(self)
        if not self._can_see(self.contrib):
            raise Forbidden

    def _process_GET(self):
        return PaperDetailsSchema().jsonify(self.contrib)


@json_errors
class RHPaperList(PaperMixin, RHListBase, RHProtectedEventBase):
    schema = PaperSchema

    def _query(self):
        return self._contribution_query()

    def _can_access(self, obj):
        return self._can_see(obj)


ENDPOINTS = [
    Endpoint(rule='/events/<int:event_id>/papers', name='papers', rh=RHPaperList, schema=PaperSchema, many=True,
             summary='List the papers of an event', tag='Papers'),
    Endpoint(rule='/events/<int:event_id>/contributions/<int:contrib_id>/paper', name='paper', rh=RHPaper,
             schema=PaperDetailsSchema, summary='Paper of a contribution', tag='Papers'),
]
