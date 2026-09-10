# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from operator import itemgetter

from flask import request, session
from marshmallow import fields, post_dump
from werkzeug.exceptions import Forbidden

from indico.core.db import db
from indico.core.marshmallow import mm
from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.modules.events.surveys.models.items import SurveyQuestion
from indico.modules.events.surveys.models.submissions import SurveySubmission
from indico.modules.events.surveys.models.surveys import Survey, SurveyState
from indico.modules.events.surveys.schemas import SurveyAnswerSchema as CoreSurveyAnswerSchema
from indico.modules.events.surveys.schemas import SurveySubmissionSchema as CoreSurveySubmissionSchema
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase


class SurveyAnswerSchema(DescribedFieldsMixin, CoreSurveyAnswerSchema):
    class Meta(CoreSurveyAnswerSchema.Meta):
        descriptions = {
            'question_id': 'Identifier of the question that was answered.',
            'question_title': 'Title of the question that was answered.',
            'answer': 'Value the respondent gave, shaped after the type of the question: a string for `text`, a '
                      'number for `number`, a boolean for `bool`, an option for `single_choice` and a list of '
                      'options for `multiselect`.',
        }


class SurveySubmissionSchema(DescribedFieldsMixin, CoreSurveySubmissionSchema):
    class Meta(CoreSurveySubmissionSchema.Meta):
        fields = ('id', 'survey_id', 'survey_title', 'submitted_dt', 'is_anonymous', 'answers')
        descriptions = {
            'id': 'Numeric identifier of the submission, unique across the whole instance.',
            'survey_id': 'Identifier of the survey that was answered.',
            'survey_title': 'Title of the survey that was answered.',
            'submitted_dt': 'Moment the survey was submitted, in UTC.',
            'is_anonymous': 'Whether the submission was made anonymously. The respondent is never exposed, so an '
                            'anonymous submission only differs in that Indico itself does not know who sent it.',
            'answers': 'Answers given to the questions of the survey.',
        }

    answers = fields.List(fields.Nested(SurveyAnswerSchema))


class SurveyQuestionSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """Questionnaire of a survey.

    Core has no schema for survey questions because it only ever renders them as
    a form, so this one is defined here.
    """

    class Meta:
        model = SurveyQuestion
        fields = ('id', 'title', 'description', 'section_title', 'section_position', 'position', 'is_required',
                  'field_type', 'field_data')
        descriptions = {
            'id': 'Numeric identifier of the question, unique across the whole instance.',
            'title': 'Question as it is shown to the respondent.',
            'description': 'Text shown below the question, as Markdown.',
            'section_title': 'Title of the section the question belongs to.',
            'section_position': 'Place of that section in the survey, starting at 1.',
            'position': 'Place of the question inside its section, starting at 1.',
            'is_required': 'Whether the question has to be answered to submit the survey.',
            'field_type': 'Type of answer the question takes: `text`, `number`, `bool`, `single_choice` or '
                          '`multiselect`.',
            'field_data': 'Settings of the field, such as the `options` of a choice question or the `max_length` of '
                          'a text one.',
        }

    section_title = fields.String(attribute='parent.title')
    section_position = fields.Integer(attribute='parent.position')
    field_data = fields.Dict()


class SurveySchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """Survey of an event.

    Core has no schema for surveys because the management interface renders them
    from the model, so this one is defined here.
    """

    class Meta:
        model = Survey
        fields = ('id', 'title', 'introduction', 'anonymous', 'require_user', 'private', 'submission_limit',
                  'start_dt', 'end_dt', 'state', 'is_active')
        descriptions = {
            'id': 'Numeric identifier of the survey, unique across the whole instance.',
            'title': 'Title of the survey.',
            'introduction': 'Text shown above the questionnaire, as plain text.',
            'anonymous': 'Whether submissions are stored without a link to their author.',
            'require_user': 'Whether answering requires being logged in.',
            'private': 'Whether the survey is only reachable through its direct link instead of being listed in '
                       'the event.',
            'submission_limit': 'Maximum number of submissions accepted, or `null` when there is no limit.',
            'start_dt': 'Moment the survey opens, in UTC, or `null` while it has not been scheduled.',
            'end_dt': 'Moment the survey closes, in UTC, or `null` when it stays open.',
            'state': 'Where the survey stands: `not_ready` while it has no questions, `ready_to_open` before it '
                     'starts, `active_and_clean` once open without submissions, `active_and_answered` once it has '
                     'some, `limit_reached` when it hit its submission limit and `finished` after it closed.',
            'is_active': 'Whether the survey is accepting submissions right now.',
            'questions': 'Questions of the survey, in the order they are asked.',
        }

    state = fields.Enum(SurveyState)
    is_active = fields.Boolean()


class SurveyDetailsSchema(SurveySchema):
    class Meta(SurveySchema.Meta):
        fields = (*SurveySchema.Meta.fields, 'questions')

    questions = fields.Nested(SurveyQuestionSchema, many=True)

    @post_dump
    def _sort_questions(self, data, **kwargs):
        data['questions'].sort(key=itemgetter('section_position', 'position'))
        return data


class SurveyMixin:
    """Access checks shared by the survey endpoints.

    Survey managers see every survey of the event. Everybody else sees the ones
    the event advertises, that is the surveys that have started and are not
    restricted to holders of their direct link. Submissions are manager-only,
    and only submitted ones are listed since a draft is not an answer yet.
    """

    EVENT_FEATURE = 'surveys'

    def _process_args(self):
        RHProtectedEventBase._process_args(self)
        self.can_manage = self.event.can_manage(session.user, permission='surveys')

    def _survey_query(self):
        return (Survey.query.with_parent(self.event)
                .filter(~Survey.is_deleted)
                .order_by(db.func.lower(Survey.title), Survey.id))

    def _can_see(self, survey):
        return self.can_manage or (survey.is_visible and not survey.private)


@json_errors
class RHSurvey(SurveyMixin, RHProtectedEventBase):
    def _process_args(self):
        SurveyMixin._process_args(self)
        self.survey = self._survey_query().filter(Survey.id == request.view_args['survey_id']).first_or_404()

    def _check_access(self):
        RHProtectedEventBase._check_access(self)
        if not self._can_see(self.survey):
            raise Forbidden

    def _process_GET(self):
        return SurveyDetailsSchema().jsonify(self.survey)


@json_errors
class RHSurveyList(SurveyMixin, RHListBase, RHProtectedEventBase):
    schema = SurveySchema

    def _query(self):
        return self._survey_query()

    def _can_access(self, obj):
        return self._can_see(obj)


@json_errors
class RHSurveySubmissionList(SurveyMixin, RHListBase, RHProtectedEventBase):
    schema = SurveySubmissionSchema

    def _process_args(self):
        SurveyMixin._process_args(self)
        self.survey = self._survey_query().filter(Survey.id == request.view_args['survey_id']).first_or_404()

    def _check_access(self):
        RHProtectedEventBase._check_access(self)
        if not self.can_manage:
            raise Forbidden

    def _query(self):
        return (SurveySubmission.query
                .filter(SurveySubmission.survey_id == self.survey.id, SurveySubmission.is_submitted)
                .order_by(SurveySubmission.friendly_id))

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(rule='/events/<int:event_id>/surveys', name='surveys', rh=RHSurveyList, schema=SurveySchema, many=True,
             summary='List the surveys of an event', tag='Surveys'),
    Endpoint(rule='/events/<int:event_id>/surveys/<int:survey_id>', name='survey', rh=RHSurvey,
             schema=SurveyDetailsSchema, summary='Survey details', tag='Surveys'),
    Endpoint(rule='/events/<int:event_id>/surveys/<int:survey_id>/submissions', name='survey_submissions',
             rh=RHSurveySubmissionList, schema=SurveySubmissionSchema, many=True,
             summary='List the submitted answers of a survey', tag='Surveys'),
]
