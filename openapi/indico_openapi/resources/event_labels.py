# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 Unconventional
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from flask import request

from indico.core.db import db
from indico.core.marshmallow import mm
from indico.modules.events.models.labels import EventLabel
from indico.web.rh import RHProtected, json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase


class LabelSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """Label an event can be marked with, as the administrators of the instance defined it."""

    class Meta:
        model = EventLabel
        fields = ('id', 'title', 'color', 'is_event_not_happening')
        descriptions = {
            'id': 'Numeric identifier of the label, unique across the whole instance.',
            'title': 'Text of the label, such as `Cancelled` or `Postponed`.',
            'color': 'Colour the label is shown in, as a colour name such as `red`.',
            'is_event_not_happening': 'Whether the label means the event will not take place as announced.',
        }


class EventLabelMixin:
    """Query shared by the event label endpoints.

    A label is published on the page of every event carrying it, so the
    catalogue is served to any authenticated caller.
    """

    def _label_query(self):
        return EventLabel.query.order_by(db.func.lower(EventLabel.title), EventLabel.id)


@json_errors
class RHEventLabel(EventLabelMixin, RHProtected):
    def _process_args(self):
        self.label = self._label_query().filter(EventLabel.id == request.view_args['event_label_id']).first_or_404()

    def _process_GET(self):
        return LabelSchema().jsonify(self.label)


@json_errors
class RHEventLabelList(EventLabelMixin, RHListBase, RHProtected):
    schema = LabelSchema

    def _query(self):
        return self._label_query()

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(
        rule='/event-labels',
        name='event_labels',
        rh=RHEventLabelList,
        schema=LabelSchema,
        many=True,
        summary='List the labels an event can be marked with',
        tag='Events',
    ),
    Endpoint(
        rule='/event-labels/<int:event_label_id>',
        name='event_label',
        rh=RHEventLabel,
        schema=LabelSchema,
        summary='Details of one label an event can be marked with',
        tag='Events',
    ),
]
