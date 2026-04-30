# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

"""Tests for get_previous_registration_data.

Architecture
============
Each test creates a *source* registration form (with completed registrations)
and a *target* form (dummy_regform, where the user is about to register).
Fields on the two forms share the same ``internal_name`` + ``input_type`` pair
so the prefill logic can match them. The target field IDs are in the
``excluded_ids`` list, so the query falls back to the source form's data.
"""
from datetime import UTC, datetime, timedelta

import pytest

from indico.modules.events.registration.models.items import PersonalDataType
from indico.modules.events.registration.models.registrations import RegistrationState

from indico_registration_prefill.util import get_previous_registration_data


# ---------------------------------------------------------------------------
# Stable UUIDs used as choice IDs.  These pass marshmallow's fields.UUID()
# validation and are unchanged by camelize_keys (no underscores).
# ---------------------------------------------------------------------------
_FILE_PREFILL_SENTINEL = object()  # marker: field must be present and contain a UUID string

_UUID_A = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
_UUID_B = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
_UUID_C = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc'
_UUID_NO_ACCOMM = '11111111-1111-4111-8111-111111111111'
_UUID_ROOM = '22222222-2222-4222-8222-222222222222'

_SINGLE_CHOICES = [
    {'id': _UUID_A, 'caption': 'Option A', 'is_enabled': True, 'price': 0, 'places_limit': 0},
    {'id': _UUID_B, 'caption': 'Option B', 'is_enabled': True, 'price': 0, 'places_limit': 0},
]
_MULTI_CHOICES = [
    {'id': _UUID_A, 'caption': 'Option A', 'is_enabled': True, 'price': 0, 'places_limit': 0},
    {'id': _UUID_B, 'caption': 'Option B', 'is_enabled': True, 'price': 0, 'places_limit': 0},
]
_ACCOMM_CHOICES = [
    {'id': _UUID_NO_ACCOMM, 'caption': 'No Accommodation', 'is_enabled': True,
     'price': 0, 'places_limit': 0, 'is_no_accommodation': True},
    {'id': _UUID_ROOM, 'caption': 'Single Room', 'is_enabled': True,
     'price': 0, 'places_limit': 0, 'is_no_accommodation': False},
]
_ACCOMM_DATES = {
    'arrival': {'start_date': '2025-11-20', 'end_date': '2025-11-22'},
    'departure': {'start_date': '2025-11-22', 'end_date': '2025-11-24'},
}


