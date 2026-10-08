# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from datetime import timedelta

import email_validator
import pytest
from flask import session

from indico.core import signals
from indico.core.errors import UserValueError
from indico.modules.events.features.util import set_feature_enabled
from indico.modules.events.registration import REGISTRATION_PERMISSIONS
from indico.modules.users.models.affiliations import Affiliation
from indico.modules.users.util import get_linked_events, merge_users
from indico.util.date_time import now_utc
from indico.util.user import make_user_search_token

from indico_affiliation_extras.focal_points import get_focal_affiliation_ids, set_focal_points
from indico_affiliation_extras.permissions import set_focal_point_management_enabled


pytest_plugins = 'indico.modules.events.registration.testing.fixtures'


def _login(test_client, user):
    with test_client.session_transaction() as sess:
        sess.set_session_user(user)


def _create_url(regform):
    return f'/event/{regform.event.id}/manage/registration/{regform.id}/registrations/create'


def _user_with_affiliation(create_user, db, id_, affiliation, **kwargs):
    user = create_user(id_, **kwargs)
    user.affiliation_link = affiliation
    db.session.flush()
    return user


def _registration_data(field, affiliation_id, email='new@example.test'):
    return {
        'email': email,
        'first_name': 'New',
        'last_name': 'Person',
        field.html_field_name: {'affiliation': {'id': affiliation_id, 'text': 'CERN'}},
    }


def _guardrail(regform, user, data, management):
    from indico_affiliation_extras.plugin import AffiliationExtrasPlugin

    AffiliationExtrasPlugin.instance._check_registration_pre_create(regform, user, data, management)


def _search_token(app, user):
    with app.test_request_context():
        session.set_session_user(user)
        return make_user_search_token()


@pytest.fixture
def setup_focal_point(
    db, create_user, create_catalog_affiliations, create_representation_field, create_representation_registration
):
    def _setup_focal_point(regform, *, user_id=1, full_manager=False):
        managed, other = create_catalog_affiliations(regform.event)
        field = create_representation_field(regform)
        in_range = create_representation_registration(field, managed.id)
        out_range = create_representation_registration(field, other.id)
        user = create_user(user_id)
        set_focal_points(managed, {user})
        set_focal_point_management_enabled(regform, True)
        if full_manager:
            regform.event.update_principal(user, full_access=True)
        db.session.flush()
        return user, in_range, out_range

    return _setup_focal_point


def _reglist_url(regform):
    return f'/event/{regform.event.id}/manage/registration/{regform.id}/registrations/'


@pytest.fixture
def create_focal_event(
    create_event,
    create_regform,
    create_event_catalog,
    create_representation_field,
    create_representation_registration,
):
    def _create_focal_event(affiliation, **kwargs):
        event = create_event(**kwargs)
        regform = create_regform(event)
        create_event_catalog(event, [affiliation])
        create_representation_registration(create_representation_field(regform), affiliation.id)
        set_focal_point_management_enabled(regform, True)
        return event

    return _create_focal_event


