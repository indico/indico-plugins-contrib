# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 Unconventional
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest

from indico.modules.events.abstracts.models.comments import AbstractComment
from indico.modules.events.abstracts.models.review_questions import AbstractReviewQuestion
from indico.modules.events.abstracts.models.review_ratings import AbstractReviewRating
from indico.modules.events.abstracts.models.reviews import AbstractAction, AbstractCommentVisibility, AbstractReview
from indico.modules.events.features.util import set_feature_enabled
from indico.modules.events.papers.models.comments import PaperReviewComment
from indico.modules.events.papers.models.review_questions import PaperReviewQuestion
from indico.modules.events.papers.models.review_ratings import PaperReviewRating
from indico.modules.events.papers.models.reviews import (
    PaperAction,
    PaperCommentVisibility,
    PaperReview,
    PaperReviewType,
)
from indico.modules.events.tracks.models.tracks import Track


@pytest.fixture(autouse=True)
def reviewing_enabled(db, dummy_event):
    set_feature_enabled(dummy_event, 'abstracts', True)
    set_feature_enabled(dummy_event, 'papers', True)
    db.session.flush()


@pytest.fixture(autouse=True)
def paper_submission_rights(db, dummy_contribution, dummy_user):
    dummy_contribution.update_principal(dummy_user, permissions={'submit'})
    db.session.flush()


@pytest.fixture
def dummy_track(db, dummy_event):
    track = Track(event=dummy_event, title='Dummy track', code='DT')
    db.session.add(track)
    db.session.flush()
    return track


@pytest.fixture
def reviewer(create_user):
    return create_user(43)


@pytest.fixture
def abstract_question(db, dummy_event):
    question = AbstractReviewQuestion(
        event=dummy_event,
        field_type='rating',
        title='Originality',
        description='How novel the work is',
        field_data={'min': 0, 'max': 5},
    )
    db.session.add(question)
    db.session.flush()
    return question


@pytest.fixture
def create_abstract_review(db, dummy_abstract, dummy_track, abstract_question):
    def _create(user, value=3):
        dummy_abstract.reviewed_for_tracks = {dummy_track}
        review = AbstractReview(
            abstract=dummy_abstract,
            user=user,
            track=dummy_track,
            proposed_action=AbstractAction.accept,
            comment='Worth accepting',
        )
        db.session.add(AbstractReviewRating(review=review, question=abstract_question, value=value))
        db.session.flush()
        return review

    return _create


@pytest.fixture
def paper_question(db, dummy_event):
    question = PaperReviewQuestion(
        event=dummy_event,
        type=PaperReviewType.content,
        field_type='rating',
        title='Clarity',
        description='How readable the paper is',
        field_data={'min': 0, 'max': 5},
    )
    db.session.add(question)
    db.session.flush()
    return question


@pytest.fixture
def create_paper_review(db, dummy_paper_revision, paper_question):
    def _create(user, value=4):
        review = PaperReview(
            revision=dummy_paper_revision,
            user=user,
            type=PaperReviewType.content,
            proposed_action=PaperAction.accept,
            comment='Ready as it is',
        )
        db.session.add(PaperReviewRating(review=review, question=paper_question, value=value))
        db.session.flush()
        return review

    return _create


def test_abstract_reviews_are_served_to_a_judge(
    dummy_event, dummy_abstract, create_abstract_review, reviewer, event_manager, token_headers, test_client
):
    review = create_abstract_review(reviewer)
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/abstracts/{dummy_abstract.id}/reviews', headers=token_headers
    )
    assert resp.status_code == 200
    assert [r['id'] for r in resp.json['results']] == [review.id]
    assert resp.json['results'][0]['user']['id'] == reviewer.id
    assert resp.json['results'][0]['proposed_action'] == 'accept'
    assert resp.json['results'][0]['comment'] == 'Worth accepting'
    assert resp.json['results'][0]['track']['title'] == 'Dummy track'


