from datetime import UTC, datetime
from io import BytesIO

import pytest

from indico.modules.events.registration.models.form_fields import RegistrationFormField
from indico.modules.events.registration.models.items import RegistrationFormSection
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