class TestRegistrationCreation:
    @pytest.mark.usefixtures('request_context')
    def test_pre_create_allows_focal_with_managed_affiliation(
        self, db, dummy_regform, create_user, create_catalog_affiliations, create_representation_field
    ):
        managed, __ = create_catalog_affiliations(dummy_regform.event)
        field = create_representation_field(dummy_regform)
        focal = create_user(1)
        set_focal_points(managed, {focal})
        set_focal_point_management_enabled(dummy_regform, True)
        db.session.flush()

        _guardrail(dummy_regform, focal, _registration_data(field, managed.id), True)

    @pytest.mark.usefixtures('request_context')
    def test_pre_create_rejects_focal_without_managed_affiliation(
        self, db, dummy_regform, create_user, create_catalog_affiliations, create_representation_field
    ):
        managed, other = create_catalog_affiliations(dummy_regform.event)
        field = create_representation_field(dummy_regform)
        focal = create_user(1)
        set_focal_points(managed, {focal})
        set_focal_point_management_enabled(dummy_regform, True)
        db.session.flush()

        with pytest.raises(UserValueError):
            _guardrail(dummy_regform, focal, _registration_data(field, other.id), True)

    @pytest.mark.usefixtures('request_context')
    def test_pre_create_does_not_block_self_service(
        self, db, dummy_regform, create_user, create_catalog_affiliations, create_representation_field
    ):
        managed, other = create_catalog_affiliations(dummy_regform.event)
        field = create_representation_field(dummy_regform)
        focal = create_user(1)
        set_focal_points(managed, {focal})
        set_focal_point_management_enabled(dummy_regform, True)
        db.session.flush()

        _guardrail(dummy_regform, focal, _registration_data(field, other.id), False)

    @pytest.mark.usefixtures('request_context')
    def test_pre_create_never_blocks_full_manager(
        self, db, dummy_regform, create_user, create_catalog_affiliations, create_representation_field
    ):
        managed, other = create_catalog_affiliations(dummy_regform.event)
        field = create_representation_field(dummy_regform)
        manager = create_user(3)
        dummy_regform.event.update_principal(manager, full_access=True)
        set_focal_points(managed, {manager})
        set_focal_point_management_enabled(dummy_regform, True)
        db.session.flush()

        _guardrail(dummy_regform, manager, _registration_data(field, other.id), True)

    @pytest.mark.usefixtures('request_context')
    def test_pre_create_blocked_on_disabled_form(
        self, db, dummy_regform, create_regform, create_user, create_catalog_affiliations, create_representation_field
    ):
        managed, __ = create_catalog_affiliations(dummy_regform.event)
        form_a, form_b = dummy_regform, create_regform(dummy_regform.event, title='Form B')
        field_a = create_representation_field(form_a)
        field_b = create_representation_field(form_b)
        focal = create_user(1)
        set_focal_points(managed, {focal})
        set_focal_point_management_enabled(form_b, True)
        db.session.flush()

        _guardrail(form_b, focal, _registration_data(field_b, managed.id), True)
        with pytest.raises(UserValueError):
            _guardrail(form_a, focal, _registration_data(field_a, managed.id), True)

    def test_core_create_reachable_by_focal_point(
        self, test_client, db, dummy_regform, create_user, create_catalog_affiliations, create_representation_field
    ):
        set_feature_enabled(dummy_regform.event, 'registration', True)
        create_representation_field(dummy_regform)
        managed, __ = create_catalog_affiliations(dummy_regform.event)
        focal = create_user(1)
        set_focal_points(managed, {focal})
        set_focal_point_management_enabled(dummy_regform, True)
        db.session.flush()

        _login(test_client, focal)
        resp = test_client.get(_create_url(dummy_regform))
        assert resp.status_code == 200

    def test_core_create_denies_plain_non_manager(
        self, test_client, dummy_regform, create_user, create_catalog_affiliations
    ):
        set_feature_enabled(dummy_regform.event, 'registration', True)
        create_catalog_affiliations(dummy_regform.event)

        _login(test_client, create_user(2))
        resp = test_client.get(_create_url(dummy_regform))
        assert resp.status_code == 403


