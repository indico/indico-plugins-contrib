# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from datetime import UTC, datetime
from io import BytesIO

import pytest

from indico.modules.events.registration.models.form_fields import (RegistrationFormField,
                                                                   RegistrationFormPersonalDataField)
from indico.modules.events.registration.models.items import (PersonalDataType, RegistrationFormPersonalDataSection,
                                                             RegistrationFormSection)
from indico.modules.events.registration.models.registrations import Registration, RegistrationData, RegistrationState


@pytest.fixture
def make_section(db):
    """Factory: create a section on any regform."""
    def _make_section(regform, title='Test Section'):
        section = RegistrationFormSection(
            registration_form=regform,
            title=title,
            is_manager_only=False,
        )
        db.session.add(section)
        db.session.flush()
        return section
    return _make_section


@pytest.fixture
def make_pd_section(db):
    """Factory: get or create a personal-data section on any regform.

    Each registration form may only have one section_pd (unique constraint),
    so this returns the existing one if already present.
    """
    def _make_pd_section(regform, title='Personal Data'):
        existing = next(
            (item for item in regform.form_items
             if item.type.name == 'section_pd'),
            None,
        )
        if existing is not None:
            return existing
        section = RegistrationFormPersonalDataSection(
            registration_form=regform,
            title=title,
            is_manager_only=False,
        )
        db.session.add(section)
        db.session.flush()
        return section
    return _make_pd_section


@pytest.fixture
def make_pd_field(db):
    """Factory: get or create a RegistrationFormPersonalDataField (type field_pd).

    Each registration form may only have one field per personal_data_type (unique
    constraint), so returns the existing field if already present.  ``internal_name``
    is set to ``pd_type.name`` to mirror how Indico initialises personal-data fields.
    """
    _field_data_by_type = dict(PersonalDataType.FIELD_DATA)

    def _make_pd_field(section, pd_type: PersonalDataType, **kwargs):
        existing = next(
            (item for item in section.registration_form.form_items
             if getattr(item, 'personal_data_type', None) == pd_type),
            None,
        )
        if existing is not None:
            return existing
        field = RegistrationFormPersonalDataField(
            parent=section,
            registration_form=section.registration_form,
        )
        field.title = pd_type.get_title()
        field.input_type = _field_data_by_type[pd_type]['input_type']
        field.data = kwargs
        field.versioned_data = {}
        field.internal_name = pd_type.name
        field.personal_data_type = pd_type
        db.session.flush()
        return field
    return _make_pd_field


@pytest.fixture
def make_field(db):
    """Create a RegistrationFormField with an internal name."""
    def _make_field(section, internal_name, input_type, **kwargs):
        choices = kwargs.pop('choices', None)

        # Without this, ui_default_value hits a KeyError branch and returns None instead of {}.
        if input_type == 'single_choice' and 'default_item' not in kwargs:
            kwargs['default_item'] = None

        field = RegistrationFormField(parent=section, registration_form=section.registration_form)
        field.title = ' '.join(w.capitalize() for w in internal_name.split('_'))
        field.input_type = input_type
        field.data = kwargs
        field.versioned_data = {'choices': choices} if choices is not None else {}
        field.internal_name = internal_name
        db.session.flush()
        return field
    return _make_field


@pytest.fixture
def make_registration(db):
    """Create a completed Registration with RegistrationData entries.

    field_values is a dict mapping field → data_value:
    - Regular fields: pass the JSON-serialisable value (or None for no value).
    - File/picture fields: pass a dict with keys ``filename``, ``content_type``,
      and ``content`` (bytes) to create a RegistrationData entry backed by
      storage.  Pass None to create a RegistrationData with no file stored.
    """
    def _make_registration(user, regform, field_values=None, *,
                            state=RegistrationState.complete, submitted_dt=None):
        reg = Registration(
            registration_form=regform,
            user=user,
            state=state,
            submitted_dt=submitted_dt or datetime.now(UTC),
            currency=regform.currency or 'USD',
            email=user.email,
            first_name=user.first_name or 'Test',
            last_name=user.last_name or 'User',
        )
        db.session.add(reg)
        db.session.flush()
        for field, data_value in (field_values or {}).items():
            if field.input_type in ('file', 'picture') and isinstance(data_value, dict):
                reg_data = RegistrationData(
                    registration=reg,
                    field_data=field.current_data,
                    data=None,
                )
                db.session.add(reg_data)
                db.session.flush()
                reg_data.filename = data_value.get('filename', 'test.txt')
                reg_data.content_type = data_value.get('content_type', 'text/plain')
                with BytesIO(data_value.get('content', b'test content')) as f:
                    reg_data.save(f)
            else:
                db.session.add(RegistrationData(
                    registration=reg,
                    field_data=field.current_data,
                    data=data_value,
                ))
        db.session.flush()
        return reg
    return _make_registration
