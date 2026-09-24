# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from marshmallow import fields

from indico.core.marshmallow import mm
from indico.modules.events.features.util import get_disallowed_features, get_enabled_features, get_feature_definitions
from indico.modules.events.management.controllers import RHManageEventBase
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, jsonify_results


class EventFeatureSchema(DescribedFieldsMixin, mm.Schema):
    """One part of Indico the organisers can turn on for their event.

    Core has no schema for this: the management page builds a form out of the
    feature definitions. What a feature depends on is not served either, for the
    same reason the page does not show it: enabling one pulls in whatever it
    needs anyway.
    """

    class Meta:
        descriptions = {
            'name': 'Identifier of the feature, such as `registration`.',
            'title': 'Name of the feature, in the language of the caller.',
            'description': 'What the feature gives the organisers, in the language of the caller.',
            'enabled': 'Whether the feature is turned on for this event.',
        }

    name = fields.String()
    title = fields.String()
    description = fields.String()
    enabled = fields.Boolean()


def _feature_data(feature, enabled):
    return {
        'name': feature.name,
        'title': feature.friendly_name,
        'description': feature.description,
        'enabled': feature.name in enabled,
    }


@json_errors
class RHEventFeatures(RHManageEventBase):
    def _process_GET(self):
        disallowed = get_disallowed_features(self.event)
        enabled = get_enabled_features(self.event)
        features = [
            _feature_data(feature, enabled)
            for feature in sorted(get_feature_definitions().values(), key=lambda f: str(f.friendly_name))
            if feature.name not in disallowed
        ]
        return jsonify_results(EventFeatureSchema(many=True), features)


ENDPOINTS = [
    Endpoint(
        rule='/events/<int:event_id>/features',
        name='features',
        rh=RHEventFeatures,
        schema=EventFeatureSchema,
        many=True,
        summary='List the features available to an event',
        tag='Features',
    ),
]