class TestUserSearch:
    def test_user_search_drops_other_affiliation_users(
        self, test_client, app, db, dummy_regform, create_user, monkeypatch, create_catalog_affiliations
    ):
        monkeypatch.setitem(app.config, 'INDICO', {**app.config['INDICO'], 'ALLOW_PUBLIC_USER_SEARCH': False})
        managed, other = create_catalog_affiliations(dummy_regform.event)
        focal = create_user(1)
        set_focal_points(managed, {focal})
        _user_with_affiliation(create_user, db, 10, managed, first_name='Bob', last_name='Shared')
        _user_with_affiliation(create_user, db, 11, other, first_name='Carol', last_name='Shared')
        db.session.flush()
        token = _search_token(app, focal)

        _login(test_client, focal)
        resp = test_client.get('/user/search/', query_string={'last_name': 'Shared', 'token': token})
        assert resp.status_code == 200
        returned_affiliation_ids = {u['affiliation_id'] for u in resp.json['users']}
        assert returned_affiliation_ids <= {managed.id}

    def test_user_search_unbounded_when_public_search_allowed(
        self, test_client, app, db, dummy_regform, create_user, create_catalog_affiliations
    ):
        managed, other = create_catalog_affiliations(dummy_regform.event)
        focal = create_user(1)
        set_focal_points(managed, {focal})
        mine = _user_with_affiliation(create_user, db, 10, managed, first_name='Dan', last_name='Open')
        theirs = _user_with_affiliation(create_user, db, 11, other, first_name='Dana', last_name='Open')
        db.session.flush()
        token = _search_token(app, focal)

        _login(test_client, focal)
        resp = test_client.get('/user/search/', query_string={'last_name': 'Open', 'token': token})
        assert resp.status_code == 200
        returned_ids = {u['id'] for u in resp.json['users']}
        assert {mine.id, theirs.id} <= returned_ids

    def test_user_search_unbounded_for_admin_focal_point(
        self, test_client, app, db, dummy_regform, create_user, monkeypatch, create_catalog_affiliations
    ):
        monkeypatch.setitem(app.config, 'INDICO', {**app.config['INDICO'], 'ALLOW_PUBLIC_USER_SEARCH': False})
        managed, other = create_catalog_affiliations(dummy_regform.event)
        admin = create_user(1, admin=True)
        set_focal_points(managed, {admin})
        mine = _user_with_affiliation(create_user, db, 10, managed, first_name='Erin', last_name='Admin')
        theirs = _user_with_affiliation(create_user, db, 11, other, first_name='Frank', last_name='Admin')
        db.session.flush()
        token = _search_token(app, admin)

        _login(test_client, admin)
        resp = test_client.get('/user/search/', query_string={'last_name': 'Admin', 'token': token})
        assert resp.status_code == 200
        returned_ids = {u['id'] for u in resp.json['users']}
        assert {mine.id, theirs.id} <= returned_ids


class TestRegistrationFormSettings:
    def test_settings_save_persists_focal_point_toggle(self, dummy_regform, app, create_representation_field):
        from indico_affiliation_extras.permissions import focal_point_management_enabled
        from indico_affiliation_extras.plugin import AffiliationExtrasPlugin

        create_representation_field(dummy_regform)
        with app.test_request_context(method='POST', data={'focal_point_management': '1'}):
            AffiliationExtrasPlugin.instance._persist_focal_point_setting(dummy_regform)
        assert focal_point_management_enabled(dummy_regform) is True

        with app.test_request_context(method='POST', data={}):
            AffiliationExtrasPlugin.instance._persist_focal_point_setting(dummy_regform)
        assert focal_point_management_enabled(dummy_regform) is False


