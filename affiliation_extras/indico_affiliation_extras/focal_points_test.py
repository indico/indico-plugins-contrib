# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from indico.modules.events.registration.models.form_fields import RegistrationFormField
from indico.modules.events.registration.models.registrations import RegistrationData
from indico.modules.users.models.affiliations import Affiliation

from indico_affiliation_extras.fields import RepresentationField
from indico_affiliation_extras.focal_points import (
    can_manage_registration,
    get_focal_affiliation_ids,
    get_registration_affiliation_ids,
)
from indico_affiliation_extras.models.catalogs import AffiliationCatalog
from indico_affiliation_extras.models.focal_points import set_focal_points
from indico_affiliation_extras.models.lists import AffiliationList
from indico_affiliation_extras.permissions import set_focal_point_management_enabled
from indico_affiliation_extras.settings import event_settings


pytest_plugins = 'indico.modules.events.registration.testing.fixtures'


def _add_event_catalog(db, event, affiliations):
    catalog = AffiliationCatalog(name='Catalog', event=event)
    db.session.add(catalog)
    db.session.flush()
    affiliation_list = AffiliationList(catalog=catalog, name='Representatives', position=1, is_enabled=True)
    affiliation_list.affiliations.update(affiliations)
    db.session.add(affiliation_list)
    db.session.flush()
    event_settings.set(event, 'default_catalog_id', catalog.id)


def _add_representation_field(db, regform):
    field = RegistrationFormField(
        input_type=RepresentationField.name,
        title='Representation',
        parent=regform.sections[0],
        registration_form=regform,
    )
    field.data = {}
    field.versioned_data = {}
    db.session.add(field)
    db.session.flush()
    return field


def _set_representation(db, registration, field, affiliation_id):
    RegistrationData(
        registration=registration,
        field_data=field.current_data,
        data={
            'representation_id': 1,
            'representation_name': 'Delegates',
            'affiliation': {'id': affiliation_id, 'text': 'CERN'},
        },
    )
    db.session.flush()


def test_registration_affiliation_ids_from_representation(db, dummy_regform, dummy_reg):
    affiliation = Affiliation(name='CERN')
    db.session.add(affiliation)
    db.session.flush()
    field = _add_representation_field(db, dummy_regform)
    _set_representation(db, dummy_reg, field, affiliation.id)

    assert get_registration_affiliation_ids(dummy_reg) == {affiliation.id}


def test_registration_affiliation_ids_ignores_free_text(db, dummy_regform, dummy_reg):
    field = _add_representation_field(db, dummy_regform)
    _set_representation(db, dummy_reg, field, None)

    assert get_registration_affiliation_ids(dummy_reg) == set()


def test_get_focal_affiliation_ids(db, create_user):
    user = create_user(1)
    cern = Affiliation(name='CERN')
    db.session.add(cern)
    db.session.flush()
    set_focal_points(cern, {user})
    db.session.flush()

    assert get_focal_affiliation_ids(user) == {cern.id}
    assert get_focal_affiliation_ids(None) == set()


def test_can_manage_registration(db, dummy_regform, dummy_reg, create_user):
    managed = Affiliation(name='CERN')
    other = Affiliation(name='MIT')
    db.session.add_all([managed, other])
    db.session.flush()
    _add_event_catalog(db, dummy_regform.event, [managed, other])
    field = _add_representation_field(db, dummy_regform)
    _set_representation(db, dummy_reg, field, managed.id)

    focal = create_user(1)
    set_focal_points(managed, {focal})
    non_focal = create_user(2)
    set_focal_points(other, {non_focal})
    db.session.flush()

    assert can_manage_registration(focal, dummy_reg) is True
    assert can_manage_registration(non_focal, dummy_reg) is False
    assert can_manage_registration(None, dummy_reg) is False


def test_focal_event_ids(db, dummy_regform, dummy_reg, create_user):
    from indico_affiliation_extras.focal_points import focal_event_ids

    managed = Affiliation(name='CERN')
    db.session.add(managed)
    db.session.flush()
    field = _add_representation_field(db, dummy_regform)
    _set_representation(db, dummy_reg, field, managed.id)
    focal = create_user(1)
    set_focal_points(managed, {focal})
    db.session.flush()

    assert focal_event_ids(focal) == {dummy_regform.event.id}
    assert focal_event_ids(create_user(2)) == set()


def test_registration_can_manage_grants_focal_point_edit(db, dummy_regform, dummy_reg, create_user):
    managed = Affiliation(name='CERN')
    db.session.add(managed)
    db.session.flush()
    _add_event_catalog(db, dummy_regform.event, [managed])
    field = _add_representation_field(db, dummy_regform)
    _set_representation(db, dummy_reg, field, managed.id)
    focal = create_user(1)
    set_focal_points(managed, {focal})
    set_focal_point_management_enabled(dummy_regform, True)
    db.session.flush()

    assert dummy_reg.can_manage(focal, 'registration_edit') is True
    assert dummy_reg.can_manage(focal, 'registration') is False
    assert dummy_reg.can_manage(create_user(2), 'registration_edit') is False


def test_registration_can_manage_grants_event_manager(db, dummy_reg, create_user):
    manager = create_user(3)
    dummy_reg.event.update_principal(manager, full_access=True)
    db.session.flush()

    assert dummy_reg.can_manage(manager, 'registration_edit') is True
