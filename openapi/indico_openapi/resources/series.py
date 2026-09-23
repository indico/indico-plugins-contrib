# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from flask import request, session
from marshmallow import fields
from werkzeug.exceptions import Forbidden

from indico.modules.events.models.series import EventSeries
from indico.modules.events.series.schemas import EventSeriesSchema as CoreEventSeriesSchema
from indico.web.rh import RHProtected, json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase


class EventSeriesSchema(DescribedFieldsMixin, CoreEventSeriesSchema):
    class Meta(CoreEventSeriesSchema.Meta):
        fields = ('id', 'event_ids', 'show_sequence_in_title', 'show_links', 'event_title_pattern')
        descriptions = {
            'id': 'Numeric identifier of the series, unique across the whole instance.',
            'event_ids': 'Identifiers of the events making up the series, in chronological order. Deleted events '
                         'are left out.',
            'show_sequence_in_title': 'Whether the position of an event in the series is shown in its title.',
            'show_links': 'Whether each event of the series links to the others.',
            'event_title_pattern': 'Pattern used to build the title of an event cloned from the series, with `{n}` '
                                   'standing for its position, or an empty string when there is none.',
        }

    event_ids = fields.Function(lambda series: [event.id for event in series.events])


class SeriesMixin:
    """Access checks shared by the event series endpoints.

    A series is managed by whoever manages every event in it, which is the rule
    the series management interface applies. Listing them serves only the ones
    the caller manages.
    """

    def _can_see(self, series):
        return series.can_manage(session.user)


@json_errors
class RHEventSeries(SeriesMixin, RHProtected):
    def _process_args(self):
        self.series = EventSeries.get_or_404(request.view_args['series_id'])

    def _check_access(self):
        RHProtected._check_access(self)
        if not self._can_see(self.series):
            raise Forbidden

    def _process_GET(self):
        return EventSeriesSchema().jsonify(self.series)


@json_errors
class RHEventSeriesList(SeriesMixin, RHListBase, RHProtected):
    schema = EventSeriesSchema

    def _query(self):
        return EventSeries.query.order_by(EventSeries.id)

    def _can_access(self, obj):
        return self._can_see(obj)


ENDPOINTS = [
    Endpoint(rule='/event-series', name='event_series_list', rh=RHEventSeriesList, schema=EventSeriesSchema,
             many=True, summary='List the event series the caller manages', tag='Event series'),
    Endpoint(rule='/event-series/<int:series_id>', name='event_series', rh=RHEventSeries, schema=EventSeriesSchema,
             summary='Details of one series of related events', tag='Event series'),
]