class TestFocalPointPermissions:
    def test_focal_point_bounded_to_own_affiliation(self, dummy_regform, setup_focal_point, get_scoped_list):
        focal, in_range, out_range = setup_focal_point(dummy_regform)

        assert in_range.can_manage(focal, 'registration_edit') is True
        assert out_range.can_manage(focal, 'registration_edit') is False
        assert in_range.can_manage(focal, 'registration') is False
        assert in_range.can_manage(focal, 'registration_checkin') is False
        assert get_scoped_list(dummy_regform, focal) == [in_range]
        assert dummy_regform.get_managed_registration_count(focal) == 1

    def test_focal_point_can_moderate_own_affiliation(self, dummy_regform, setup_focal_point):
        focal, in_range, out_range = setup_focal_point(dummy_regform)

        assert in_range.can_manage(focal, 'registration_moderation') is True
        assert out_range.can_manage(focal, 'registration_moderation') is False

    def test_focal_point_management_disabled_blocks_moderation(self, dummy_regform, setup_focal_point):
        focal, in_range, __ = setup_focal_point(dummy_regform)
        set_focal_point_management_enabled(dummy_regform, False)

        assert in_range.can_manage(focal, 'registration_moderation') is False

    @pytest.mark.parametrize('permission', REGISTRATION_PERMISSIONS)
    def test_genuine_registration_grant_also_focal_is_unrestricted(
        self, db, dummy_regform, setup_focal_point, get_scoped_list, permission
    ):
        focal, in_range, out_range = setup_focal_point(dummy_regform)
        dummy_regform.event.update_principal(focal, permissions={permission})
        db.session.flush()

        assert out_range.can_manage(focal, permission) is True
        assert set(get_scoped_list(dummy_regform, focal)) == {in_range, out_range}

    def test_genuine_manager_also_focal_is_unrestricted(self, dummy_regform, setup_focal_point, get_scoped_list):
        manager, in_range, out_range = setup_focal_point(dummy_regform, user_id=3, full_manager=True)

        assert in_range.can_manage(manager, 'registration_edit') is True
        assert out_range.can_manage(manager, 'registration_edit') is True
        assert set(get_scoped_list(dummy_regform, manager)) == {in_range, out_range}
        assert dummy_regform.get_managed_registration_count(manager) == 2

    def test_non_focal_user_unaffected(self, db, dummy_regform, create_user, setup_focal_point):
        from indico_affiliation_extras.plugin import AffiliationExtrasPlugin

        __, in_range, out_range = setup_focal_point(dummy_regform)
        outsider = create_user(9)
        db.session.flush()

        assert in_range.can_manage(outsider, 'registration_edit') is False
        assert out_range.can_manage(outsider, 'registration_edit') is False
        assert AffiliationExtrasPlugin.instance._filter_registration_list(dummy_regform, outsider) is None

    def test_focal_point_management_disabled_blocks_access(self, dummy_regform, setup_focal_point):
        focal, in_range, __ = setup_focal_point(dummy_regform)
        assert in_range.can_manage(focal, 'registration_edit') is True
        set_focal_point_management_enabled(dummy_regform, False)
        assert in_range.can_manage(focal, 'registration_edit') is False

    def test_per_form_toggle_isolates_forms(
        self,
        db,
        dummy_regform,
        create_regform,
        create_user,
        create_event_catalog,
        create_representation_field,
        create_representation_registration,
        get_scoped_list,
    ):
        event = dummy_regform.event
        managed = Affiliation(name='CERN')
        db.session.add(managed)
        db.session.flush()
        create_event_catalog(event, [managed])

        form_a, form_b = dummy_regform, create_regform(event, title='Form B')
        reg_a = create_representation_registration(create_representation_field(form_a), managed.id)
        reg_b = create_representation_registration(create_representation_field(form_b), managed.id)
        focal = create_user(1)
        set_focal_points(managed, {focal})
        set_focal_point_management_enabled(form_a, True)
        set_focal_point_management_enabled(form_b, True)
        db.session.flush()

        assert reg_a.can_manage(focal, 'registration_edit') is True
        assert reg_b.can_manage(focal, 'registration_edit') is True

        set_focal_point_management_enabled(form_a, False)
        assert reg_a.can_manage(focal, 'registration_edit') is False
        assert reg_b.can_manage(focal, 'registration_edit') is True
        assert get_scoped_list(form_a, focal) == []
        assert get_scoped_list(form_b, focal) == [reg_b]

    def test_focal_point_cannot_export(self, test_client, dummy_regform, setup_focal_point):
        set_feature_enabled(dummy_regform.event, 'registration', True)
        focal, __, __ = setup_focal_point(dummy_regform)
        with test_client.session_transaction() as sess:
            sess.set_session_user(focal)

        url = f'/event/{dummy_regform.event.id}/manage/registration/{dummy_regform.id}/registrations/registrations.csv'
        assert test_client.get(url).status_code == 403

    def test_focal_point_user_search_bounded_to_own_affiliation(
        self, dummy_regform, setup_focal_point, patch_indico_config
    ):
        patch_indico_config('ALLOW_PUBLIC_USER_SEARCH', False)
        focal, __, __ = setup_focal_point(dummy_regform)
        (managed_id,) = get_focal_affiliation_ids(focal)
        results = [{'id': 1, 'affiliation_id': managed_id}, {'id': 2, 'affiliation_id': None}]

        signals.users.filter_user_search_results.send(object(), user=focal, results=results)

        assert results == [{'id': 1, 'affiliation_id': managed_id}]