def test_abstract_review_carries_its_ratings(
    dummy_event,
    dummy_abstract,
    create_abstract_review,
    reviewer,
    abstract_question,
    event_manager,
    token_headers,
    test_client,
):
    create_abstract_review(reviewer, value=4)
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/abstracts/{dummy_abstract.id}/reviews', headers=token_headers
    )
    rating = resp.json['results'][0]['ratings'][0]
    assert rating['value'] == 4
    assert rating['question']['id'] == abstract_question.id
    assert rating['question']['title'] == 'Originality'
    assert rating['question']['field_type'] == 'rating'
    assert resp.json['results'][0]['score'] == 4


def test_abstract_review_proposing_a_merge_names_the_other_abstract(
    db, dummy_event, dummy_abstract, dummy_track, create_abstract, reviewer, event_manager, token_headers, test_client
):
    other = create_abstract(dummy_event, 'Another abstract', friendly_id=315, submitter=reviewer)
    dummy_abstract.reviewed_for_tracks = {dummy_track}
    db.session.add(
        AbstractReview(
            abstract=dummy_abstract,
            user=reviewer,
            track=dummy_track,
            proposed_action=AbstractAction.merge,
            proposed_related_abstract=other,
        )
    )
    db.session.flush()
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/abstracts/{dummy_abstract.id}/reviews', headers=token_headers
    )
    assert resp.json['results'][0]['proposed_action'] == 'merge'
    assert resp.json['results'][0]['proposed_related_abstract']['id'] == other.id
    assert resp.json['results'][0]['proposed_related_abstract']['title'] == 'Another abstract'


def test_abstract_review_is_hidden_from_the_submitter(
    dummy_event, dummy_abstract, create_abstract_review, reviewer, token_headers, test_client
):
    create_abstract_review(reviewer)
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/abstracts/{dummy_abstract.id}/reviews', headers=token_headers
    )
    assert resp.status_code == 200
    assert resp.json['results'] == []


def test_abstract_review_is_served_to_its_author(
    dummy_event, dummy_abstract, create_abstract_review, dummy_user, token_headers, test_client
):
    review = create_abstract_review(dummy_user)
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/abstracts/{dummy_abstract.id}/reviews', headers=token_headers
    )
    assert [r['id'] for r in resp.json['results']] == [review.id]


def test_abstract_reviews_need_access_to_the_abstract(
    dummy_event, dummy_abstract, create_abstract_review, reviewer, outsider_headers, test_client
):
    create_abstract_review(reviewer)
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/abstracts/{dummy_abstract.id}/reviews', headers=outsider_headers
    )
    assert resp.status_code == 403


def test_abstract_comments_honour_their_visibility(
    db, dummy_event, dummy_abstract, reviewer, token_headers, test_client
):
    hidden = AbstractComment(
        abstract=dummy_abstract, user=reviewer, text='Only for judges', visibility=AbstractCommentVisibility.judges
    )
    shown = AbstractComment(
        abstract=dummy_abstract,
        user=reviewer,
        text='Please clarify section 2',
        visibility=AbstractCommentVisibility.contributors,
    )
    db.session.add_all([hidden, shown])
    db.session.flush()
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/abstracts/{dummy_abstract.id}/comments', headers=token_headers
    )
    assert resp.status_code == 200
    assert [c['id'] for c in resp.json['results']] == [shown.id]
    assert resp.json['results'][0]['text'] == 'Please clarify section 2'
    assert resp.json['results'][0]['visibility'] == 'contributors'
    assert resp.json['results'][0]['user']['id'] == reviewer.id


def test_abstract_comment_is_served_to_its_author(
    db, dummy_event, dummy_abstract, dummy_track, reviewer, test_client, dummy_personal_token
):
    dummy_abstract.reviewed_for_tracks = {dummy_track}
    dummy_event.update_principal(reviewer, permissions={'abstract_reviewer'})
    dummy_track.update_principal(reviewer, permissions={'review'})
    comment = AbstractComment(
        abstract=dummy_abstract, user=reviewer, text='Only for judges', visibility=AbstractCommentVisibility.judges
    )
    db.session.add(comment)
    dummy_personal_token.user = reviewer
    dummy_personal_token.scopes = ['read:everything']
    db.session.flush()
    headers = {'Authorization': f'Bearer {dummy_personal_token._plaintext_token}'}
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/abstracts/{dummy_abstract.id}/comments', headers=headers)
    assert resp.status_code == 200
    assert [c['id'] for c in resp.json['results']] == [comment.id]