def _all_field_specs():
    """Return a list of dicts describing every supported field type.

    Keys per entry:
    - internal_name : used as the matching key across forms
    - input_type    : the field's input_type string
    - field_kwargs  : extra kwargs forwarded to make_field / _fill_form_field_with_data
    - stored_data   : value written to RegistrationData.data on the source form
    - expected      : value expected in the prefill result dict (None = field must be absent)
    """
    return [
        # ── plain text fields ──────────────────────────────────────────────
        {
            'internal_name': 'my_text',
            'input_type': 'text',
            'field_kwargs': {},
            'stored_data': 'Hello World',
            'expected': 'Hello World',
        },
        {
            'internal_name': 'my_textarea',
            'input_type': 'textarea',
            'field_kwargs': {},
            'stored_data': 'Line 1\nLine 2',
            'expected': 'Line 1\nLine 2',
        },
        # ── numeric ───────────────────────────────────────────────────────
        {
            'internal_name': 'my_number',
            'input_type': 'number',
            'field_kwargs': {},
            'stored_data': 42,
            'expected': 42,
        },
        # ── boolean-ish ───────────────────────────────────────────────────
        {
            'internal_name': 'my_checkbox',
            'input_type': 'checkbox',
            'field_kwargs': {},
            'stored_data': True,
            'expected': True,
        },
        {
            'internal_name': 'my_bool',
            'input_type': 'bool',
            'field_kwargs': {},
            'stored_data': True,
            'expected': True,
        },
        # ── date ──────────────────────────────────────────────────────────
        {
            'internal_name': 'my_date',
            'input_type': 'date',
            'field_kwargs': {'date_format': '%d/%m/%Y'},
            'stored_data': '2024-06-15T00:00:00',
            'expected': '2024-06-15T00:00:00',
        },
        # ── contact ───────────────────────────────────────────────────────
        {
            'internal_name': 'my_phone',
            'input_type': 'phone',
            'field_kwargs': {},
            'stored_data': '+1-555-0100',
            'expected': '+1-555-0100',
        },
        {
            'internal_name': 'my_country',
            'input_type': 'country',
            'field_kwargs': {},
            'stored_data': 'US',
            'expected': 'US',
        },
        {
            'internal_name': 'my_email_addr',
            'input_type': 'email',
            'field_kwargs': {},
            'stored_data': 'user@example.com',
            'expected': 'user@example.com',
        },
        # ── choice fields ─────────────────────────────────────────────────
        # camelize_keys leaves UUID strings unchanged (no underscores)
        {
            'internal_name': 'my_single_choice',
            'input_type': 'single_choice',
            'field_kwargs': {
                'item_type': 'radiogroup',
                'choices': _SINGLE_CHOICES,
            },
            'stored_data': {_UUID_A: 1},
            'expected': {_UUID_A: 1},
        },
        {
            'internal_name': 'my_multi_choice',
            'input_type': 'multi_choice',
            'field_kwargs': {
                'with_extra_slots': False,
                'choices': _MULTI_CHOICES,
            },
            'stored_data': {_UUID_A: 1, _UUID_B: 1},
            'expected': {_UUID_A: 1, _UUID_B: 1},
        },
        # ── accommodation ─────────────────────────────────────────────────
        # Stored in snake_case; camelize_keys converts to camelCase on return.
        {
            'internal_name': 'my_accommodation',
            'input_type': 'accommodation',
            'field_kwargs': {'choices': _ACCOMM_CHOICES, **_ACCOMM_DATES},
            'stored_data': {
                'choice': _UUID_ROOM,
                'is_no_accommodation': False,
                'arrival_date': '2025-11-20',
                'departure_date': '2025-11-22',
            },
            'expected': {
                'choice': _UUID_ROOM,
                'isNoAccommodation': False,
                'arrivalDate': '2025-11-20',
                'departureDate': '2025-11-22',
            },
        },
        # ── accompanying persons ──────────────────────────────────────────
        # Stored as a list (not a dict), so camelize_keys is NOT applied;
        # the value is returned as-is.
        {
            'internal_name': 'my_accompanying',
            'input_type': 'accompanying_persons',
            'field_kwargs': {'max_persons': 5, 'persons_count_against_limit': False},
            'stored_data': [{'id': 'pers-001', 'firstName': 'Alice', 'lastName': 'Doe'}],
            'expected': [{'id': 'pers-001', 'firstName': 'Alice', 'lastName': 'Doe'}],
        },
        # ── file upload fields ────────────────────────────────────────────
        # Files are stored in the storage backend (data column is NULL).
        # get_previous_registration_data copies the file into a new unclaimed
        # File object and returns its UUID string as the prefill value.
        {
            'internal_name': 'my_file',
            'input_type': 'file',
            'field_kwargs': {},
            'stored_data': {'filename': 'cv.txt', 'content_type': 'text/plain', 'content': b'my cv'},
            'expected': _FILE_PREFILL_SENTINEL,
        },
        {
            'internal_name': 'my_picture',
            'input_type': 'picture',
            'field_kwargs': {},
            'stored_data': {'filename': 'photo.jpg', 'content_type': 'image/jpeg', 'content': b'jpeg data'},
            'expected': _FILE_PREFILL_SENTINEL,
        },
        # ── timetable / sessions ──────────────────────────────────────────
        # Stored as a list of session-block IDs.  Not a dict, so camelize_keys
        # is not applied; the list is returned unchanged.
        {
            'internal_name': 'my_sessions',
            'input_type': 'sessions',
            'field_kwargs': {},
            'stored_data': [101, 202],
            'expected': [101, 202],
        },
    ]