class TestRegistrationList:
    def test_reglist_reachable_by_focal_point(
        self, test_client, db, dummy_regform, create_user, create_representation_field, create_catalog_affiliations
    ):
        set_feature_enabled(dummy_regform.event, 'registration', True)
        create_representation_field(dummy_regform)
        managed, __ = create_catalog_affiliations(dummy_regform.event)
        focal = create_user(1)
        set_focal_points(managed, {focal})
        set_focal_point_management_enabled(dummy_regform, True)
        db.session.flush()

        _login(test_client, focal)
        resp = test_client.get(_reglist_url(dummy_regform))
        assert resp.status_code == 200

    def test_reglist_denies_plain_non_manager(
        self, test_client, dummy_regform, create_user, create_catalog_affiliations
    ):
        set_feature_enabled(dummy_regform.event, 'registration', True)
        create_catalog_affiliations(dummy_regform.event)

        _login(test_client, create_user(2))
        resp = test_client.get(_reglist_url(dummy_regform))
        assert resp.status_code == 403

    def test_reglist_reachable_by_manager(self, test_client, db, dummy_regform, dummy_user):
        set_feature_enabled(dummy_regform.event, 'registration', True)
        dummy_regform.event.update_principal(dummy_user, full_access=True)
        db.session.flush()

        _login(test_client, dummy_user)
        resp = test_client.get(_reglist_url(dummy_regform))
        assert resp.status_code == 200

    def test_manager_handler_unrestricted(self, db, dummy_regform, create_user, create_catalog_affiliations):
        from indico_affiliation_extras.plugin import AffiliationExtrasPlugin

        managed, __ = create_catalog_affiliations(dummy_regform.event)
        manager = create_user(3)
        set_focal_points(managed, {manager})
        dummy_regform.event.update_principal(manager, full_access=True)
        db.session.flush()

        assert AffiliationExtrasPlugin.instance._filter_registration_list(dummy_regform, manager) is None

    def test_generator_scopes_list_for_focal_point(
        self,
        db,
        dummy_regform,
        create_user,
        create_catalog_affiliations,
        create_representation_field,
        create_representation_registration,
        get_scoped_list,
    ):
        managed, other = create_catalog_affiliations(dummy_regform.event)
        field = create_representation_field(dummy_regform)
        mine = create_representation_registration(field, managed.id)
        create_representation_registration(field, other.id)

        focal = create_user(1)
        set_focal_points(managed, {focal})
        set_focal_point_management_enabled(dummy_regform, True)
        db.session.flush()

        assert get_scoped_list(dummy_regform, focal) == [mine]

    def test_generator_unrestricted_for_manager(
        self,
        db,
        dummy_regform,
        create_user,
        create_catalog_affiliations,
        create_representation_field,
        create_representation_registration,
        get_scoped_list,
    ):
        managed, other = create_catalog_affiliations(dummy_regform.event)
        field = create_representation_field(dummy_regform)
        mine = create_representation_registration(field, managed.id)
        theirs = create_representation_registration(field, other.id)

        manager = create_user(3)
        set_focal_points(managed, {manager})
        dummy_regform.event.update_principal(manager, full_access=True)
        db.session.flush()

        assert set(get_scoped_list(dummy_regform, manager)) == {mine, theirs}


class TestLinkedEvents:
    def test_linked_events_scoped_by_end_date(self, db, create_user, create_focal_event):
        managed = Affiliation(name='CERN')
        db.session.add(managed)
        db.session.flush()
        now = now_utc()
        ongoing = create_focal_event(managed, start_dt=now - timedelta(days=30), end_dt=now + timedelta(days=1))
        create_focal_event(managed, start_dt=now - timedelta(days=60), end_dt=now - timedelta(days=30))
        focal = create_user(1)
        set_focal_points(managed, {focal})
        db.session.flush()

        assert set(get_linked_events(focal, now - timedelta(days=7))) == {ongoing}

    def test_linked_events_not_truncated(self, db, create_user, create_focal_event):
        managed = Affiliation(name='CERN')
        db.session.add(managed)
        db.session.flush()
        events = {create_focal_event(managed) for __ in range(30)}
        focal = create_user(1)
        set_focal_points(managed, {focal})
        db.session.flush()

        assert set(get_linked_events(focal)) == events


class TestUserMerge:
    def test_merge_users_moves_focal_points(self, db, create_user):
        source, target = create_user(1), create_user(2)
        cern, mit, epfl = Affiliation(name='CERN'), Affiliation(name='MIT'), Affiliation(name='EPFL')
        db.session.add_all([cern, mit, epfl])
        db.session.flush()
        set_focal_points(cern, {source})
        set_focal_points(mit, {source, target})
        set_focal_points(epfl, {target})
        db.session.flush()

        merge_users(source, target)

        assert get_focal_affiliation_ids(target) == {cern.id, mit.id, epfl.id}
        assert get_focal_affiliation_ids(source) == set()


