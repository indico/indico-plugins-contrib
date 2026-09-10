# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


import pytest

from indico.modules.events.features.util import set_feature_enabled
from indico.modules.events.papers.models.revisions import PaperRevisionState
from indico.util.date_time import now_utc


@pytest.fixture(autouse=True)
def papers_enabled(db, dummy_event):
    set_feature_enabled(dummy_event, 'papers', True)
    db.session.flush()


@pytest.fixture(autouse=True)
def paper_submission_rights(db, dummy_contribution, dummy_user):
    dummy_contribution.update_principal(dummy_user, permissions={'submit'})
    db.session.flush()


def test_paper_details(dummy_event, dummy_contribution, dummy_paper_revision, dummy_user, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}/paper',
                           headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['contribution']['id'] == dummy_contribution.id
    assert resp.json['contribution']['title'] == dummy_contribution.title
    assert resp.json['state'] == 'submitted'
    assert resp.json['is_in_final_state'] is False
    assert resp.json['revision_count'] == 1
    assert [r['number'] for r in resp.json['revisions']] == [1]
    assert resp.json['revisions'][0]['submitter']['id'] == dummy_user.id
    assert resp.json['revisions'][0]['judge'] is None
    assert resp.json['revisions'][0]['is_last_revision'] is True


def test_paper_revisions(db, dummy_event, dummy_contribution, dummy_paper, dummy_paper_revision, dummy_user,
                         create_paper_revision, token_headers, test_client):
    create_paper_revision(dummy_paper, submitter=dummy_user)
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}/paper',
                           headers=token_headers)
    assert [r['number'] for r in resp.json['revisions']] == [1, 2]
    assert [r['is_last_revision'] for r in resp.json['revisions']] == [False, True]
    assert resp.json['revision_count'] == 2


def test_paper_files(dummy_event, dummy_contribution, dummy_paper_file, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}/paper',
                           headers=token_headers)
    files = resp.json['revisions'][0]['files']
    assert [f['filename'] for f in files] == [dummy_paper_file.filename]
    assert files[0]['content_type'] == dummy_paper_file.content_type
    assert files[0]['download_url'].endswith(f'{dummy_paper_file.id}-{dummy_paper_file.filename}')


def test_paper_list(dummy_event, dummy_contribution, dummy_paper_revision, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/papers', headers=token_headers)
    assert resp.status_code == 200
    assert [p['contribution']['id'] for p in resp.json['results']] == [dummy_contribution.id]
    assert resp.json['results'][0]['last_revision']['id'] == dummy_paper_revision.id
    assert 'revisions' not in resp.json['results'][0]


def test_paper_list_skips_contributions_without_paper(dummy_event, dummy_contribution, dummy_paper_revision,
                                                      create_contribution, token_headers, test_client):
    create_contribution(dummy_event, 'No paper here')
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/papers', headers=token_headers)
    assert [p['contribution']['id'] for p in resp.json['results']] == [dummy_contribution.id]


def test_paper_of_someone_else_is_forbidden(dummy_event, dummy_contribution, dummy_paper_revision, outsider_headers,
                                            test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}/paper',
                           headers=outsider_headers)
    assert resp.status_code == 403


def test_paper_list_skips_unreadable_papers(dummy_event, dummy_paper_revision, outsider_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/papers', headers=outsider_headers)
    assert resp.status_code == 200
    assert resp.json['results'] == []


def test_paper_manager_sees_every_paper(db, dummy_event, dummy_contribution, dummy_paper_revision, outsider,
                                        outsider_headers, test_client):
    dummy_event.update_principal(outsider, permissions={'paper_manager'})
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/papers', headers=outsider_headers)
    assert [p['contribution']['id'] for p in resp.json['results']] == [dummy_contribution.id]


def test_contribution_without_paper_is_not_found(dummy_event, dummy_contribution, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}/paper',
                           headers=token_headers)
    assert resp.status_code == 404


def test_papers_require_the_feature(db, dummy_event, dummy_contribution, dummy_paper_revision, token_headers,
                                    test_client):
    set_feature_enabled(dummy_event, 'papers', False)
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/papers', headers=token_headers)
    assert resp.status_code == 404


def test_papers_require_login(dummy_event, dummy_contribution, dummy_paper_revision, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}/paper')
    assert resp.status_code == 403


def test_judged_paper(db, dummy_event, dummy_contribution, dummy_paper_revision, dummy_user, token_headers,
                      test_client):
    dummy_paper_revision.state = PaperRevisionState.accepted
    dummy_paper_revision.judge = dummy_user
    dummy_paper_revision.judgment_dt = now_utc()
    dummy_paper_revision.judgment_comment = 'Good enough'
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}/paper',
                           headers=token_headers)
    assert resp.json['state'] == 'accepted'
    assert resp.json['is_in_final_state'] is True
    assert resp.json['revisions'][0]['judge']['id'] == dummy_user.id
    assert resp.json['revisions'][0]['judgment_comment'] == 'Good enough'


@pytest.fixture
def paper_manager(db, dummy_event, dummy_user):
    dummy_event.update_principal(dummy_user, permissions={'paper_manager'})
    db.session.flush()


PAPER_FIELDS = ('contribution', 'is_in_final_state')


def as_state_name(current):
    return current['state']['name']


def as_revision_count(current):
    return len(current['revisions'])


def as_last_revision(current):
    return next(revision for revision in current['revisions'] if revision['is_last_revision'])


PAPER_DERIVED = {'state': as_state_name, 'revision_count': as_revision_count}


@pytest.fixture
def judged_paper(db, dummy_paper_revision, dummy_user):
    dummy_paper_revision.state = PaperRevisionState.accepted
    dummy_paper_revision.judge = dummy_user
    dummy_paper_revision.judgment_dt = now_utc()
    dummy_paper_revision.judgment_comment = 'Good enough'
    db.session.flush()


def test_paper_matches_current_api(dummy_event, dummy_contribution, dummy_paper_revision, dummy_paper_file,
                                   paper_manager, token_headers, test_client, indico_api, same_json):
    current = indico_api(f'/event/{dummy_event.id}/manage/papers/assignment-list/export-json')
    paper = next(p for p in current['papers'] if p['contribution']['id'] == dummy_contribution.id)
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}/paper',
                          headers=token_headers).json
    same_json(new, paper, same=(*PAPER_FIELDS, 'revisions'), derived=PAPER_DERIVED)


@pytest.mark.usefixtures('judged_paper')
def test_judged_paper_matches_current_api(dummy_event, dummy_contribution, dummy_paper_file, paper_manager,
                                          token_headers, test_client, indico_api, same_json):
    current = indico_api(f'/event/{dummy_event.id}/manage/papers/assignment-list/export-json')
    paper = next(p for p in current['papers'] if p['contribution']['id'] == dummy_contribution.id)
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}/paper',
                          headers=token_headers).json
    same_json(new, paper, same=(*PAPER_FIELDS, 'revisions'), derived=PAPER_DERIVED)


def test_paper_list_matches_current_api(dummy_event, dummy_contribution, dummy_paper_revision, dummy_paper_file,
                                        create_contribution, paper_manager, token_headers, test_client, indico_api,
                                        same_json_list):
    create_contribution(dummy_event, 'No paper here')
    current = indico_api(f'/event/{dummy_event.id}/manage/papers/assignment-list/export-json')
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/papers', headers=token_headers).json['results']
    same_json_list(new, current['papers'], same=PAPER_FIELDS,
                   derived={**PAPER_DERIVED, 'last_revision': as_last_revision},
                   key=lambda paper: paper['contribution']['id'])
