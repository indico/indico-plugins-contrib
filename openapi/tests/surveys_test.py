# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from datetime import timedelta

import pytest

from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.modules.events.features.util import set_feature_enabled
from indico.modules.events.surveys.models.items import SurveyQuestion, SurveySection
from indico.modules.events.surveys.models.submissions import SurveyAnswer, SurveySubmission
from indico.modules.events.surveys.models.surveys import Survey
from indico.util.date_time import now_utc


@pytest.fixture
def create_survey(db, dummy_event):
    def _create_survey(title, **params):
        params.setdefault('introduction', 'Tell us what you think')
        params.setdefault('start_dt', now_utc() - timedelta(days=1))
        params.setdefault('end_dt', now_utc() + timedelta(days=1))
        survey = Survey(event=dummy_event, title=title, **params)
        section = SurveySection(survey=survey, title='General', display_as_section=True, position=1)
        SurveyQuestion(survey=survey, parent=section, title='Your name', description='As you want it published',
                       field_type='text', is_required=True, position=1, field_data={})
        db.session.add(survey)
        db.session.flush()
        return survey

    return _create_survey


@pytest.fixture
def dummy_survey(create_survey):
    return create_survey('Feedback')


@pytest.fixture
def survey_manager(db, dummy_event, dummy_user):
    dummy_event.update_principal(dummy_user, permissions={'surveys'})
    db.session.flush()


@pytest.fixture
def dummy_submission(db, dummy_survey, dummy_user):
    submission = SurveySubmission(survey=dummy_survey, user=dummy_user, is_submitted=True, submitted_dt=now_utc())
    submission.answers.append(SurveyAnswer(question=next(iter(dummy_survey.questions)), data='Alice'))
    db.session.add(submission)
    db.session.flush()
    return submission


def test_survey_details(dummy_survey, dummy_event, outsider_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/surveys/{dummy_survey.id}', headers=outsider_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_survey.id
    assert resp.json['title'] == 'Feedback'
    assert resp.json['introduction'] == 'Tell us what you think'
    assert resp.json['state'] == 'active_and_clean'
    assert resp.json['is_active'] is True
    assert resp.json['anonymous'] is False
    assert resp.json['require_user'] is True
    assert resp.json['submission_limit'] is None


def test_survey_questions(dummy_survey, dummy_event, outsider_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/surveys/{dummy_survey.id}', headers=outsider_headers)
    question = resp.json['questions'][0]
    assert question['id'] == next(iter(dummy_survey.questions)).id
    assert question['title'] == 'Your name'
    assert question['description'] == 'As you want it published'
    assert question['section_title'] == 'General'
    assert question['section_position'] == 1
    assert question['position'] == 1
    assert question['field_type'] == 'text'
    assert question['is_required'] is True
    assert question['field_data'] == {}


def test_survey_questions_are_sorted(db, dummy_survey, dummy_event, outsider_headers, test_client):
    section = SurveySection(survey=dummy_survey, title='Extra', display_as_section=True, position=0)
    SurveyQuestion(survey=dummy_survey, parent=section, title='Anything else?', field_type='text', is_required=False,
                   position=1, field_data={})
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/surveys/{dummy_survey.id}', headers=outsider_headers)
    assert [q['title'] for q in resp.json['questions']] == ['Anything else?', 'Your name']


def test_survey_list(dummy_survey, create_survey, dummy_event, outsider_headers, test_client):
    other = create_survey('Another survey')
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/surveys', headers=outsider_headers)
    assert resp.status_code == 200
    assert [s['id'] for s in resp.json['results']] == [other.id, dummy_survey.id]
    assert 'questions' not in resp.json['results'][0]


def test_survey_that_has_not_started_is_hidden(dummy_survey, create_survey, dummy_event, outsider_headers,
                                               test_client):
    upcoming = create_survey('Upcoming survey', start_dt=None, end_dt=None)
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/surveys', headers=outsider_headers)
    assert [s['id'] for s in resp.json['results']] == [dummy_survey.id]
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/surveys/{upcoming.id}', headers=outsider_headers)
    assert resp.status_code == 403


def test_private_survey_is_hidden(dummy_survey, create_survey, dummy_event, outsider_headers, test_client):
    private = create_survey('Private survey', private=True)
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/surveys', headers=outsider_headers)
    assert [s['id'] for s in resp.json['results']] == [dummy_survey.id]
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/surveys/{private.id}', headers=outsider_headers)
    assert resp.status_code == 403


def test_survey_manager_sees_every_survey(dummy_survey, create_survey, dummy_event, survey_manager,
                                          token_headers, test_client):
    private = create_survey('Private survey', private=True)
    upcoming = create_survey('Upcoming survey', start_dt=None, end_dt=None)
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/surveys', headers=token_headers)
    states = {s['id']: s['state'] for s in resp.json['results']}
    assert set(states) == {dummy_survey.id, private.id, upcoming.id}
    assert states[upcoming.id] == 'ready_to_open'


def test_deleted_survey_is_not_found(db, dummy_survey, dummy_event, token_headers, test_client):
    dummy_survey.is_deleted = True
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/surveys/{dummy_survey.id}', headers=token_headers)
    assert resp.status_code == 404
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/surveys', headers=token_headers)
    assert resp.json['results'] == []


def test_surveys_require_the_feature(db, dummy_survey, dummy_event, token_headers, test_client):
    set_feature_enabled(dummy_event, 'surveys', False)
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/surveys', headers=token_headers)
    assert resp.status_code == 404


def test_surveys_denied_without_event_access(db, dummy_survey, dummy_event, outsider_headers, test_client):
    dummy_event.protection_mode = ProtectionMode.protected
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/surveys/{dummy_survey.id}', headers=outsider_headers)
    assert resp.status_code == 403
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/surveys', headers=outsider_headers)
    assert resp.status_code == 403


def test_survey_submissions(dummy_survey, dummy_submission, dummy_event, survey_manager, token_headers,
                            test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/surveys/{dummy_survey.id}/submissions',
                           headers=token_headers)
    assert resp.status_code == 200
    submission = resp.json['results'][0]
    assert submission['id'] == dummy_submission.id
    assert submission['survey_id'] == dummy_survey.id
    assert submission['survey_title'] == 'Feedback'
    assert submission['is_anonymous'] is False
    assert submission['answers'] == [{'question_id': next(iter(dummy_survey.questions)).id,
                                      'question_title': 'Your name',
                                      'answer': 'Alice'}]


def test_survey_submissions_skip_drafts(db, dummy_survey, dummy_submission, dummy_event, dummy_user,
                                        survey_manager, token_headers, test_client):
    db.session.add(SurveySubmission(survey=dummy_survey, user=dummy_user, is_submitted=False))
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/surveys/{dummy_survey.id}/submissions',
                           headers=token_headers)
    assert [s['id'] for s in resp.json['results']] == [dummy_submission.id]


def test_anonymous_submission_keeps_the_respondent_hidden(db, dummy_survey, dummy_event, survey_manager,
                                                         token_headers, test_client):
    submission = SurveySubmission(survey=dummy_survey, is_anonymous=True, is_submitted=True, submitted_dt=now_utc())
    db.session.add(submission)
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/surveys/{dummy_survey.id}/submissions',
                           headers=token_headers)
    assert resp.json['results'][0]['is_anonymous'] is True
    assert not {'user', 'user_id'} & set(resp.json['results'][0])


