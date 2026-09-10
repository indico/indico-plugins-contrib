# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from flask import request, session
from marshmallow import fields
from werkzeug.exceptions import Forbidden

from indico.core.db import db
from indico.core.marshmallow import mm
from indico.modules.events.agreements.models.agreements import Agreement, AgreementState
from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, ListArgs, RHListBase


class AgreementSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """Agreement an event asked somebody to sign.

    Core has no schema for agreements because the management interface renders
    them from the model, so this one is defined here. The signing token is left
    out on purpose: it lets anybody holding it answer on behalf of the person.
    """

    class Meta:
        model = Agreement
        fields = ('id', 'event_id', 'type', 'identifier', 'person_name', 'person_email', 'user_id', 'state',
                  'timestamp', 'signed_dt', 'reason', 'attachment_filename', 'data')
        descriptions = {
            'id': 'Numeric identifier of the agreement, unique across the whole instance.',
            'event_id': 'Identifier of the event the agreement was requested for.',
            'type': 'Name of the agreement definition the request came from, such as `cern-speaker-release`. '
                    'Definitions are provided by plugins.',
            'identifier': 'Identifier of the person within the event and the agreement type, as built by the '
                          'definition.',
            'person_name': 'Full name of the person who was asked to sign.',
            'person_email': 'Email address the request was sent to, or `null` when the definition provided none.',
            'user_id': 'Identifier of the Indico account of the signer, or `null` when they have none.',
            'state': 'Where the request stands: `pending`, `accepted`, `rejected`, `accepted_on_behalf` or '
                     '`rejected_on_behalf`, the last two meaning a manager answered for the person.',
            'timestamp': 'Moment the request was created, in UTC.',
            'signed_dt': 'Moment the person answered, in UTC, or `null` while the request is pending.',
            'reason': 'Explanation the signer gave along with their answer, or `null` when they gave none.',
            'attachment_filename': 'Name of the file the signer attached, or `null` when there is none.',
            'data': 'Extra values the agreement definition stored with the request, or `null` when it stored none.',
        }

    state = fields.Enum(AgreementState)
    data = fields.Raw()


class AgreementListArgs(ListArgs):
    agreement_type = fields.String(data_key='type', load_default=None,
                                   metadata={'description': 'Only list the agreements of this definition, such as '
                                                            '`cern-speaker-release`.'})


class AgreementMixin:
    """Access checks shared by the agreement endpoints.

    Agreements are only visible to the managers of the event, which is also what
    the legacy export API requires. The people asked to sign reach their own
    agreement through the link they were emailed, not through this API.
    """

    def _check_access(self):
        RHProtectedEventBase._check_access(self)
        if not self.event.can_manage(session.user):
            raise Forbidden

    def _agreement_query(self):
        return (Agreement.query.with_parent(self.event)
                .order_by(db.func.lower(Agreement.person_name), Agreement.id))


@json_errors
class RHAgreement(AgreementMixin, RHProtectedEventBase):
    def _process_args(self):
        RHProtectedEventBase._process_args(self)
        self.agreement = (self._agreement_query()
                          .filter(Agreement.id == request.view_args['agreement_id']).first_or_404())

    def _process_GET(self):
        return AgreementSchema().jsonify(self.agreement)


@json_errors
class RHAgreementList(AgreementMixin, RHListBase, RHProtectedEventBase):
    args_schema = AgreementListArgs
    schema = AgreementSchema

    def _query(self, agreement_type):
        query = self._agreement_query()
        if agreement_type is not None:
            query = query.filter(Agreement.type == agreement_type)
        return query

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(rule='/events/<int:event_id>/agreements', name='agreements', rh=RHAgreementList, schema=AgreementSchema,
             many=True, summary='List the agreements an event asked for', tag='Agreements'),
    Endpoint(rule='/events/<int:event_id>/agreements/<int:agreement_id>', name='agreement', rh=RHAgreement,
             schema=AgreementSchema, summary='Agreement details', tag='Agreements'),
]
