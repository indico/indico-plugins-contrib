# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest

from indico.modules.events.cloning import EventCloner
from indico.modules.events.features.util import set_feature_enabled
from indico.modules.events.registration.util import clone_registration_form

from indico_affiliation_extras.fields import RepresentationField
from indico_affiliation_extras.models.lists import AffiliationListMode
from indico_affiliation_extras.permissions import focal_point_management_enabled, set_focal_point_management_enabled
from indico_affiliation_extras.util import get_representation_catalog


pytest_plugins = 'indico.modules.events.registration.testing.fixtures'


@pytest.mark.parametrize(('inherited', 'same_category'), ((False, True), (True, True), (True, False)))
def test_event_clone_preserves_explicit_catalog_and_remaps_answers(
    db,
    dummy_regform,
    dummy_contact_affiliation,
    create_event,
    create_event_catalog,
    create_representation_field,
    create_representation_registration,
    inherited,
    same_category,
    create_category,
):
    source = dummy_regform.event
    source.category = create_category()
    selected = create_event_catalog(source, [dummy_contact_affiliation])
    if inherited:
        selected.catalog.event = None
        selected.catalog.category = source.category
    field = create_representation_field(dummy_regform)
    field.data = {'catalog_id': selected.catalog_id}
    second = create_representation_field(dummy_regform)
    second.data = {'catalog_id': selected.catalog_id}
    registration = create_representation_registration(field, dummy_contact_affiliation.id)
    registration.data_by_field[field.id].data = {
        'representation_id': selected.id,
        'representation_name': selected.name,
        'affiliation': {'id': dummy_contact_affiliation.id, 'text': dummy_contact_affiliation.name},
    }
    set_focal_point_management_enabled(dummy_regform, True)
    set_feature_enabled(source, 'registration', True)
    target = create_event(category=source.category if same_category else create_category())
    db.session.flush()

    EventCloner.run_cloners(source, target, {'registration_forms', 'registrations'})
    db.session.flush()

    cloned_form = target.registration_forms[0]
    fields = [item for item in cloned_form.active_fields if item.input_type == RepresentationField.name]
    catalog_ids = {item.data['catalog_id'] for item in fields}
    assert len(catalog_ids) == 1
    cloned_catalog = get_representation_catalog(fields[0])
    assert cloned_catalog is not None
    if inherited and same_category:
        assert cloned_catalog == selected.catalog
        assert not target.affiliation_catalogs
    else:
        assert cloned_catalog.event == target
        assert cloned_catalog.id != selected.catalog_id
        assert len(target.affiliation_catalogs) == 1
    cloned_value = cloned_form.registrations[0].data_by_field[fields[0].id].data
    assert cloned_value['representation_id'] == cloned_catalog.lists[0].id
    assert cloned_value['affiliation']['id'] == dummy_contact_affiliation.id
    assert focal_point_management_enabled(cloned_form)
    assert field.data == {'catalog_id': selected.catalog_id}


def test_form_clone_preserves_explicit_catalog(dummy_regform, create_event_catalog, create_representation_field):
    selected = create_event_catalog(dummy_regform.event, [])
    field = create_representation_field(dummy_regform)
    field.data = {'catalog_id': selected.catalog_id}

    cloned_form = clone_registration_form(dummy_regform, 'Funding copy')

    cloned_field = next(item for item in cloned_form.active_fields if item.input_type == RepresentationField.name)
    assert get_representation_catalog(cloned_field) == selected.catalog


def test_event_clone_does_not_copy_an_unavailable_catalog(
    db, dummy_regform, create_event, create_event_catalog, create_representation_field
):
    selected = create_event_catalog(create_event(), [])
    field = create_representation_field(dummy_regform)
    field.data = {'catalog_id': selected.catalog_id}
    set_feature_enabled(dummy_regform.event, 'registration', True)
    target = create_event()
    db.session.flush()

    EventCloner.run_cloners(dummy_regform.event, target, {'registration_forms'})

    assert not target.affiliation_catalogs
    cloned_field = next(
        item for item in target.registration_forms[0].active_fields if item.input_type == RepresentationField.name
    )
    assert get_representation_catalog(cloned_field) is None


def test_event_clone_preserves_custom_affiliation_mode(
    db, dummy_regform, create_event, create_event_catalog, create_representation_field
):
    selected = create_event_catalog(dummy_regform.event, [])
    selected.affiliation_mode = AffiliationListMode.custom
    field = create_representation_field(dummy_regform)
    field.data = {'catalog_id': selected.catalog_id}
    set_feature_enabled(dummy_regform.event, 'registration', True)
    target = create_event()
    db.session.flush()

    EventCloner.run_cloners(dummy_regform.event, target, {'registration_forms'})

    cloned_field = next(
        item for item in target.registration_forms[0].active_fields if item.input_type == RepresentationField.name
    )
    [cloned_list] = get_representation_catalog(cloned_field).lists
    assert cloned_list.affiliation_mode == AffiliationListMode.custom
