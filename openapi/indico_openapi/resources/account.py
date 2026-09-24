# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 Unconventional
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from flask import session
from marshmallow import fields
from werkzeug.exceptions import NotFound

from indico.core.marshmallow import mm
from indico.modules.users.models.emails import UserEmail
from indico.modules.users.models.export import DataExportOptions, DataExportRequest, DataExportRequestState
from indico.modules.users.models.users import NameFormat
from indico.web.rh import RHProtected, json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase


class UserSettingsSchema(DescribedFieldsMixin, mm.Schema):
    """Preferences the caller saved on their own profile."""

    class Meta:
        descriptions = {
            'lang': 'Language the interface is shown in, such as `en_GB`, or `null` to follow the browser.',
            'force_language': 'Whether that language is used even when an event asks for another one.',
            'timezone': 'Timezone dates are shown in, such as `Europe/Zurich`, or `null` to follow the instance.',
            'force_timezone': 'Whether that timezone is used even when an event is held in another one.',
            'show_future_events': 'Whether the category pages open with the upcoming events unfolded.',
            'show_past_events': 'Whether the category pages open with the past events unfolded.',
            'name_format': 'How names are written: `first_last`, `first_last_upper`, `last_first`, '
            '`last_first_upper`, `f_last`, `f_last_upper`, `last_f` or `last_f_upper`.',
            'use_previewer_pdf': 'Whether PDF files open in the Indico previewer instead of being downloaded.',
            'add_ical_alerts': 'Whether exported calendar entries carry an alarm.',
            'add_ical_alerts_mins': 'How many minutes before the event that alarm goes off.',
            'use_markdown_for_minutes': 'Whether minutes are written in Markdown instead of rich text.',
            'synced_fields': 'Profile fields the user keeps in sync with the account they log in with, '
            'or `null` when every field that can be synced is.',
            'suggest_categories': 'Whether the dashboard suggests categories to follow.',
            'mastodon_server_url': 'Mastodon server the sharing buttons point at, or `null` when none is set.',
            'mastodon_server_name': 'Name of that server, looked up from its URL.',
        }

    lang = fields.String(allow_none=True)
    force_language = fields.Boolean()
    timezone = fields.String(allow_none=True)
    force_timezone = fields.Boolean()
    show_future_events = fields.Boolean()
    show_past_events = fields.Boolean()
    name_format = fields.Enum(NameFormat)
    use_previewer_pdf = fields.Boolean()
    add_ical_alerts = fields.Boolean()
    add_ical_alerts_mins = fields.Integer()
    use_markdown_for_minutes = fields.Boolean()
    synced_fields = fields.List(fields.String(), allow_none=True)
    suggest_categories = fields.Boolean()
    mastodon_server_url = fields.String(allow_none=True)
    mastodon_server_name = fields.String(allow_none=True)


class UserEmailSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """Email address the caller receives Indico mail at."""

    class Meta:
        model = UserEmail
        fields = ('email', 'is_primary')
        descriptions = {
            'email': 'The address itself.',
            'is_primary': 'Whether this is the address Indico writes to and shows on the profile.',
        }


class DataExportRequestSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """Archive of their own data the caller asked Indico to build."""

    class Meta:
        model = DataExportRequest
        fields = ('state', 'requested_dt', 'selected_options', 'include_files', 'max_size_exceeded', 'url')
        descriptions = {
            'state': 'Where the export stands: `running`, `success`, `failed` or `expired`.',
            'requested_dt': 'When the export was asked for, in UTC.',
            'selected_options': 'Areas of the account the export covers, such as `personal_data` or `registrations`.',
            'include_files': 'Whether the archive also carries the files attached to those areas.',
            'max_size_exceeded': 'Whether the archive was cut short because it grew past the configured limit.',
            'url': 'URL the archive is downloaded from, or `null` while there is no file to download.',
        }

    state = fields.Enum(DataExportRequestState)
    selected_options = fields.List(fields.Enum(DataExportOptions))
    url = fields.String(allow_none=True)


@json_errors
class RHUserSettings(RHProtected):
    """Preferences of the caller.

    The preferences page reads and writes them for one account at a time, so
    the endpoint answers with the settings of whoever holds the token.
    """

    def _process_GET(self):
        return UserSettingsSchema().jsonify(session.user.settings.get_all())


@json_errors
class RHUserEmailList(RHListBase, RHProtected):
    schema = UserEmailSchema

    def _query(self):
        return UserEmail.query.filter_by(user_id=session.user.id, is_user_deleted=False).order_by(
            UserEmail.is_primary.desc(), UserEmail.email
        )

    def _can_access(self, obj):
        return True


@json_errors
class RHDataExportRequest(RHProtected):
    def _process_GET(self):
        if not (export_request := session.user.data_export_request):
            raise NotFound
        return DataExportRequestSchema().jsonify(export_request)


ENDPOINTS = [
    Endpoint(
        rule='/users/me/settings',
        name='user_settings',
        rh=RHUserSettings,
        schema=UserSettingsSchema,
        summary='Preferences of the authenticated user',
        tag='Personal data',
    ),
    Endpoint(
        rule='/users/me/emails',
        name='user_emails',
        rh=RHUserEmailList,
        schema=UserEmailSchema,
        many=True,
        summary='List the email addresses of the authenticated user',
        tag='Personal data',
    ),
    Endpoint(
        rule='/users/me/data-export',
        name='user_data_export',
        rh=RHDataExportRequest,
        schema=DataExportRequestSchema,
        summary='Data export the authenticated user requested',
        tag='Personal data',
    ),
]
