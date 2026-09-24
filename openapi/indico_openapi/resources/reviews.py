# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from flask import request, session
from marshmallow import fields, post_dump
from werkzeug.exceptions import Forbidden, NotFound

from indico.modules.events.abstracts.models.reviews import AbstractAction, AbstractCommentVisibility
from indico.modules.events.abstracts.schemas import AbstractCommentSchema as CoreAbstractCommentSchema
from indico.modules.events.abstracts.schemas import AbstractReviewQuestionSchema as CoreAbstractReviewQuestionSchema
from indico.modules.events.abstracts.schemas import AbstractReviewRatingSchema as CoreAbstractReviewRatingSchema
from indico.modules.events.abstracts.schemas import AbstractReviewSchema as CoreAbstractReviewSchema
from indico.modules.events.abstracts.schemas import AbstractSchema as CoreAbstractSchema
from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.modules.events.papers.models.reviews import PaperAction, PaperCommentVisibility, PaperReviewType
from indico.modules.events.papers.schemas import PaperRatingSchema as CorePaperRatingSchema
from indico.modules.events.papers.schemas import PaperReviewCommentSchema as CorePaperReviewCommentSchema
from indico.modules.events.papers.schemas import PaperReviewQuestionSchema as CorePaperReviewQuestionSchema
from indico.modules.events.papers.schemas import PaperReviewSchema as CorePaperReviewSchema
from indico.web.rh import json_errors

from indico_openapi.resources.abstracts import AbstractMixin, RHAbstract
from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, jsonify_results
from indico_openapi.resources.papers import PaperMixin, RHPaper
from indico_openapi.schemas import ContributionTypeReferenceSchema, TrackReferenceSchema, UserReferenceSchema


QUESTION_DESCRIPTIONS = {
    'id': 'Numeric identifier of the question.',
    'title': 'The question itself, as the reviewers read it.',
    'description': 'Longer explanation shown under the question, or an empty string when there is none.',
    'field_type': 'How the question is answered: `rating`, `bool` or `text`.',
    'field_data': 'Settings of the field, such as the bounds of a rating scale, in the shape its type defines.',
    'is_required': 'Whether a reviewer has to answer the question before submitting.',
    'no_score': 'Whether the answer is left out of the score of the review.',
    'position': 'Position of the question in the reviewing form, starting at `1`.',
}

RATING_DESCRIPTIONS = {
    'question': 'The question that was answered.',
    'value': 'The answer, in the shape defined by the type of the question.',
}

COMMENT_DESCRIPTIONS = {
    'id': 'Numeric identifier of the comment.',
    'user': 'User who wrote the comment.',
    'text': 'The comment itself, as Markdown.',
    'created_dt': 'Moment the comment was written, in UTC.',
    'modified_dt': 'Moment the comment was last edited, in UTC, or `null` when never edited.',
    'modified_by': 'User who last edited the comment, or `null` when never edited.',
}


class AbstractReviewQuestionSchema(DescribedFieldsMixin, CoreAbstractReviewQuestionSchema):
    """One question the reviewers of an abstract answer."""

    class Meta(CoreAbstractReviewQuestionSchema.Meta):
        fields = ('id', 'title', 'description', 'field_type', 'field_data', 'is_required', 'no_score', 'position')
        descriptions = QUESTION_DESCRIPTIONS


class AbstractReviewRatingSchema(DescribedFieldsMixin, CoreAbstractReviewRatingSchema):
    """The answer a review gave to one question."""

    class Meta(CoreAbstractReviewRatingSchema.Meta):
        descriptions = RATING_DESCRIPTIONS

    question = fields.Nested(AbstractReviewQuestionSchema)

    @post_dump(pass_many=True)
    def _sort_by_question(self, data, many, **kwargs):
        return sorted(data, key=lambda rating: rating['question']['position']) if many else data


class AbstractReferenceSchema(DescribedFieldsMixin, CoreAbstractSchema):
    """The abstract a review proposes to merge into or mark as duplicated."""

    class Meta(CoreAbstractSchema.Meta):
        fields = ('id', 'friendly_id', 'title')
        descriptions = {
            'id': 'Numeric identifier of the abstract, unique across the whole instance.',
            'friendly_id': 'Number shown to users, unique within the event.',
            'title': 'Title of the abstract.',
        }