# ============================================================================
# Test class
# ============================================================================

@pytest.mark.usefixtures('db', 'request_context')
class TestGetPreviousRegistrationData:

    # ── basic guard tests ────────────────────────────────────────────────────
    def test_returns_empty_for_anonymous_user(self, dummy_regform):
        assert get_previous_registration_data(dummy_regform, None) == {}

    def test_returns_empty_when_no_fields_with_internal_name(self, dummy_regform, dummy_user):
        assert get_previous_registration_data(dummy_regform, dummy_user) == {}

    # ── happy path ───────────────────────────────────────────────────────────
    def test_happy_path_all_field_types(self, dummy_event, dummy_regform, dummy_user,
                                         create_regform, make_section, make_field, make_registration):
        """Every supported field type is prefilled from the most recent registration."""
        source_regform = create_regform(dummy_event, title='Source Form')
        source_section = make_section(source_regform, 'Source Section')
        target_section = make_section(dummy_regform, 'Target Section')
        source_fields = {}  # internal_name -> (field, stored_data)
        target_fields = {}  # internal_name -> (field, expected_value)

        for spec in _all_field_specs():
            iname = spec['internal_name']
            kwargs = spec['field_kwargs']
            src = make_field(source_section, iname, spec['input_type'], **kwargs)
            tgt = make_field(target_section, iname, spec['input_type'], **kwargs)
            source_fields[iname] = (src, spec['stored_data'])
            target_fields[iname] = (tgt, spec['expected'])

        # Build source registration (all fields, including file fields with data=None)
        field_values = dict(source_fields.values())
        make_registration(dummy_user, source_regform, field_values)
        result = get_previous_registration_data(dummy_regform, dummy_user)

        for iname, (tgt_field, expected) in target_fields.items():
            if expected is _FILE_PREFILL_SENTINEL:
                assert tgt_field.html_field_name in result, (
                    f'Field "{iname}" (type={tgt_field.input_type}) should be prefilled with a file UUID'
                )
                assert isinstance(result[tgt_field.html_field_name], str), (
                    f'Field "{iname}": expected a UUID string, got {result[tgt_field.html_field_name]!r}'
                )
            else:
                assert tgt_field.html_field_name in result, (
                    f'Field "{iname}" (type={tgt_field.input_type}) should be prefilled'
                )
                assert result[tgt_field.html_field_name] == expected, (
                    f'Field "{iname}": expected {expected!r}, '
                    f'got {result[tgt_field.html_field_name]!r}'
                )

    # ── choice field corner cases ────────────────────────────────────────────
    def test_disabled_choice_filtered_from_result(self, dummy_event, dummy_regform, dummy_user,
                                                   create_regform, make_section, make_field,
                                                   make_registration):
        """Choices that are disabled in the target form are removed from the prefilled value."""
        source_regform = create_regform(dummy_event, title='Source Form')
        src_section = make_section(source_regform, 'Source Section')
        tgt_section = make_section(dummy_regform, 'Target Section')
        src_field = make_field(src_section, 'diet', 'multi_choice',
                               with_extra_slots=False, choices=_MULTI_CHOICES)
        tgt_choices = [
            {'id': _UUID_A, 'caption': 'Option A', 'is_enabled': False, 'price': 0, 'places_limit': 0},
            {'id': _UUID_B, 'caption': 'Option B', 'is_enabled': True, 'price': 0, 'places_limit': 0},
        ]
        tgt_field = make_field(tgt_section, 'diet', 'multi_choice',
                               with_extra_slots=False, choices=tgt_choices)
        make_registration(dummy_user, source_regform, {src_field: {_UUID_A: 1, _UUID_B: 1}})
        result = get_previous_registration_data(dummy_regform, dummy_user)

        assert tgt_field.html_field_name in result
        assert result[tgt_field.html_field_name] == {_UUID_B: 1}

    def test_choice_absent_from_target_is_filtered(self, dummy_event, dummy_regform, dummy_user,
                                                    create_regform, make_section, make_field,
                                                    make_registration):
        """A previously selected choice that no longer exists in the target form is dropped."""
        source_regform = create_regform(dummy_event, title='Source Form')
        src_section = make_section(source_regform, 'Source Section')
        tgt_section = make_section(dummy_regform, 'Target Section')

        src_field = make_field(src_section, 'tier', 'single_choice',
                               item_type='radiogroup', choices=_SINGLE_CHOICES)
        tgt_choices = [
            {'id': _UUID_C, 'caption': 'Option C', 'is_enabled': True, 'price': 0, 'places_limit': 0},
        ]
        tgt_field = make_field(tgt_section, 'tier', 'single_choice',
                               item_type='radiogroup', choices=tgt_choices)
        make_registration(dummy_user, source_regform, {src_field: {_UUID_A: 1}})
        result = get_previous_registration_data(dummy_regform, dummy_user)
        value = result.get(tgt_field.html_field_name)

        assert value == {} or tgt_field.html_field_name not in result

    def test_all_choices_filtered_returns_default(self, dummy_event, dummy_regform, dummy_user,
                                                   create_regform, make_section, make_field,
                                                   make_registration):
        """When every previously selected choice is disabled in the target, the field's
        default value (empty dict for single_choice with no default item) is used.
        """
        source_regform = create_regform(dummy_event, title='Source Form')
        src_section = make_section(source_regform, 'Source Section')
        tgt_section = make_section(dummy_regform, 'Target Section')

        src_field = make_field(src_section, 'meal', 'single_choice',
                               item_type='radiogroup', choices=_SINGLE_CHOICES)
        tgt_choices = [
            {'id': _UUID_A, 'caption': 'Option A', 'is_enabled': False, 'price': 0, 'places_limit': 0},
            {'id': _UUID_B, 'caption': 'Option B', 'is_enabled': False, 'price': 0, 'places_limit': 0},
        ]
        tgt_field = make_field(tgt_section, 'meal', 'single_choice',
                               item_type='radiogroup', choices=tgt_choices)
        make_registration(dummy_user, source_regform, {src_field: {_UUID_A: 1}})
        result = get_previous_registration_data(dummy_regform, dummy_user)

        assert tgt_field.html_field_name in result
        assert result[tgt_field.html_field_name] == {}

    def test_different_choice_order_still_matches_by_uuid(self, dummy_event, dummy_regform,
                                                           dummy_user, create_regform,
                                                           make_section, make_field, make_registration):
        """Reordering choices in the target form does not affect UUID-based matching."""
        source_regform = create_regform(dummy_event, title='Source Form')
        src_section = make_section(source_regform, 'Source Section')
        tgt_section = make_section(dummy_regform, 'Target Section')

        src_field = make_field(src_section, 'transport', 'single_choice',
                               item_type='radiogroup', choices=_SINGLE_CHOICES)
        tgt_choices = list(reversed(_SINGLE_CHOICES))
        tgt_field = make_field(tgt_section, 'transport', 'single_choice',
                               item_type='radiogroup', choices=tgt_choices)
        make_registration(dummy_user, source_regform, {src_field: {_UUID_B: 1}})
        result = get_previous_registration_data(dummy_regform, dummy_user)

        assert tgt_field.html_field_name in result
        assert result[tgt_field.html_field_name] == {_UUID_B: 1}

    # ── file_data population ─────────────────────────────────────────────────
    def test_file_data_populated_for_picture_field(self, dummy_event, dummy_regform, dummy_user,
                                                    create_regform, make_section, make_field,
                                                    make_registration):
        """file_data is populated with display metadata for picture fields.

        The ``uuid`` in file_data must match the UUID returned in initial_values so
        the frontend PictureInput widget recognizes and displays the pre-filled image.
        """
        source_regform = create_regform(dummy_event, title='Source Form')
        src_section = make_section(source_regform, 'Source Section')
        tgt_section = make_section(dummy_regform, 'Target Section')
        src_field = make_field(src_section, 'headshot', 'picture')
        tgt_field = make_field(tgt_section, 'headshot', 'picture')
        make_registration(dummy_user, source_regform, {
            src_field: {'filename': 'photo.jpg', 'content_type': 'image/jpeg', 'content': b'jpeg data'},
        })
        file_data = {}
        result = get_previous_registration_data(dummy_regform, dummy_user, file_data=file_data)
        uuid_str = result[tgt_field.html_field_name]
        fd = file_data[tgt_field.html_field_name]

        assert fd['uuid'] == uuid_str
        assert fd['filename'] == 'photo.jpg'
        assert isinstance(fd['size'], int)
        assert isinstance(fd['locator'], dict)

    def test_file_data_populated_for_file_field(self, dummy_event, dummy_regform, dummy_user,
                                                 create_regform, make_section, make_field,
                                                 make_registration):
        """file_data is populated with display metadata for file fields."""
        source_regform = create_regform(dummy_event, title='Source Form')
        src_section = make_section(source_regform, 'Source Section')
        tgt_section = make_section(dummy_regform, 'Target Section')
        src_field = make_field(src_section, 'cv_doc', 'file')
        tgt_field = make_field(tgt_section, 'cv_doc', 'file')
        make_registration(dummy_user, source_regform, {
            src_field: {'filename': 'cv.txt', 'content_type': 'text/plain', 'content': b'my cv'},
        })
        file_data = {}
        result = get_previous_registration_data(dummy_regform, dummy_user, file_data=file_data)
        uuid_str = result[tgt_field.html_field_name]
        fd = file_data[tgt_field.html_field_name]

        assert fd['uuid'] == uuid_str
        assert fd['filename'] == 'cv.txt'
        assert isinstance(fd['locator'], dict)

    def test_file_data_not_populated_when_none(self, dummy_event, dummy_regform, dummy_user,
                                                create_regform, make_section, make_field,
                                                make_registration):
        """When file_data=None (default), no locator access is attempted."""
        source_regform = create_regform(dummy_event, title='Source Form')
        src_section = make_section(source_regform, 'Source Section')
        tgt_section = make_section(dummy_regform, 'Target Section')
        src_field = make_field(src_section, 'headshot', 'picture')
        tgt_field = make_field(tgt_section, 'headshot', 'picture')
        make_registration(dummy_user, source_regform, {
            src_field: {'filename': 'photo.jpg', 'content_type': 'image/jpeg', 'content': b'jpeg data'},
        })

        result = get_previous_registration_data(dummy_regform, dummy_user)
        assert tgt_field.html_field_name in result
        assert isinstance(result[tgt_field.html_field_name], str)

    # ── file, picture and sessions corner cases ──────────────────────────────
    def test_file_field_not_prefilled_when_no_upload(self, dummy_event, dummy_regform, dummy_user,
                                                      create_regform, make_section, make_field, make_registration):
        """A file field with no file stored (storage_file_id=None) is not prefilled."""
        source_regform = create_regform(dummy_event, title='Source Form')
        src_section = make_section(source_regform, 'Source Section')
        tgt_section = make_section(dummy_regform, 'Target Section')
        src_field = make_field(src_section, 'cv_file', 'file')
        tgt_field = make_field(tgt_section, 'cv_file', 'file')
        make_registration(dummy_user, source_regform, {src_field: None})
        result = get_previous_registration_data(dummy_regform, dummy_user)

        assert tgt_field.html_field_name not in result

    def test_picture_field_not_prefilled_when_no_upload(self, dummy_event, dummy_regform, dummy_user,
                                                         create_regform, make_section, make_field, make_registration):
        """A picture field with no file stored (storage_file_id=None) is not prefilled."""
        source_regform = create_regform(dummy_event, title='Source Form')
        src_section = make_section(source_regform, 'Source Section')
        tgt_section = make_section(dummy_regform, 'Target Section')
        src_field = make_field(src_section, 'headshot', 'picture')
        tgt_field = make_field(tgt_section, 'headshot', 'picture')
        make_registration(dummy_user, source_regform, {src_field: None})
        result = get_previous_registration_data(dummy_regform, dummy_user)

        assert tgt_field.html_field_name not in result

    def test_sessions_field_returns_block_id_list(self, dummy_event, dummy_regform, dummy_user,
                                                   create_regform, make_section, make_field,
                                                   make_registration):
        """Sessions fields store a list of session-block IDs.  The list is returned
        as-is (camelize_keys is only applied to dicts).
        """
        source_regform = create_regform(dummy_event, title='Source Form')
        src_section = make_section(source_regform, 'Source Section')
        tgt_section = make_section(dummy_regform, 'Target Section')
        src_field = make_field(src_section, 'timetable_sessions', 'sessions')
        tgt_field = make_field(tgt_section, 'timetable_sessions', 'sessions')
        session_ids = [101, 202, 303]
        make_registration(dummy_user, source_regform, {src_field: session_ids})
        result = get_previous_registration_data(dummy_regform, dummy_user)

        assert tgt_field.html_field_name in result
        assert result[tgt_field.html_field_name] == session_ids

    # ── most-recent registration selection ───────────────────────────────────
    def test_most_recent_registration_selected(self, dummy_event, dummy_regform, dummy_user,
                                                create_regform, make_section, make_field, make_registration):
        """When a user has registrations on multiple forms, the most recent value wins.

        A user can have at most one registration per form, so we use a separate source form per registration.
        The function selects across all forms, ordering by submitted_dt DESC.
        """
        now = datetime.now(UTC)
        tgt_section = make_section(dummy_regform, 'Target Section')
        tgt_field = make_field(tgt_section, 'company', 'text')

        for title, company, days_ago in [
            ('Old Form', 'Old Corp', 30),
            ('Recent Form', 'Latest Corp', 1),
            ('Middle Form', 'Middle Corp', 15),
        ]:
            src_rf = create_regform(dummy_event, title=title)
            src_sec = make_section(src_rf, 'Source Section')
            src_field = make_field(src_sec, 'company', 'text')
            make_registration(dummy_user, src_rf, {src_field: company},
                              submitted_dt=now - timedelta(days=days_ago))
        result = get_previous_registration_data(dummy_regform, dummy_user)

        assert result[tgt_field.html_field_name] == 'Latest Corp'

    # ── registration state ───────────────────────────────────────────────────
    def test_incomplete_registration_ignored(self, dummy_event, dummy_regform, dummy_user,
                                              create_regform, make_section, make_field, make_registration):
        """Only registrations in state=complete are used as prefill sources."""
        source_regform = create_regform(dummy_event, title='Source Form')
        src_section = make_section(source_regform, 'Source Section')
        tgt_section = make_section(dummy_regform, 'Target Section')
        src_field = make_field(src_section, 'company', 'text')
        tgt_field = make_field(tgt_section, 'company', 'text')
        make_registration(dummy_user, source_regform, {src_field: 'Pending Corp'},
                          state=RegistrationState.pending)
        result = get_previous_registration_data(dummy_regform, dummy_user)

        assert tgt_field.html_field_name not in result

    # ── field state on source form ───────────────────────────────────────────
    def test_deleted_source_field_not_used(self, dummy_event, dummy_regform, dummy_user,
                                            create_regform, make_section, make_field,
                                            make_registration, db):
        """If the source field is deleted, its data is not used for prefilling."""
        source_regform = create_regform(dummy_event, title='Source Form')
        src_section = make_section(source_regform, 'Source Section')
        tgt_section = make_section(dummy_regform, 'Target Section')
        src_field = make_field(src_section, 'affiliation', 'text')
        tgt_field = make_field(tgt_section, 'affiliation', 'text')
        make_registration(dummy_user, source_regform, {src_field: 'ACME Corp'})
        src_field.is_deleted = True
        db.session.flush()
        result = get_previous_registration_data(dummy_regform, dummy_user)

        assert tgt_field.html_field_name not in result

    def test_disabled_source_field_not_used(self, dummy_event, dummy_regform, dummy_user,
                                             create_regform, make_section, make_field,
                                             make_registration, db):
        """If the source field is disabled, its data is not used for prefilling."""
        source_regform = create_regform(dummy_event, title='Source Form')
        src_section = make_section(source_regform, 'Source Section')
        tgt_section = make_section(dummy_regform, 'Target Section')
        src_field = make_field(src_section, 'position', 'text')
        tgt_field = make_field(tgt_section, 'position', 'text')
        make_registration(dummy_user, source_regform, {src_field: 'Engineer'})
        src_field.is_enabled = False
        db.session.flush()
        result = get_previous_registration_data(dummy_regform, dummy_user)

        assert tgt_field.html_field_name not in result

    # ── matching logic ───────────────────────────────────────────────────────
    def test_current_regform_fields_not_used_as_source(self, dummy_regform, dummy_user,
                                                         make_section, make_field, make_registration):
        """Target form fields are excluded from the source query (self-prefill prevention).

        In practice a user can only register once per form, so their own data from the
        same form would never appear here. The test verifies the ``excluded_ids`` filter
        works correctly as a safety net.
        """
        section = make_section(dummy_regform, 'Section')
        field = make_field(section, 'company', 'text')
        make_registration(dummy_user, dummy_regform, {field: 'Self Corp'})
        result = get_previous_registration_data(dummy_regform, dummy_user)

        assert field.html_field_name not in result

    def test_field_type_mismatch_not_prefilled(self, dummy_event, dummy_regform, dummy_user,
                                                create_regform, make_section, make_field,
                                                make_registration):
        """Same internal_name but different input_type → no match."""
        source_regform = create_regform(dummy_event, title='Source Form')
        src_section = make_section(source_regform, 'Source Section')
        tgt_section = make_section(dummy_regform, 'Target Section')
        src_field = make_field(src_section, 'count', 'number')
        tgt_field = make_field(tgt_section, 'count', 'text')
        make_registration(dummy_user, source_regform, {src_field: 7})
        result = get_previous_registration_data(dummy_regform, dummy_user)

        assert tgt_field.html_field_name not in result

    # ── personal data (field_pd) fields ─────────────────────────────────────
    def test_personal_data_field_prefilled_from_previous_registration(
        self, dummy_event, dummy_regform, dummy_user,
        create_regform, make_pd_section, make_pd_field, make_registration
    ):
        """field_pd fields in the personaldata section are prefilled when internal_name and input_type match.

        Previously the filter used an exact type check (== field) which excluded field_pd,
        so personaldata-section fields with matching internal_name were silently skipped.
        """
        source_regform = create_regform(dummy_event, title='Source Form')
        src_pd_section = make_pd_section(source_regform)
        tgt_pd_section = make_pd_section(dummy_regform)
        src_field = make_pd_field(src_pd_section, PersonalDataType.affiliation)
        tgt_field = make_pd_field(tgt_pd_section, PersonalDataType.affiliation)

        make_registration(dummy_user, source_regform, {src_field: 'CERN'})
        result = get_previous_registration_data(dummy_regform, dummy_user)

        assert tgt_field.html_field_name in result
        assert result[tgt_field.html_field_name] == 'CERN'
