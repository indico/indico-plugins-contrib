# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 Unconventional
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest

from indico.modules.events.editing.models.comments import EditingRevisionComment
from indico.modules.events.editing.models.editable import Editable, EditableType
from indico.modules.events.editing.models.file_types import EditingFileType
from indico.modules.events.editing.models.review_conditions import EditingReviewCondition
from indico.modules.events.editing.models.revision_files import EditingRevisionFile
from indico.modules.events.editing.models.revisions import EditingRevision, RevisionType
from indico.modules.events.editing.models.tags import EditingTag
from indico.modules.events.editing.settings import editable_type_settings
from indico.modules.events.features.util import set_feature_enabled
from indico.util.date_time import now_utc


EDITABLE_FIELDS = (
    'id',
    'type',
    'contribution',
    'review_conditions_valid',
    'editing_enabled',
    'has_published_revision',
    'last_update_dt',
)
REVISION_FIELDS = ('id', 'created_dt', 'modified_dt', 'comment', 'is_undone', 'is_editor_revision', 'tags')
COMMENT_FIELDS = ('id', 'revision_id', 'text', 'internal', 'system', 'created_dt', 'modified_dt')
TAG_FIELDS = ('id', 'code', 'title', 'color', 'system', 'verbose_title')
FILE_TYPE_FIELDS = ('id', 'name', 'extensions', 'allow_multiple_files', 'required', 'publishable', 'filename_template')


def as_type_name(current):
    return current['type']['name']


def as_state_name(current):
    return current['state']['name']


def _as_editing_user(user):
    return user and {
        'id': user['id'],
        'identifier': user['identifier'],
        'full_name': user['full_name'],
        'anonymous': False,
    }


def as_editor(current):
    return _as_editing_user(current['editor'])


def as_revision_user(current):
    return _as_editing_user(current['user'])


def as_revision_count(current):
    # the timeline serves the revisions themselves instead of counting the ones carrying files
    return len([revision for revision in current['revisions'] if revision['files']])


def as_files(current):
    return [
        {
            'id': file['id'],
            'uuid': file['uuid'],
            'filename': file['filename'],
            'size': file['size'],
            'content_type': file['content_type'],
            'file_type_id': file['file_type'],
            'download_url': file['download_url'],
        }
        for file in current['files']
    ]


EDITABLE_MAPPINGS = {
    'same': EDITABLE_FIELDS,
    'derived': {'state': as_state_name, 'editor': as_editor, 'revision_count': as_revision_count},
}
REVISION_MAPPINGS = {
    'same': REVISION_FIELDS,
    'derived': {'type': as_type_name, 'user': as_revision_user, 'files': as_files},
}
COMMENT_MAPPINGS = {'same': COMMENT_FIELDS, 'derived': {'user': as_revision_user}}


@pytest.fixture(autouse=True)
def editing_enabled(db, dummy_event, request_context):
    # turning the feature on creates a default file type per editable type, and says so with a flash
    set_feature_enabled(dummy_event, 'editing', True)
    db.session.flush()


@pytest.fixture(autouse=True)
def submission_rights(db, dummy_contribution, dummy_user):
    dummy_contribution.update_principal(dummy_user, permissions={'submit'})
    db.session.flush()


@pytest.fixture
def editable(db, dummy_contribution):
    editable = Editable(contribution=dummy_contribution, type=EditableType.paper)
    db.session.add(editable)
    db.session.flush()
    return editable


@pytest.fixture
def create_revision(db, editable, dummy_user):
    def _create(type=RevisionType.ready_for_review, user=None, comment='', is_undone=False):
        revision = EditingRevision(
            editable=editable,
            user=(user or dummy_user),
            type=type,
            comment=comment,
            is_undone=is_undone,
            created_dt=now_utc(),
        )
        db.session.add(revision)
        db.session.flush()
        return revision

    return _create


@pytest.fixture
def revision(create_revision):
    return create_revision(comment='First upload')


@pytest.fixture
def editor(db, dummy_event, create_user):
    user = create_user(43)
    dummy_event.update_principal(user, permissions={'paper_editing'})
    db.session.flush()
    return user


@pytest.fixture
def revision_file(db, revision, file_type, dummy_file):
    revision_file = EditingRevisionFile(revision=revision, file=dummy_file, file_type=file_type)
    dummy_file.claim()
    db.session.flush()
    return revision_file


@pytest.fixture
def editing_tag(db, dummy_event):
    tag = EditingTag(event=dummy_event, title='Ready', code='RDY', color='green')
    db.session.add(tag)
    db.session.flush()
    return tag


@pytest.fixture
def file_type(db, dummy_event):
    file_type = EditingFileType(
        event=dummy_event,
        type=EditableType.paper,
        name='Source',
        extensions=['tex'],
        required=True,
        publishable=False,
        filename_template='paper-{code}',
    )
    db.session.add(file_type)
    db.session.flush()
    return file_type