class AbstractReviewSchema(DescribedFieldsMixin, CoreAbstractReviewSchema):
    """One review of an abstract, written for a single track."""

    class Meta(CoreAbstractReviewSchema.Meta):
        fields = (
            'id',
            'user',
            'track',
            'comment',
            'proposed_action',
            'proposed_contrib_type',
            'proposed_related_abstract',
            'proposed_tracks',
            'score',
            'ratings',
            'created_dt',
            'modified_dt',
        )
        descriptions = {
            'id': 'Numeric identifier of the review.',
            'user': 'Reviewer who wrote the review.',
            'track': 'Track the abstract was reviewed for, or `null` when the review was written without one.',
            'comment': 'Comment the reviewer left, as Markdown.',
            'proposed_action': 'What the reviewer proposes: `accept`, `reject`, `change_tracks`, `mark_as_duplicate` '
            'or `merge`.',
            'proposed_contrib_type': 'Contribution type proposed with an acceptance, or `null`.',
            'proposed_related_abstract': 'Abstract this one was proposed to be merged into or to duplicate, or `null`.',
            'proposed_tracks': 'Tracks proposed instead of the current ones, set only with `change_tracks`.',
            'score': 'Average of the answers that count towards a score, or `null` when there is none.',
            'ratings': 'Answers the reviewer gave to the questions of the reviewing form.',
            'created_dt': 'Moment the review was written, in UTC.',
            'modified_dt': 'Moment the review was last edited, in UTC, or `null` when never edited.',
        }

    user = fields.Nested(UserReferenceSchema)
    track = fields.Nested(TrackReferenceSchema)
    proposed_action = fields.Enum(AbstractAction)
    proposed_contrib_type = fields.Nested(ContributionTypeReferenceSchema, attribute='proposed_contribution_type')
    proposed_related_abstract = fields.Nested(AbstractReferenceSchema)
    proposed_tracks = fields.Nested(TrackReferenceSchema, many=True)
    score = fields.Float()
    ratings = fields.Nested(AbstractReviewRatingSchema, many=True)


class AbstractCommentSchema(DescribedFieldsMixin, CoreAbstractCommentSchema):
    """One comment left on an abstract."""

    class Meta(CoreAbstractCommentSchema.Meta):
        fields = ('id', 'user', 'text', 'visibility', 'created_dt', 'modified_dt', 'modified_by')
        descriptions = COMMENT_DESCRIPTIONS | {
            'visibility': 'Who the comment was addressed to: `judges`, `conveners`, `reviewers`, `contributors` '
            'or `users`.',
        }

    user = fields.Nested(UserReferenceSchema)
    modified_by = fields.Nested(UserReferenceSchema)
    visibility = fields.Enum(AbstractCommentVisibility)


class ApiPaperReviewQuestionSchema(DescribedFieldsMixin, CorePaperReviewQuestionSchema):
    """One question the reviewers of a paper answer."""

    class Meta(CorePaperReviewQuestionSchema.Meta):
        fields = (
            'id',
            'type',
            'title',
            'description',
            'field_type',
            'field_data',
            'is_required',
            'no_score',
            'position',
        )
        descriptions = QUESTION_DESCRIPTIONS | {
            'type': 'Kind of reviewing the question belongs to: `layout` or `content`.',
        }

    type = fields.Enum(PaperReviewType)


class PaperReviewRatingSchema(DescribedFieldsMixin, CorePaperRatingSchema):
    """The answer a review gave to one question."""

    class Meta(CorePaperRatingSchema.Meta):
        fields = ('question', 'value')
        descriptions = RATING_DESCRIPTIONS

    question = fields.Nested(ApiPaperReviewQuestionSchema)


class PaperReviewSchema(DescribedFieldsMixin, CorePaperReviewSchema):
    """One review of a paper revision, written for a single kind of reviewing."""

    class Meta(CorePaperReviewSchema.Meta):
        fields = ('id', 'type', 'user', 'comment', 'proposed_action', 'score', 'ratings', 'created_dt', 'modified_dt')
        descriptions = {
            'id': 'Numeric identifier of the review.',
            'type': 'Kind of reviewing the review belongs to: `layout` or `content`.',
            'user': 'Reviewer who wrote the review.',
            'comment': 'Comment the reviewer left, as Markdown.',
            'proposed_action': 'What the reviewer proposes: `accept`, `reject` or `to_be_corrected`.',
            'score': 'Average of the answers that count towards a score, or `null` when there is none.',
            'ratings': 'Answers the reviewer gave to the questions of the reviewing form.',
            'created_dt': 'Moment the review was written, in UTC.',
            'modified_dt': 'Moment the review was last edited, in UTC, or `null` when never edited.',
        }

    type = fields.Enum(PaperReviewType)
    user = fields.Nested(UserReferenceSchema)
    proposed_action = fields.Enum(PaperAction)
    score = fields.Float()
    ratings = fields.Nested(PaperReviewRatingSchema, many=True)