def test_abstract_review_questions_are_served_to_the_abstract_managers(
    dummy_event, abstract_question, event_manager, token_headers, test_client
):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/abstract-review-questions', headers=token_headers)
    assert resp.status_code == 200
    assert [q['id'] for q in resp.json['results']] == [abstract_question.id]
    assert resp.json['results'][0]['title'] == 'Originality'
    assert resp.json['results'][0]['description'] == 'How novel the work is'
    assert resp.json['results'][0]['field_data'] == {'min': 0, 'max': 5}
    assert resp.json['results'][0]['no_score'] is False


def test_abstract_review_questions_are_forbidden_without_management(
    dummy_event, abstract_question, token_headers, test_client
):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/abstract-review-questions', headers=token_headers)
    assert resp.status_code == 403


def test_paper_reviews_are_served_to_a_judge(
    dummy_event,
    dummy_contribution,
    dummy_paper_revision,
    create_paper_review,
    reviewer,
    event_manager,
    token_headers,
    test_client,
):
    review = create_paper_review(reviewer)
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}'
        f'/paper/revisions/{dummy_paper_revision.id}/reviews',
        headers=token_headers,
    )
    assert resp.status_code == 200
    assert [r['id'] for r in resp.json['results']] == [review.id]
    assert resp.json['results'][0]['user']['id'] == reviewer.id
    assert resp.json['results'][0]['type'] == 'content'
    assert resp.json['results'][0]['proposed_action'] == 'accept'
    assert resp.json['results'][0]['comment'] == 'Ready as it is'


def test_paper_review_carries_its_ratings(
    dummy_event,
    dummy_contribution,
    dummy_paper_revision,
    create_paper_review,
    reviewer,
    paper_question,
    event_manager,
    token_headers,
    test_client,
):
    create_paper_review(reviewer, value=5)
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}'
        f'/paper/revisions/{dummy_paper_revision.id}/reviews',
        headers=token_headers,
    )
    rating = resp.json['results'][0]['ratings'][0]
    assert rating['value'] == 5
    assert rating['question']['id'] == paper_question.id
    assert rating['question']['title'] == 'Clarity'
    assert rating['question']['type'] == 'content'
    assert resp.json['results'][0]['score'] == 5


def test_paper_review_is_hidden_from_the_submitter(
    dummy_event, dummy_contribution, dummy_paper_revision, create_paper_review, reviewer, token_headers, test_client
):
    create_paper_review(reviewer)
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}'
        f'/paper/revisions/{dummy_paper_revision.id}/reviews',
        headers=token_headers,
    )
    assert resp.status_code == 200
    assert resp.json['results'] == []


def test_paper_reviews_need_access_to_the_paper(
    dummy_event, dummy_contribution, dummy_paper_revision, create_paper_review, reviewer, outsider_headers, test_client
):
    create_paper_review(reviewer)
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}'
        f'/paper/revisions/{dummy_paper_revision.id}/reviews',
        headers=outsider_headers,
    )
    assert resp.status_code == 403


def test_paper_reviews_of_an_unknown_revision_are_not_found(
    dummy_event, dummy_contribution, dummy_paper_revision, event_manager, token_headers, test_client
):
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}'
        f'/paper/revisions/{dummy_paper_revision.id + 100}/reviews',
        headers=token_headers,
    )
    assert resp.status_code == 404