class TestRegistrationManagement:
    def test_registration_can_manage_grants_focal_point_edit(
        self,
        db,
        dummy_regform,
        create_user,
        create_event_catalog,
        create_representation_field,
        create_representation_registration,
    ):
        managed = Affiliation(name='CERN')
        db.session.add(managed)
        db.session.flush()
        create_event_catalog(dummy_regform.event, [managed])
        registration = create_representation_registration(create_representation_field(dummy_regform), managed.id)
        focal = create_user(1)
        set_focal_points(managed, {focal})
        set_focal_point_management_enabled(dummy_regform, True)
        db.session.flush()

        assert registration.can_manage(focal, 'registration_edit') is True
        assert registration.can_manage(focal, 'registration') is False
        assert registration.can_manage(create_user(2), 'registration_edit') is False


@pytest.mark.usefixtures('no_csrf_check')
class TestAffiliationContactsSave:
    @pytest.mark.parametrize(
        ('payload', 'expected'),
        (
            ({'name': 'Updated'}, [('Ops', ['ops@example.test'])]),
            ({'contact_lists': []}, []),
            ({'contact_lists': [{'name': 'New', 'emails': ['NEW@example.test']}]}, [('New', ['new@example.test'])]),
        ),
    )
    def test_update(self, test_client, db, create_user, dummy_contact_affiliation, payload, expected):
        _login(test_client, create_user(1, admin=True))
        affiliation = dummy_contact_affiliation

        resp = test_client.patch(f'/api/admin/affiliations/{affiliation.id}', json=payload)

        assert resp.status_code == 204
        db.session.expire_all()
        assert [(lst.name, lst.emails) for lst in affiliation.contact_lists] == expected
        resp = test_client.get('/api/admin/affiliations')
        assert resp.status_code == 200
        saved = next(item for item in resp.json if item['id'] == affiliation.id)
        assert [(lst['name'], lst['emails']) for lst in saved['contact_lists']] == expected

    @pytest.mark.parametrize(
        'contact_lists',
        (
            [{'name': 'New', 'emails': []}],
            [{'name': 'New', 'emails': ['not-an-email']}],
            [{'name': 'Ops', 'emails': ['a@example.test']}, {'name': 'ops', 'emails': ['b@example.test']}],
        ),
        ids=('empty-emails', 'malformed-email', 'duplicate-names'),
    )
    def test_rejected_update_preserves_contacts(
        self,
        test_client,
        db,
        create_user,
        dummy_contact_affiliation,
        contact_lists,
    ):
        _login(test_client, create_user(1, admin=True))
        affiliation = dummy_contact_affiliation

        resp = test_client.patch(
            f'/api/admin/affiliations/{affiliation.id}',
            json={'name': 'Changed', 'contact_lists': contact_lists},
        )

        assert resp.status_code == 422
        assert 'contact_lists' in resp.json['webargs_errors']
        db.session.expire_all()
        assert affiliation.name == 'CERN'
        assert [(lst.name, lst.emails) for lst in affiliation.contact_lists] == [('Ops', ['ops@example.test'])]

    def test_undeliverable_email_preserves_contacts(
        self,
        test_client,
        db,
        create_user,
        dummy_contact_affiliation,
        mocker,
    ):
        _login(test_client, create_user(1, admin=True))
        affiliation = dummy_contact_affiliation
        mocker.patch(
            'email_validator.validate_email',
            side_effect=email_validator.EmailUndeliverableError('No MX records'),
        )

        resp = test_client.patch(
            f'/api/admin/affiliations/{affiliation.id}',
            json={
                'contact_lists': [{'name': 'New', 'emails': ['new@example.test']}],
            },
        )

        assert resp.status_code == 422
        assert 'contact_lists' in resp.json['webargs_errors']
        db.session.expire_all()
        assert [(lst.name, lst.emails) for lst in affiliation.contact_lists] == [('Ops', ['ops@example.test'])]