def test_editable_is_served_to_the_submitter(
    dummy_event, dummy_contribution, editable, revision, token_headers, test_client
):
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}/editables/paper', headers=token_headers
    )
    assert resp.status_code == 200
    assert resp.json['id'] == editable.id
    assert resp.json['type'] == 'paper'
    assert resp.json['state'] == 'ready_for_review'
    assert resp.json['contribution']['id'] == dummy_contribution.id
    assert [rev['id'] for rev in resp.json['revisions']] == [revision.id]
    assert resp.json['revisions'][0]['comment'] == 'First upload'
    assert resp.json['revisions'][0]['type'] == 'ready_for_review'
    assert resp.json['revisions'][0]['user']['id'] == editable.contribution.event.creator.id


def test_editable_of_an_unknown_type_is_not_found(
    dummy_event, dummy_contribution, editable, token_headers, test_client
):
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}/editables/slides', headers=token_headers
    )
    assert resp.status_code == 404


def test_editable_is_not_served_to_an_outsider(
    dummy_event, dummy_contribution, editable, outsider_headers, test_client
):
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}/editables/paper',
        headers=outsider_headers,
    )
    assert resp.status_code == 403


def test_undone_revision_is_hidden_from_the_submitter(
    dummy_event, dummy_contribution, editable, create_revision, token_headers, test_client
):
    kept = create_revision()
    create_revision(is_undone=True)
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}/editables/paper', headers=token_headers
    )
    assert [rev['id'] for rev in resp.json['revisions']] == [kept.id]


def test_undone_revision_is_served_to_the_editing_team(
    db, dummy_event, dummy_contribution, dummy_user, editable, create_revision, token_headers, test_client
):
    dummy_event.update_principal(dummy_user, permissions={'paper_editing'})
    db.session.flush()
    kept = create_revision()
    undone = create_revision(is_undone=True)
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}/editables/paper', headers=token_headers
    )
    assert [rev['id'] for rev in resp.json['revisions']] == [kept.id, undone.id]


def test_editor_name_is_hidden_while_the_team_is_anonymous(
    db, dummy_event, dummy_contribution, editable, editor, revision, token_headers, test_client
):
    editable.editor = editor
    editable_type_settings[EditableType.paper].set(dummy_event, 'anonymous_team', True)
    db.session.flush()
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}/editables/paper', headers=token_headers
    )
    assert resp.json['editor'] == {'id': None, 'identifier': None, 'full_name': None, 'anonymous': True}
    assert resp.json['revisions'][0]['user']['anonymous'] is False


def test_editor_name_is_served_to_the_editing_team(
    db, dummy_event, dummy_contribution, dummy_user, editable, editor, revision, token_headers, test_client
):
    editable.editor = editor
    editable_type_settings[EditableType.paper].set(dummy_event, 'anonymous_team', True)
    dummy_event.update_principal(dummy_user, permissions={'paper_editing'})
    db.session.flush()
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}/editables/paper', headers=token_headers
    )
    assert resp.json['editor']['id'] == editor.id
    assert resp.json['editor']['anonymous'] is False


def test_editables_are_listed_for_the_whole_event(dummy_event, editable, revision, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/editables', headers=token_headers)
    assert resp.status_code == 200
    assert [item['id'] for item in resp.json['results']] == [editable.id]


def test_editable_list_leaves_out_what_the_caller_cannot_see(
    dummy_event, editable, revision, outsider_headers, test_client
):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/editables', headers=outsider_headers)
    assert resp.json['results'] == []


def test_editable_list_takes_the_type_as_a_filter(dummy_event, editable, revision, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/editables?type=slides', headers=token_headers)
    assert resp.json['results'] == []
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/editables?type=paper', headers=token_headers)
    assert [item['id'] for item in resp.json['results']] == [editable.id]


def test_revision_comments_are_served(
    db, dummy_event, dummy_contribution, dummy_user, editable, revision, token_headers, test_client
):
    comment = EditingRevisionComment(revision=revision, user=dummy_user, text='Looks good')
    db.session.add(comment)
    db.session.flush()
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}'
        f'/editables/paper/revisions/{revision.id}/comments',
        headers=token_headers,
    )
    assert resp.status_code == 200
    assert [item['id'] for item in resp.json['results']] == [comment.id]
    assert resp.json['results'][0]['text'] == 'Looks good'
    assert resp.json['results'][0]['user']['id'] == dummy_user.id


def test_internal_comment_is_hidden_from_the_submitter(
    db, dummy_event, dummy_contribution, editable, editor, revision, token_headers, test_client
):
    EditingRevisionComment(revision=revision, user=editor, text='Only for the team', internal=True)
    db.session.flush()
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}'
        f'/editables/paper/revisions/{revision.id}/comments',
        headers=token_headers,
    )
    assert resp.json['results'] == []


def test_internal_comment_is_served_to_the_editing_team(
    db, dummy_event, dummy_contribution, dummy_user, editable, revision, token_headers, test_client
):
    comment = EditingRevisionComment(revision=revision, user=dummy_user, text='Only for the team', internal=True)
    dummy_event.update_principal(dummy_user, permissions={'paper_editing'})
    db.session.flush()
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}'
        f'/editables/paper/revisions/{revision.id}/comments',
        headers=token_headers,
    )
    assert [item['id'] for item in resp.json['results']] == [comment.id]


