# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest

from indico.modules.events.registration.models.items import PersonalDataType, RegistrationFormSection
from indico.modules.events.registration.models.registrations import Registration, RegistrationData
from indico.modules.users.models.affiliations import Affiliation

from indico_affiliation_extras.focal_points import (
    focal_event_ids,
    focal_list_criterion,
    get_focal_affiliation_ids,
    set_focal_points,
)
from indico_affiliation_extras.permissions import set_focal_point_management_enabled


pytest_plugins = 'indico.modules.events.registration.testing.fixtures'


def _affiliation_field(regform):
    return next(
        field
        for field in regform.sections[0].fields
        if field.is_field and field.personal_data_type == PersonalDataType.affiliation
    )


def _set_affiliation(db, registration, field, affiliation_id):
    db.session.add(
        RegistrationData(
            registration=registration,
            field_data=field.current_data,
            data={'id': affiliation_id, 'text': 'CERN'},
        )
    )
    db.session.flush()


def _focal_query(regform, user):
    return Registration.query.with_parent(regform).filter(focal_list_criterion(user, regform.event)).all()


class TestFocalPointQueries:
    def test_get_focal_affiliation_ids(self, db, create_user):
        user = create_user(1)
        cern = Affiliation(name='CERN')
        db.session.add(cern)
        db.session.flush()
        set_focal_points(cern, {user})
        db.session.flush()

        assert get_focal_affiliation_ids(user) == {cern.id}
        assert get_focal_affiliation_ids(None) == set()

    def test_focal_event_ids(
        self, db, dummy_regform, create_user, create_representation_field, create_representation_registration
    ):
        managed = Affiliation(name='CERN')
        db.session.add(managed)
        db.session.flush()
        create_representation_registration(create_representation_field(dummy_regform), managed.id)
        focal = create_user(1)
        set_focal_points(managed, {focal})
        set_focal_point_management_enabled(dummy_regform, True)
        db.session.flush()

        assert focal_event_ids(focal) == {dummy_regform.event.id}
        assert focal_event_ids(create_user(2)) == set()

        set_focal_point_management_enabled(dummy_regform, False)
        db.session.flush()
        assert focal_event_ids(focal) == set()


class TestRegistrationCriterion:
    def test_criterion_matches_representation_field(
        self,
        db,
        dummy_regform,
        create_user,
        create_catalog_affiliations,
        create_representation_field,
        create_representation_registration,
    ):
        managed, other = create_catalog_affiliations(dummy_regform.event)
        field = create_representation_field(dummy_regform)
        mine = create_representation_registration(field, managed.id)
        create_representation_registration(field, other.id)
        create_representation_registration(field, None)

        focal = create_user(1)
        set_focal_points(managed, {focal})
        db.session.flush()

        assert _focal_query(dummy_regform, focal) == [mine]

    @pytest.mark.parametrize(
        ('attr', 'value'),
        (
            ('is_enabled', False),
            ('is_deleted', True),
        ),
    )
    def test_criterion_ignores_field_in_inactive_section(
        self,
        db,
        dummy_regform,
        create_user,
        create_catalog_affiliations,
        create_representation_field,
        create_representation_registration,
        attr,
        value,
    ):
        managed, __ = create_catalog_affiliations(dummy_regform.event)
        field = create_representation_field(dummy_regform)
        field.parent = RegistrationFormSection(registration_form=dummy_regform, title='Extra')
        create_representation_registration(field, managed.id)

        focal = create_user(1)
        set_focal_points(managed, {focal})
        setattr(field.parent, attr, value)
        db.session.flush()

        assert _focal_query(dummy_regform, focal) == []

    def test_criterion_matches_representation_only(
        self,
        db,
        dummy_regform,
        create_user,
        create_registration,
        create_catalog_affiliations,
        create_representation_field,
        create_representation_registration,
    ):
        managed, __ = create_catalog_affiliations(dummy_regform.event)
        via_affiliation = create_registration(create_user(5), dummy_regform)
        _set_affiliation(db, via_affiliation, _affiliation_field(dummy_regform), managed.id)
        via_representation = create_representation_registration(create_representation_field(dummy_regform), managed.id)

        focal = create_user(1)
        set_focal_points(managed, {focal})
        db.session.flush()

        assert _focal_query(dummy_regform, focal) == [via_representation]

    def test_criterion_empty_for_non_focal(
        self,
        db,
        dummy_regform,
        create_user,
        create_catalog_affiliations,
        create_representation_field,
        create_representation_registration,
    ):
        managed, other = create_catalog_affiliations(dummy_regform.event)
        create_representation_registration(create_representation_field(dummy_regform), managed.id)

        non_focal = create_user(2)
        set_focal_points(other, {non_focal})
        db.session.flush()

        assert _focal_query(dummy_regform, non_focal) == []

    def test_criterion_admin_override_intact(
        self,
        db,
        dummy_regform,
        create_user,
        create_catalog_affiliations,
        create_representation_field,
        create_representation_registration,
    ):
        managed, __ = create_catalog_affiliations(dummy_regform.event)
        create_representation_registration(create_representation_field(dummy_regform), managed.id)

        admin = create_user(7, admin=True)
        db.session.flush()

        assert _focal_query(dummy_regform, admin) == []
