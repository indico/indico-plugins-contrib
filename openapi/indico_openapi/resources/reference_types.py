# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from flask import request

from indico.core.db import db
from indico.core.marshmallow import mm
from indico.modules.events.models.references import ReferenceType
from indico.web.rh import RHProtected, json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase


class ReferenceTypeSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """System an event, contribution or subcontribution can carry an identifier of, such as a DOI."""

    class Meta:
        model = ReferenceType
        fields = ('id', 'name', 'scheme', 'url_template')
        descriptions = {
            'id': 'Numeric identifier of the reference type, unique across the whole instance.',
            'name': 'Name of the system the identifiers belong to, such as `DOI`.',
            'scheme': 'URN scheme the identifiers are built with, or an empty string when the system has none.',
            'url_template': 'Template a link to an entry is built from, with `{value}` standing for the identifier, '
            'or an empty string when the system has no URL.',
        }


class ReferenceTypeMixin:
    """Query shared by the reference type endpoints.

    The identifiers themselves are published next to the objects carrying them,
    so the systems they point at are not restricted either.
    """

    def _reference_type_query(self):
        return ReferenceType.query.order_by(db.func.lower(ReferenceType.name), ReferenceType.id)


@json_errors
class RHReferenceType(ReferenceTypeMixin, RHProtected):
    def _process_args(self):
        self.reference_type = (
            self
            ._reference_type_query()
            .filter(ReferenceType.id == request.view_args['reference_type_id'])
            .first_or_404()
        )

    def _process_GET(self):
        return ReferenceTypeSchema().jsonify(self.reference_type)


@json_errors
class RHReferenceTypeList(ReferenceTypeMixin, RHListBase, RHProtected):
    schema = ReferenceTypeSchema

    def _query(self):
        return self._reference_type_query()

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(
        rule='/reference-types',
        name='reference_types',
        rh=RHReferenceTypeList,
        schema=ReferenceTypeSchema,
        many=True,
        summary='List the systems external identifiers point at',
        tag='Reference types',
    ),
    Endpoint(
        rule='/reference-types/<int:reference_type_id>',
        name='reference_type',
        rh=RHReferenceType,
        schema=ReferenceTypeSchema,
        summary='Details of one system external identifiers point at',
        tag='Reference types',
    ),
]
