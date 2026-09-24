# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from flask import request
from marshmallow import fields

from indico.core.marshmallow import mm
from indico.modules.events.management.controllers import RHManageEventBase
from indico.modules.events.static.models.static import StaticSite, StaticSiteState
from indico.web.flask.util import url_for
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase
from indico_openapi.schemas import MemberSchema


def _download_url(site):
    # the page only offers the link once the build succeeded, and the download 404s otherwise
    if site.state != StaticSiteState.success:
        return None
    return url_for('static_site.download', site, _external=True)


class OfflineCopySchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """Offline copy of an event: a build job whose result is the event as static HTML.

    Core has no schema for one because the management page renders the jobs
    straight from the model. The stored file is left out: it is an internal
    storage path the caller cannot act on, and `download_url` is what the
    interface offers instead.
    """

    class Meta:
        model = StaticSite
        fields = ('id', 'event_id', 'state', 'requested_dt', 'creator', 'download_url')
        descriptions = {
            'id': 'Numeric identifier of the offline copy, unique across the whole instance.',
            'event_id': 'Identifier of the event the copy was requested for.',
            'state': 'Where the build stands: `pending`, `running`, `success`, `failed` or `expired`.',
            'requested_dt': 'Moment the copy was requested, in UTC.',
            'creator': 'User who requested the copy.',
            'download_url': 'Absolute URL the ZIP file is downloaded from, or `null` unless the build succeeded.',
        }

    state = fields.Enum(StaticSiteState)
    creator = fields.Nested(MemberSchema)
    download_url = fields.Function(_download_url)


class OfflineCopyMixin:
    """Access checks shared by the offline copy endpoints.

    An offline copy holds the whole event as it is rendered for a manager, so
    both the page listing the copies and the download itself are restricted to
    event managers.
    """

    def _site_query(self):
        return StaticSite.query.with_parent(self.event).order_by(StaticSite.requested_dt.desc(), StaticSite.id.desc())


@json_errors
class RHOfflineCopy(OfflineCopyMixin, RHManageEventBase):
    def _process_args(self):
        RHManageEventBase._process_args(self)
        self.site = self._site_query().filter(StaticSite.id == request.view_args['site_id']).first_or_404()

    def _process_GET(self):
        return OfflineCopySchema().jsonify(self.site)


@json_errors
class RHOfflineCopyList(OfflineCopyMixin, RHListBase, RHManageEventBase):
    schema = OfflineCopySchema

    def _query(self):
        return self._site_query()

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(
        rule='/events/<int:event_id>/offline-copies',
        name='offline_copies',
        rh=RHOfflineCopyList,
        schema=OfflineCopySchema,
        many=True,
        summary='List the offline copies of an event',
        tag='Offline copies',
    ),
    Endpoint(
        rule='/events/<int:event_id>/offline-copies/<int:site_id>',
        name='offline_copy',
        rh=RHOfflineCopy,
        schema=OfflineCopySchema,
        summary='Details of one offline copy of an event',
        tag='Offline copies',
    ),
]