class PaperCommentSchema(DescribedFieldsMixin, CorePaperReviewCommentSchema):
    """One comment left on a paper revision."""

    class Meta(CorePaperReviewCommentSchema.Meta):
        fields = ('id', 'user', 'text', 'visibility', 'created_dt', 'modified_dt', 'modified_by')
        descriptions = COMMENT_DESCRIPTIONS | {
            'visibility': 'Who the comment was addressed to: `judges`, `reviewers`, `contributors` or `users`.',
        }

    user = fields.Nested(UserReferenceSchema)
    modified_by = fields.Nested(UserReferenceSchema)
    visibility = fields.Enum(PaperCommentVisibility)


def visible_to_caller(entries):
    """Keep the entries of a timeline the caller is allowed to read, oldest first.

    Reviewing is written so that each role reads a different part of the same
    timeline, and every entry knows who may see it, which is the check the
    interface applies when rendering it.
    """
    entries = [entry for entry in entries if entry.can_view(session.user)]
    return sorted(entries, key=lambda entry: (entry.created_dt, entry.id))


@json_errors
class RHAbstractReviews(RHAbstract):
    def _process_GET(self):
        return jsonify_results(AbstractReviewSchema(many=True), visible_to_caller(self.abstract.reviews))


@json_errors
class RHAbstractComments(RHAbstract):
    def _process_GET(self):
        return jsonify_results(AbstractCommentSchema(many=True), visible_to_caller(self.abstract.comments))


@json_errors
class RHAbstractReviewQuestions(AbstractMixin, RHProtectedEventBase):
    def _check_access(self):
        RHProtectedEventBase._check_access(self)
        if not self.management:
            raise Forbidden

    def _process_GET(self):
        return jsonify_results(AbstractReviewQuestionSchema(many=True), self.event.abstract_review_questions)


class PaperRevisionMixin:
    """Locate the revision the reviews and comments of a paper hang off."""

    def _process_args(self):
        super()._process_args()
        revision_id = request.view_args['revision_id']
        self.revision = next((r for r in self.contrib.paper.revisions if r.id == revision_id), None)
        if self.revision is None:
            raise NotFound


@json_errors
class RHPaperRevisionReviews(PaperRevisionMixin, RHPaper):
    def _process_GET(self):
        return jsonify_results(PaperReviewSchema(many=True), visible_to_caller(self.revision.reviews))


@json_errors
class RHPaperRevisionComments(PaperRevisionMixin, RHPaper):
    def _process_GET(self):
        return jsonify_results(PaperCommentSchema(many=True), visible_to_caller(self.revision.comments))


@json_errors
class RHPaperReviewQuestions(PaperMixin, RHProtectedEventBase):
    def _check_access(self):
        RHProtectedEventBase._check_access(self)
        if not self.event.cfp.is_manager(session.user):
            raise Forbidden

    def _process_GET(self):
        return jsonify_results(ApiPaperReviewQuestionSchema(many=True), self.event.paper_review_questions)


ENDPOINTS = [
    Endpoint(
        rule='/events/<int:event_id>/abstracts/<int:abstract_id>/reviews',
        name='abstract_reviews',
        rh=RHAbstractReviews,
        schema=AbstractReviewSchema,
        many=True,
        summary='List the reviews of an abstract',
        tag='Abstracts',
    ),
    Endpoint(
        rule='/events/<int:event_id>/abstracts/<int:abstract_id>/comments',
        name='abstract_comments',
        rh=RHAbstractComments,
        schema=AbstractCommentSchema,
        many=True,
        summary='List the comments left on an abstract',
        tag='Abstracts',
    ),
    Endpoint(
        rule='/events/<int:event_id>/abstract-review-questions',
        name='abstract_review_questions',
        rh=RHAbstractReviewQuestions,
        schema=AbstractReviewQuestionSchema,
        many=True,
        summary='List the questions abstract reviewers answer',
        tag='Abstracts',
    ),
    Endpoint(
        rule='/events/<int:event_id>/contributions/<int:contrib_id>/paper/revisions/<int:revision_id>/reviews',
        name='paper_reviews',
        rh=RHPaperRevisionReviews,
        schema=PaperReviewSchema,
        many=True,
        summary='List the reviews of a paper revision',
        tag='Papers',
    ),
    Endpoint(
        rule='/events/<int:event_id>/contributions/<int:contrib_id>/paper/revisions/<int:revision_id>/comments',
        name='paper_comments',
        rh=RHPaperRevisionComments,
        schema=PaperCommentSchema,
        many=True,
        summary='List the comments left on a paper revision',
        tag='Papers',
    ),
    Endpoint(
        rule='/events/<int:event_id>/paper-review-questions',
        name='paper_review_questions',
        rh=RHPaperReviewQuestions,
        schema=ApiPaperReviewQuestionSchema,
        many=True,
        summary='List the questions paper reviewers answer',
        tag='Papers',
    ),
]
