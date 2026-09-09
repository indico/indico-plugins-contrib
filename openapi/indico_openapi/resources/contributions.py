# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from operator import attrgetter

from flask import request, session
from marshmallow import fields
from werkzeug.exceptions import Forbidden, NotFound

from indico.modules.events.contributions import contribution_settings
from indico.modules.events.contributions.models.contributions import Contribution
from indico.modules.events.contributions.schemas import FullContributionSchema
from indico.modules.events.contributions.util import has_contributions_with_user_as_submitter
from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.modules.events.sessions.schemas import BasicSessionSchema, SessionBlockSchema
from indico.util.i18n import _
from indico.util.marshmallow import SortedList
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase
from indico_openapi.schemas import (
    ContributionPersonSchema,
    ContributionTypeReferenceSchema,
    CustomFieldValueSchema,
    TrackReferenceSchema,
)


class SessionReferenceSchema(DescribedFieldsMixin, BasicSessionSchema):
    class Meta(BasicSessionSchema.Meta):
        fields = ('id', 'title', 'friendly_id', 'code')
        descriptions = {
            'id': 'Numeric identifier of the session, unique across the whole instance.',
            'title': 'Title of the session.',
            'friendly_id': 'Number shown to users, unique within the event.',
            'code': 'Programme code assigned to the session.',
        }


class SessionBlockReferenceSchema(DescribedFieldsMixin, SessionBlockSchema):
    class Meta(SessionBlockSchema.Meta):
        fields = ('id', 'title', 'code')
        descriptions = {
            'id': 'Numeric identifier of the session block.',
            'title': 'Title of the block, empty when it takes the title of its session.',
            'code': 'Programme code assigned to the block.',
        }


class ContributionSchema(DescribedFieldsMixin, FullContributionSchema):
    class Meta(FullContributionSchema.Meta):
        descriptions = {
            'id': 'Numeric identifier of the contribution, unique across the whole instance.',
            'title': 'Title of the contribution.',
            'description': 'Description of the contribution, as HTML.',
            'friendly_id': 'Number shown to users, unique within the event and stable once assigned.',
            'code': 'Programme code assigned to the contribution.',
            'abstract_id': 'Identifier of the abstract the contribution was created from, if any.',
            'board_number': 'Board number assigned to the contribution in a poster session.',
            'keywords': 'Keywords assigned to the contribution.',
            'venue_name': 'Name of the venue, such as `CERN`.',
            'room_name': 'Name of the room, such as `500/1-001`.',
            'address': 'Postal address of the venue.',
            'inherit_location': 'Whether the location is taken from the session or event holding it.',
            'start_dt': 'Start of the contribution, in UTC, or `null` if it is not scheduled.',
            'end_dt': 'End of the contribution, in UTC, or `null` if it is not scheduled.',
            'duration': 'Length of the contribution, in seconds.',
            'session': 'Session the contribution belongs to, if any.',
            'session_block': 'Session block the contribution is scheduled in, if any.',
            'track': 'Track the contribution belongs to, if any.',
            'type': 'Contribution type, such as `Poster` or `Oral`.',
            'custom_fields': 'Values of the custom fields defined by the event, without the ones '
                             'restricted to managers.',
            'persons': 'Speakers and authors, in display order. Email, phone and address are only '
                       'present for users who can manage the contribution.',
        }

    session = fields.Nested(SessionReferenceSchema)
    session_block = fields.Nested(SessionBlockReferenceSchema)
    track = fields.Nested(TrackReferenceSchema)
    type = fields.Nested(ContributionTypeReferenceSchema)
    custom_fields = fields.List(fields.Nested(CustomFieldValueSchema), attribute='field_values')
    persons = SortedList(fields.Nested(ContributionPersonSchema), attribute='person_links',
                         sort_key=attrgetter('display_order_key'))


class ContributionMixin:
    """Access checks shared by the contribution endpoints.

    Contributions are hidden while the event has not published them, which is a
    separate gate from the protection mode.
    """

    def _can_view_unpublished(self):
        return (self.event.can_manage(session.user, permission='contributions') or
                has_contributions_with_user_as_submitter(self.event, session.user))

    def _check_published(self):
        if not contribution_settings.get(self.event, 'published') and not self._can_view_unpublished():
            raise NotFound(_('The contributions of this event have not been published yet.'))

    def _schema(self, **kwargs):
        can_manage = self.event.can_manage(session.user, permission='contributions')
        return ContributionSchema(context={'hide_restricted_data': not can_manage,
                                           'user_can_manage': can_manage,
                                           'user_owns_abstract': False}, **kwargs)


@json_errors
class RHContribution(ContributionMixin, RHProtectedEventBase):
    def _process_args(self):
        RHProtectedEventBase._process_args(self)
        self.contrib = (Contribution.query.with_parent(self.event)
                        .filter_by(id=request.view_args['contrib_id'], is_deleted=False)
                        .first_or_404())

    def _check_access(self):
        RHProtectedEventBase._check_access(self)
        if not self.contrib.can_access(session.user):
            raise Forbidden
        self._check_published()

    def _process_GET(self):
        return self._schema().jsonify(self.contrib)


@json_errors
class RHContributionList(ContributionMixin, RHListBase, RHProtectedEventBase):
    schema = ContributionSchema

    def _check_access(self):
        RHProtectedEventBase._check_access(self)
        self._check_published()

    def _query(self):
        return (Contribution.query.with_parent(self.event)
                .filter(~Contribution.is_deleted)
                .order_by(Contribution.friendly_id))

    def _dump_schema(self):
        return self._schema(many=True)


ENDPOINTS = [
    Endpoint(rule='/events/<int:event_id>/contributions', name='contributions', rh=RHContributionList,
             schema=ContributionSchema, many=True, summary='List the contributions of an event',
             tag='Contributions'),
    Endpoint(rule='/events/<int:event_id>/contributions/<int:contrib_id>', name='contribution', rh=RHContribution,
             schema=ContributionSchema, summary='Contribution details', tag='Contributions'),
]
