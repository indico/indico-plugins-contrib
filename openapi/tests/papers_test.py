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


def test_paper_matches_current_api(dummy_event, dummy_contribution, dummy_paper_revision, dummy_paper_file,
                                   paper_manager, token_headers, test_client, indico_api):
    current = indico_api(f'/event/{dummy_event.id}/manage/papers/assignment-list/export-json')
    paper = next(p for p in current['papers'] if p['contribution']['id'] == dummy_contribution.id)
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}/paper',
                          headers=token_headers).json
    assert new['state'] == paper['state']['name']
    assert new['is_in_final_state'] == paper['is_in_final_state']
    assert new['contribution']['id'] == paper['contribution']['id']
    assert new['contribution']['title'] == paper['contribution']['title']
    assert new['contribution']['friendly_id'] == paper['contribution']['friendly_id']
    for mine, theirs in zip(new['revisions'], paper['revisions'], strict=True):
        for field in ('id', 'number', 'state', 'submitted_dt', 'judgment_dt', 'judgment_comment', 'is_last_revision'):
            assert mine[field] == theirs[field]
        assert mine['submitter']['id'] == theirs['submitter']['id']
        assert (mine['judge'] or {}).get('id') == (theirs['judge'] or {}).get('id')
        assert (mine['spotlight_file'] or {}).get('id') == (theirs['spotlight_file'] or {}).get('id')
        assert [f['id'] for f in mine['files']] == [f['id'] for f in theirs['files']]
        assert [f['filename'] for f in mine['files']] == [f['filename'] for f in theirs['files']]
        assert [f['download_url'] for f in mine['files']] == [f['download_url'] for f in theirs['files']]


def test_judged_paper_matches_current_api(db, dummy_event, dummy_contribution, dummy_paper_revision, dummy_user,
                                          paper_manager, token_headers, test_client, indico_api):
    dummy_paper_revision.state = PaperRevisionState.accepted
    dummy_paper_revision.judge = dummy_user
    dummy_paper_revision.judgment_dt = now_utc()
    dummy_paper_revision.judgment_comment = 'Good enough'
    db.session.flush()
    current = indico_api(f'/event/{dummy_event.id}/manage/papers/assignment-list/export-json')
    paper = next(p for p in current['papers'] if p['contribution']['id'] == dummy_contribution.id)
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}/paper',
                          headers=token_headers).json
    assert new['state'] == paper['state']['name']
    assert new['is_in_final_state'] == paper['is_in_final_state']
    assert new['revisions'][0]['judge']['id'] == paper['revisions'][0]['judge']['id']
    assert new['revisions'][0]['judgment_dt'] == paper['revisions'][0]['judgment_dt']
    assert new['revisions'][0]['judgment_comment'] == paper['revisions'][0]['judgment_comment']


def test_paper_list_matches_current_api(dummy_event, dummy_contribution, dummy_paper_revision, create_contribution,
                                        paper_manager, token_headers, test_client, indico_api):
    create_contribution(dummy_event, 'No paper here')
    current = indico_api(f'/event/{dummy_event.id}/manage/papers/assignment-list/export-json')
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/papers', headers=token_headers).json
    assert (sorted(p['contribution']['id'] for p in new['results']) ==
            sorted(p['contribution']['id'] for p in current['papers']))
