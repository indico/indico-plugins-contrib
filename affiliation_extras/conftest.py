# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from itertools import count

import pytest
from flask import session

from indico.core.plugins import IndicoPlugin
from indico.modules.events.registration.lists import RegistrationListGenerator
from indico.modules.events.registration.models.form_fields import RegistrationFormField
from indico.modules.events.registration.models.registrations import Registration, RegistrationData, RegistrationState
from indico.modules.users.models.affiliations import Affiliation

from indico_affiliation_extras.fields import RepresentationField
from indico_affiliation_extras.models.catalogs import AffiliationCatalog
from indico_affiliation_extras.models.contacts import AffiliationContactList
from indico_affiliation_extras.models.lists import AffiliationList
from indico_affiliation_extras.settings import event_settings


@pytest.fixture(autouse=True)
def _plugin_manifest(mocker):
    """Mock the plugin's webpack manifest.

    Plugin assets are not built when running tests, so ``IndicoPlugin.manifest``
    returns ``None`` and any page that injects a plugin bundle raises a
    ``RuntimeError``. Indico core mocks its own manifest the same way in
    ``make_test_client``; we do the same for plugin bundles here.
    """
    mocker.patch.object(IndicoPlugin, 'manifest')


@pytest.fixture
def dummy_contact_affiliation(db):
    affiliation = Affiliation(name='CERN')
    db.session.add(affiliation)
    affiliation.contact_lists.append(AffiliationContactList(name='Ops', emails=['ops@example.test']))
    db.session.flush()
    return affiliation


@pytest.fixture
def create_representation_field(db):
    def _create_representation_field(regform):
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

    return _create_representation_field


@pytest.fixture
def create_event_catalog(db):
    def _create_event_catalog(event, affiliations):
        catalog = AffiliationCatalog(name='Catalog', event=event)
        db.session.add(catalog)
        db.session.flush()
        affiliation_list = AffiliationList(catalog=catalog, name='Representatives', position=1, is_enabled=True)
        affiliation_list.affiliations.update(affiliations)
        db.session.add(affiliation_list)
        db.session.flush()
        event_settings.set(event, 'default_catalog_id', catalog.id)
        return affiliation_list

    return _create_event_catalog


@pytest.fixture
def create_catalog_affiliations(db, create_event_catalog):
    def _create_catalog_affiliations(event):
        managed = Affiliation(name='CERN')
        other = Affiliation(name='MIT')
        db.session.add_all([managed, other])
        db.session.flush()
        create_event_catalog(event, [managed, other])
        return managed, other

    return _create_catalog_affiliations


@pytest.fixture
def create_representation_registration(db):
    ids = count(1)

    def _create_representation_registration(field, affiliation_id):
        regform = field.registration_form
        registration = Registration(
            first_name='Guinea',
            last_name='Pig',
            state=RegistrationState.complete,
            currency='USD',
            email=f'registrant{next(ids)}@example.test',
            registration_form=regform,
        )
        regform.event.registrations.append(registration)
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
        return registration

    return _create_representation_registration


@pytest.fixture
def get_scoped_list(request_context):
    def _get_scoped_list(regform, user):
        session.set_session_user(user)
        return RegistrationListGenerator(regform=regform).get_list_kwargs()['registrations']

    return _get_scoped_list