def test_survey_submissions_are_manager_only(dummy_survey, dummy_submission, dummy_event, outsider_headers,
                                             test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/surveys/{dummy_survey.id}/submissions',
                           headers=outsider_headers)
    assert resp.status_code == 403


def test_survey_questionnaire_matches_current_api(dummy_survey, dummy_event, survey_manager, token_headers,
                                                  test_client, indico_api):
    current = indico_api(f'/event/{dummy_event.id}/manage/surveys/{dummy_survey.id}/questionnaire/survey.json')
    section = current['sections'][0]
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/surveys/{dummy_survey.id}', headers=token_headers).json
    for mine, theirs in zip(new['questions'], section['content'], strict=True):
        assert mine['section_title'] == section['title']
        assert mine['title'] == theirs['title']
        assert mine['description'] == theirs['description']
        assert mine['field_type'] == theirs['field_type']
        assert mine['is_required'] == theirs['is_required']
        assert mine['field_data'] == theirs['field_data']


def test_survey_question_order_matches_current_api(db, dummy_survey, dummy_event, survey_manager, token_headers,
                                                   test_client, indico_api):
    section = SurveySection(survey=dummy_survey, title='Extra', display_as_section=True, position=0)
    SurveyQuestion(survey=dummy_survey, parent=section, title='Anything else?', field_type='text', is_required=False,
                   position=1, field_data={})
    db.session.flush()
    current = indico_api(f'/event/{dummy_event.id}/manage/surveys/{dummy_survey.id}/questionnaire/survey.json')
    expected = [q['title'] for s in current['sections'] for q in s['content']]
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/surveys/{dummy_survey.id}', headers=token_headers).json
    assert [q['title'] for q in new['questions']] == expected
    assert [q['section_title'] for q in new['questions']] == [s['title'] for s in current['sections']
                                                              for _ in s['content']]
