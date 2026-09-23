# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from flask import request

from indico.core.db import db
from indico.modules.users.models.affiliations import Affiliation
from indico.web.rh import RHProtected, json_errors

from indico_openapi.resources.base import Endpoint, RHListBase
from indico_openapi.schemas import AffiliationSchema


class AffiliationMixin:
    """Query shared by the affiliation endpoints.

    An affiliation is published next to every person carrying it, and the
    interface lets anybody search the catalogue while filling in a name, so the
    catalogue is served to any authenticated caller. Deleted affiliations are
    never returned.
    """

    def _affiliation_query(self):
        return (Affiliation.query
                .filter(~Affiliation.is_deleted)
                .order_by(db.func.indico.indico_unaccent(db.func.lower(Affiliation.name)), Affiliation.id))


@json_errors
class RHAffiliation(AffiliationMixin, RHProtected):
    def _process_args(self):
        self.affiliation = (self._affiliation_query()
                            .filter(Affiliation.id == request.view_args['affiliation_id']).first_or_404())

    def _process_GET(self):
        return AffiliationSchema().jsonify(self.affiliation)


@json_errors
class RHAffiliationList(AffiliationMixin, RHListBase, RHProtected):
    schema = AffiliationSchema

    def _query(self):
        return self._affiliation_query()

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(rule='/affiliations', name='affiliations', rh=RHAffiliationList, schema=AffiliationSchema, many=True,
             summary='List the organisations people can be affiliated with', tag='Users'),
    Endpoint(rule='/affiliations/<int:affiliation_id>', name='affiliation', rh=RHAffiliation,
             schema=AffiliationSchema,
             summary='Details of one organisation people can be affiliated with', tag='Users'),
]