def test_comments_of_an_unknown_revision_are_not_found(
    dummy_event, dummy_contribution, editable, revision, token_headers, test_client
):
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}'
        f'/editables/paper/revisions/{revision.id + 1000}/comments',
        headers=token_headers,
    )
    assert resp.status_code == 404


def test_editing_tags_are_served(dummy_event, editing_tag, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/editing/tags', headers=token_headers)
    assert resp.status_code == 200
    assert [item['code'] for item in resp.json['results']] == ['RDY']
    assert resp.json['results'][0]['verbose_title'] == 'RDY: Ready'


def test_file_types_are_served(dummy_event, file_type, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/editing/paper/file-types', headers=token_headers)
    assert resp.status_code == 200
    served = next(item for item in resp.json['results'] if item['id'] == file_type.id)
    assert served['name'] == 'Source'
    assert served['extensions'] == ['tex']
    assert served['required'] is True
    assert served['publishable'] is False
    assert served['filename_template'] == 'paper-{code}'


def test_file_types_of_another_type_are_not_served(dummy_event, file_type, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/editing/poster/file-types', headers=token_headers)
    assert file_type.id not in [item['id'] for item in resp.json['results']]


def test_editing_endpoints_need_the_feature(
    db, dummy_event, dummy_contribution, editable, editing_tag, token_headers, test_client
):
    set_feature_enabled(dummy_event, 'editing', False)
    db.session.flush()
    for path in (
        f'/events/{dummy_event.id}/editables',
        f'/events/{dummy_event.id}/contributions/{dummy_contribution.id}/editables/paper',
        f'/events/{dummy_event.id}/editing/tags',
        f'/events/{dummy_event.id}/editing/paper/file-types',
    ):
        assert test_client.get(f'/api/v1{path}', headers=token_headers).status_code == 404


def test_review_conditions_are_served_to_a_manager(
    db, dummy_event, file_type, event_manager, token_headers, test_client
):
    condition = EditingReviewCondition(event=dummy_event, type=EditableType.paper, file_types={file_type})
    db.session.add(condition)
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/editing/paper/review-conditions', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['results'] == [{'id': condition.id, 'file_type_ids': [file_type.id]}]


def test_review_conditions_need_management(dummy_event, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/editing/paper/review-conditions', headers=token_headers)
    assert resp.status_code == 403


def test_editable_matches_the_timeline(
    dummy_event, dummy_contribution, editable, revision, revision_file, indico_api, same_json, same_json_list
):
    ours = indico_api(f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}/editables/paper')
    theirs = indico_api(f'/event/{dummy_event.id}/api/contributions/{dummy_contribution.id}/editing/paper')
    same_json_list(ours.pop('revisions'), theirs['revisions'], **REVISION_MAPPINGS)
    same_json(ours, theirs, **EDITABLE_MAPPINGS)


def test_comments_match_the_timeline(
    db, dummy_event, dummy_contribution, dummy_user, editable, revision, indico_api, same_json_list
):
    db.session.add(EditingRevisionComment(revision=revision, user=dummy_user, text='Looks good'))
    db.session.flush()
    ours = indico_api(
        f'/api/v1/events/{dummy_event.id}/contributions/{dummy_contribution.id}'
        f'/editables/paper/revisions/{revision.id}/comments'
    )
    theirs = indico_api(f'/event/{dummy_event.id}/api/contributions/{dummy_contribution.id}/editing/paper')
    same_json_list(ours['results'], theirs['revisions'][0]['comments'], **COMMENT_MAPPINGS)


def test_tags_match_the_editing_api(dummy_event, editing_tag, indico_api, same_json_list):
    ours = indico_api(f'/api/v1/events/{dummy_event.id}/editing/tags')
    theirs = indico_api(f'/event/{dummy_event.id}/editing/api/tags')
    same_json_list(ours['results'], theirs, same=TAG_FIELDS)


def test_file_types_match_the_editing_api(dummy_event, file_type, indico_api, same_json_list):
    ours = indico_api(f'/api/v1/events/{dummy_event.id}/editing/paper/file-types')
    theirs = indico_api(f'/event/{dummy_event.id}/editing/api/paper/file-types')
    same_json_list(ours['results'], theirs, same=FILE_TYPE_FIELDS)


def test_review_conditions_match_the_editing_api(db, dummy_event, file_type, event_manager, indico_api):
    db.session.add(EditingReviewCondition(event=dummy_event, type=EditableType.paper, file_types={file_type}))
    db.session.flush()
    ours = indico_api(f'/api/v1/events/{dummy_event.id}/editing/paper/review-conditions')
    theirs = indico_api(f'/event/{dummy_event.id}/editing/api/paper/review-conditions')
    assert [[row['id'], row['file_type_ids']] for row in ours['results']] == theirs