def test_paper_comments_honour_their_visibility(
    db, dummy_event, dummy_contribution, dummy_paper_revision, reviewer, token_headers, test_client
):
    hidden = PaperReviewComment(
        paper_revision=dummy_paper_revision,
        user=reviewer,
        text='Only for judges',
        visibility=PaperCommentVisibility.judges,
    )
    shown = PaperReviewComment(
        paper_revision=dummy_paper_revision,
        user=reviewer,
        text='Check the references',
        visibility=PaperCommentVisibility.contributors,
    )
    db.session.add_all([hidden, shown])
    db.session.flush()
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}'
        f'/paper/revisions/{dummy_paper_revision.id}/comments',
        headers=token_headers,
    )
    assert resp.status_code == 200
    assert [c['id'] for c in resp.json['results']] == [shown.id]
    assert resp.json['results'][0]['text'] == 'Check the references'
    assert resp.json['results'][0]['visibility'] == 'contributors'


def test_paper_review_questions_are_served_to_the_paper_managers(
    dummy_event, paper_question, event_manager, token_headers, test_client
):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/paper-review-questions', headers=token_headers)
    assert resp.status_code == 200
    assert [q['id'] for q in resp.json['results']] == [paper_question.id]
    assert resp.json['results'][0]['title'] == 'Clarity'
    assert resp.json['results'][0]['type'] == 'content'
    assert resp.json['results'][0]['is_required'] is False


def test_paper_review_questions_are_forbidden_without_management(
    dummy_event, paper_question, token_headers, test_client
):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/paper-review-questions', headers=token_headers)
    assert resp.status_code == 403


ABSTRACT_REVIEW_FIELDS = (
    'id',
    'user',
    'track',
    'comment',
    'proposed_action',
    'proposed_contrib_type',
    'proposed_related_abstract',
    'proposed_tracks',
    'created_dt',
    'modified_dt',
)
COMMENT_FIELDS = ('id', 'user', 'text', 'visibility', 'created_dt', 'modified_dt', 'modified_by')
PAPER_REVIEW_FIELDS = ('id', 'user', 'comment', 'created_dt', 'modified_dt')
PAPER_QUESTION_FIELDS = ('id', 'type', 'title', 'description', 'field_type', 'field_data', 'is_required', 'position')


def as_question_ids(ratings):
    """The abstracts export names the question of a rating by identifier, where we nest it."""
    return [{'question': rating['question']['id'], 'value': rating['value']} for rating in ratings]


def as_rated_questions(ratings):
    """The papers export nests the question of a rating without the flag Indico computes for it."""
    return [
        {
            'question': {key: value for key, value in rating['question'].items() if key != 'no_score'},
            'value': rating['value'],
        }
        for rating in ratings
    ]


def as_review_score(current):
    """The abstracts export leaves the score of a review to be computed from its ratings.

    Only a rating answers with a number, which is what the score of a review
    averages, unless a rating question was taken out of it by hand.
    """
    values = [
        rating['value']
        for rating in current['ratings']
        if isinstance(rating['value'], int | float) and not isinstance(rating['value'], bool)
    ]
    return sum(values) / len(values) if values else None


def as_paper_score(current):
    return float(current['score']) if current['score'] is not None else None


def as_review_type(current):
    return current['group']['name']


def as_action_name(current):
    return current['proposed_action']['name']


def as_visibility_name(current):
    return current['visibility']['name']


def as_no_score(current):
    """The papers export leaves out the flag, which holds for every question but a rating excluded by hand."""
    return current['field_type'] != 'rating'


ABSTRACT_REVIEW_MAPPINGS = {
    'same': ABSTRACT_REVIEW_FIELDS,
    'renamed': {'ratings': ('ratings', as_question_ids)},
    'derived': {'score': as_review_score},
}
PAPER_REVIEW_MAPPINGS = {
    'same': PAPER_REVIEW_FIELDS,
    'renamed': {'ratings': ('ratings', as_rated_questions)},
    'derived': {'type': as_review_type, 'proposed_action': as_action_name, 'score': as_paper_score},
}
PAPER_COMMENT_MAPPINGS = {
    'same': tuple(field for field in COMMENT_FIELDS if field != 'visibility'),
    'derived': {'visibility': as_visibility_name},
}
PAPER_QUESTION_MAPPINGS = {'same': PAPER_QUESTION_FIELDS, 'derived': {'no_score': as_no_score}}


