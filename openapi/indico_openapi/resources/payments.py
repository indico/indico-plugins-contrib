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
from indico.modules.events.payment.models.transactions import PaymentTransaction, TransactionStatus
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.registrations import Registration
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, ListArgs, RHListBase


class PaymentSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """Payment a registrant made, as the payment provider reported it.

    Core has no schema for transactions because the management interface renders
    them from the model. The answer of the provider is left out: its shape is
    specific to each payment plugin, so there is nothing to document, and it
    carries whatever the provider chose to send back about the payer.
    """

    class Meta:
        model = PaymentTransaction
        fields = ('id', 'registration_id', 'status', 'amount', 'currency', 'provider', 'timestamp')
        descriptions = {
            'id': 'Numeric identifier of the payment, unique across the whole instance.',
            'registration_id': 'Identifier of the registration the payment is for.',
            'status': 'Where the payment stands: `successful`, `pending`, `failed`, `cancelled` or `rejected`.',
            'amount': 'Amount the registrant was charged, as a decimal string.',
            'currency': 'ISO 4217 code of the currency the amount is expressed in, such as `EUR`.',
            'provider': 'Name of the payment plugin that handled the payment, or `_manual` when a manager '
                        'recorded it by hand.',
            'timestamp': 'Moment the payment was recorded, in UTC.',
        }

    status = fields.Enum(TransactionStatus)
    amount = fields.Decimal(as_string=True)


class PaymentListArgs(ListArgs):
    registration_id = fields.Integer(load_default=None,
                                     metadata={'description': 'Only list the payments of this registration.'})
    status = fields.Enum(TransactionStatus, load_default=None,
                         metadata={'description': 'Only list the payments in this state.'})


class PaymentMixin:
    """Access checks shared by the payment endpoints.

    A payment says which provider a registrant paid through and what they were
    charged, which the interface only shows on the management page of the
    registration. Registrants see whether their own registration is paid, not
    the payment behind it, so that is all this API serves them as well, through
    the registration itself.
    """

    EVENT_FEATURE = 'registration'
    PERMISSION = 'registration'

    def _payment_query(self):
        return (PaymentTransaction.query
                .join(PaymentTransaction.registration)
                .join(Registration.registration_form)
                .filter(Registration.event_id == self.event.id,
                        ~Registration.is_deleted,
                        ~RegistrationForm.is_deleted)
                .order_by(PaymentTransaction.timestamp.desc(), PaymentTransaction.id.desc()))


@json_errors
class RHPayment(PaymentMixin, RHManageEventBase):
    def _process_args(self):
        RHManageEventBase._process_args(self)
        self.payment = (self._payment_query()
                        .filter(PaymentTransaction.id == request.view_args['payment_id']).first_or_404())

    def _process_GET(self):
        return PaymentSchema().jsonify(self.payment)


@json_errors
class RHPaymentList(PaymentMixin, RHListBase, RHManageEventBase):
    args_schema = PaymentListArgs
    schema = PaymentSchema

    def _query(self, registration_id, status):
        query = self._payment_query()
        if registration_id is not None:
            query = query.filter(PaymentTransaction.registration_id == registration_id)
        if status is not None:
            query = query.filter(PaymentTransaction.status == status)
        return query

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(rule='/events/<int:event_id>/payments', name='payments', rh=RHPaymentList, schema=PaymentSchema,
             many=True, summary='List the payments of an event', tag='Payments'),
    Endpoint(rule='/events/<int:event_id>/payments/<int:payment_id>', name='payment', rh=RHPayment,
             schema=PaymentSchema, summary='Details of one payment of an event', tag='Payments'),
]
