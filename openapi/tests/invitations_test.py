# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest

from indico.modules.events.features.util import set_feature_enabled
from indico.modules.events.registration.models.invitations import InvitationState, RegistrationInvitation


@pytest.fixture(autouse=True)
def registration_enabled(db, dummy_event):
    set_feature_enabled(dummy_event, 'registration', True)
    db.session.flush()


@pytest.fixture
def registration_manager(db, dummy_event, dummy_user):
    dummy_event.update_principal(dummy_user, permissions={'registration'})
    db.session.flush()


@pytest.fixture
def create_invitation(db, dummy_regform):
    def _create(first_name, last_name, email, regform=None, **kwargs):
        invitation = RegistrationInvitation(first_name=first_name, last_name=last_name, email=email,
                                            affiliation=kwargs.pop('affiliation', 'ACME'), **kwargs)
        (regform or dummy_regform).invitations.append(invitation)
        db.session.flush()
        return invitation

    return _create


@pytest.fixture
def dummy_invitation(create_invitation):
    return create_invitation('Ada', 'Lovelace', 'ada@example.com', skip_moderation=True, lock_email=True)


@pytest.mark.usefixtures('event_manager')
def test_invitation_details(dummy_event, dummy_regform, dummy_invitation, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registration-forms/{dummy_regform.id}/invitations/'
                           f'{dummy_invitation.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json == {'id': dummy_invitation.id, 'registration_form_id': dummy_regform.id, 'registration_id': None,
                         'state': 'pending', 'first_name': 'Ada', 'last_name': 'Lovelace', 'email': 'ada@example.com',
                         'affiliation': 'ACME', 'skip_moderation': True, 'skip_access_check': False,
                         'lock_email': True}


@pytest.mark.usefixtures('event_manager')
def test_accepted_invitation_points_at_the_registration(db, dummy_event, dummy_regform, dummy_reg, dummy_invitation,
                                                        token_headers, test_client):
    dummy_invitation.state = InvitationState.accepted
    dummy_invitation.registration = dummy_reg
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registration-forms/{dummy_regform.id}/invitations/'
                           f'{dummy_invitation.id}', headers=token_headers)
    assert resp.json['state'] == 'accepted'
    assert resp.json['registration_id'] == dummy_reg.id


@pytest.mark.usefixtures('event_manager')
def test_invitation_list_is_sorted_by_name(dummy_event, dummy_regform, dummy_invitation, create_invitation,
                                           token_headers, test_client):
    grace = create_invitation('grace', 'Hopper', 'grace@example.com')
    alan = create_invitation('Alan', 'Turing', 'alan@example.com', state=InvitationState.declined)
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registration-forms/{dummy_regform.id}/invitations',
                           headers=token_headers)
    assert resp.status_code == 200
    assert [inv['id'] for inv in resp.json['results']] == [dummy_invitation.id, alan.id, grace.id]
    assert resp.json['count'] == 3
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registration-forms/{dummy_regform.id}/invitations'
                           '?state=declined', headers=token_headers)
    assert [inv['id'] for inv in resp.json['results']] == [alan.id]


@pytest.mark.usefixtures('registration_manager')
def test_registration_managers_can_see_invitations(dummy_event, dummy_regform, dummy_invitation, token_headers,
                                                   test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registration-forms/{dummy_regform.id}/invitations',
                           headers=token_headers)
    assert resp.status_code == 200
    assert [inv['id'] for inv in resp.json['results']] == [dummy_invitation.id]


def test_invitations_are_manager_only(dummy_event, dummy_regform, dummy_invitation, token_headers, test_client):
    url = f'/api/v1/events/{dummy_event.id}/registration-forms/{dummy_regform.id}/invitations'
    resp = test_client.get(url, headers=token_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json
    resp = test_client.get(f'{url}/{dummy_invitation.id}', headers=token_headers)
    assert resp.status_code == 403


@pytest.mark.usefixtures('event_manager')
def test_invitations_need_the_registration_feature(db, dummy_event, dummy_regform, dummy_invitation, token_headers,
                                                   test_client):
    set_feature_enabled(dummy_event, 'registration', False)
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registration-forms/{dummy_regform.id}/invitations',
                           headers=token_headers)
    assert resp.status_code == 404


@pytest.mark.usefixtures('event_manager')
def test_invitations_of_a_deleted_form_are_not_found(db, dummy_event, dummy_regform, dummy_invitation, token_headers,
                                                     test_client):
    dummy_regform.is_deleted = True
    db.session.flush()
    url = f'/api/v1/events/{dummy_event.id}/registration-forms/{dummy_regform.id}/invitations'
    assert test_client.get(url, headers=token_headers).status_code == 404
    assert test_client.get(f'{url}/{dummy_invitation.id}', headers=token_headers).status_code == 404


@pytest.mark.usefixtures('event_manager')
def test_invitation_of_another_form_is_not_found(dummy_event, dummy_regform, create_regform, create_invitation,
                                                 token_headers, test_client):
    other = create_regform(dummy_event, title='Other')
    stranger = create_invitation('Linus', 'Torvalds', 'linus@example.com', regform=other)
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registration-forms/{dummy_regform.id}/invitations/'
                           f'{stranger.id}', headers=token_headers)
    assert resp.status_code == 404