def test_abstract_reviews_match_the_current_api(
    dummy_event,
    dummy_abstract,
    create_abstract_review,
    reviewer,
    event_manager,
    token_headers,
    test_client,
    indico_api,
    same_json_list,
):
    create_abstract_review(reviewer)
    current = indico_api(f'/event/{dummy_event.id}/manage/abstracts/abstracts.json')['abstracts']
    theirs = next(abstract for abstract in current if abstract['id'] == dummy_abstract.id)['reviews']
    ours = test_client.get(
        f'/api/v1/events/{dummy_event.id}/abstracts/{dummy_abstract.id}/reviews', headers=token_headers
    ).json['results']
    same_json_list(ours, theirs, **ABSTRACT_REVIEW_MAPPINGS)


def test_abstract_comments_match_the_current_api(
    db, dummy_event, dummy_abstract, reviewer, event_manager, token_headers, test_client, indico_api, same_json_list
):
    db.session.add(
        AbstractComment(
            abstract=dummy_abstract,
            user=reviewer,
            text='Please clarify section 2',
            visibility=AbstractCommentVisibility.contributors,
        )
    )
    db.session.flush()
    current = indico_api(f'/event/{dummy_event.id}/manage/abstracts/abstracts.json')['abstracts']
    theirs = next(abstract for abstract in current if abstract['id'] == dummy_abstract.id)['comments']
    ours = test_client.get(
        f'/api/v1/events/{dummy_event.id}/abstracts/{dummy_abstract.id}/comments', headers=token_headers
    ).json['results']
    same_json_list(ours, theirs, same=COMMENT_FIELDS)


def test_paper_reviews_match_the_current_api(
    dummy_event,
    dummy_contribution,
    dummy_paper_revision,
    create_paper_review,
    reviewer,
    event_manager,
    token_headers,
    test_client,
    indico_api,
    same_json_list,
):
    create_paper_review(reviewer)
    current = indico_api(f'/event/{dummy_event.id}/manage/papers/assignment-list/export-json')['papers']
    paper = next(p for p in current if p['contribution']['id'] == dummy_contribution.id)
    theirs = next(r for r in paper['revisions'] if r['id'] == dummy_paper_revision.id)['reviews']
    ours = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}'
        f'/paper/revisions/{dummy_paper_revision.id}/reviews',
        headers=token_headers,
    ).json['results']
    same_json_list(ours, theirs, **PAPER_REVIEW_MAPPINGS)


def test_paper_comments_match_the_current_api(
    db,
    dummy_event,
    dummy_contribution,
    dummy_paper_revision,
    reviewer,
    event_manager,
    token_headers,
    test_client,
    indico_api,
    same_json_list,
):
    db.session.add(
        PaperReviewComment(
            paper_revision=dummy_paper_revision,
            user=reviewer,
            text='Check the references',
            visibility=PaperCommentVisibility.contributors,
        )
    )
    db.session.flush()
    current = indico_api(f'/event/{dummy_event.id}/manage/papers/assignment-list/export-json')['papers']
    paper = next(p for p in current if p['contribution']['id'] == dummy_contribution.id)
    theirs = next(r for r in paper['revisions'] if r['id'] == dummy_paper_revision.id)['comments']
    ours = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}'
        f'/paper/revisions/{dummy_paper_revision.id}/comments',
        headers=token_headers,
    ).json['results']
    same_json_list(ours, theirs, **PAPER_COMMENT_MAPPINGS)


def test_paper_review_questions_match_the_current_api(
    dummy_event, paper_question, event_manager, token_headers, test_client, indico_api, same_json_list
):
    current = indico_api(f'/event/{dummy_event.id}/manage/papers/assignment-list/export-json')
    theirs = current['layout_review_questions'] + current['content_review_questions']
    ours = test_client.get(f'/api/v1/events/{dummy_event.id}/paper-review-questions', headers=token_headers).json
    same_json_list(ours['results'], theirs, **PAPER_QUESTION_MAPPINGS)
