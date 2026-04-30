# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from sqlalchemy import tuple_

from indico.core.db import db
from indico.modules.events.registration.models.form_fields import RegistrationFormFieldData
from indico.modules.events.registration.models.items import RegistrationFormItem
from indico.modules.events.registration.models.registrations import Registration, RegistrationData, RegistrationState
from indico.modules.files.models.files import File
from indico.util.string import camelize_keys


def _create_prefill_file(reg_data, field):
    """Create an unclaimed File from RegistrationData for use as a prefill value.

    The returned File is unclaimed and will be cleaned up automatically if the user
    does not complete the registration.  For picture fields, ``registration_picture_checked``
    is set in the file's metadata so the picture validator accepts it on submission.

    Args:
        reg_data: RegistrationData whose file content will be copied
        field: Target RegistrationFormField being prefilled

    Returns:
        A new unclaimed File object, or None if the source has no file stored
    """
    if not reg_data.storage_file_id:
        return None

    meta = {'regform_field_id': field.id}
    if field.input_type == 'picture':
        meta['registration_picture_checked'] = True

    with reg_data.open() as f:
        new_file = File.create_from_stream(
            stream=f,
            filename=reg_data.filename,
            content_type=reg_data.content_type,
            context=('registration_prefill',),
        )
    new_file.meta = meta
    return new_file


def get_previous_registration_data(regform, user, file_data=None):
    """Prefill custom fields from the user's most recent completed registration.

    For each active field with ``internal_name`` set, finds the user's last completed
    registration on any regform that also has a field with the same ``internal_name`` and
    ``input_type``, and returns its stored value.
    File and picture fields are handled by creating a new unclaimed File for prefill.

    Args:
        regform: The RegistrationForm being displayed
        user: The current user (may be None)
        file_data: Optional mutable dict to populate with file display metadata

    Returns:
        Dict mapping html_field_name to field values (with camelized keys)
    """
    if user is None:
        return {}

    custom_fields = [
        field for field in regform.active_fields
        if field.is_field and field.internal_name
    ]
    if not custom_fields:
        return {}

    field_pairs = [(f.internal_name, f.input_type) for f in custom_fields]
    excluded_ids = [f.id for f in custom_fields]

    rows = (
        db.session.query(RegistrationData, RegistrationFormItem.internal_name, RegistrationFormItem.input_type)
        .distinct(RegistrationFormItem.internal_name, RegistrationFormItem.input_type)
        .join(RegistrationData.field_data)
        .join(RegistrationFormFieldData.field)
        .join(RegistrationData.registration)
        .filter(
            tuple_(RegistrationFormItem.internal_name, RegistrationFormItem.input_type).in_(field_pairs),
            RegistrationFormItem.id.notin_(excluded_ids),
            RegistrationFormItem.is_enabled.is_(True),
            ~RegistrationFormItem.is_deleted,
            Registration.user_id == user.id,
            Registration.state == RegistrationState.complete,
            ~Registration.is_deleted,
        )
        .order_by(
            RegistrationFormItem.internal_name,
            RegistrationFormItem.input_type,
            Registration.submitted_dt.desc(),
        )  # Get the most recent registration for each field, triple ordering required
        .all()
    )
    data_by_key = {(internal_name, input_type): reg_data for reg_data, internal_name, input_type in rows}

    result = {}
    for field in custom_fields:
        reg_data = data_by_key.get((field.internal_name, field.input_type))

        if reg_data is None:
            continue

        if field.input_type in {'file', 'picture'}:
            # Files are stored in the storage backend, not in the data column.
            # Create a new unclaimed File that the frontend can reference via its UUID.
            prefill_file = _create_prefill_file(reg_data, field)
            if prefill_file:
                uuid_str = str(prefill_file.uuid)
                result[field.html_field_name] = uuid_str
                if file_data is not None and field.html_field_name not in file_data:
                    file_data[field.html_field_name] = {
                        'filename': reg_data.filename,
                        'size': reg_data.size,
                        'uuid': uuid_str,
                        'locator': reg_data.locator.registrant_file,
                    }
            continue

        if reg_data.data is None:
            continue

        value = reg_data.data

        if field.input_type in {'single_choice', 'multi_choice'}:
            valid_uuids = {
                c['id'] for c in (field.versioned_data or {}).get('choices', [])
                if c.get('is_enabled', True)
            }
            value = {uuid: slots for uuid, slots in value.items() if uuid in valid_uuids}
            if not value:
                value = field.field_impl.ui_default_value

        if isinstance(value, dict):
            value = camelize_keys(value)
        result[field.html_field_name] = value

    return result
