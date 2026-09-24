# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from flask import request, session
from marshmallow import fields
from werkzeug.exceptions import Forbidden

from indico.core.marshmallow import mm
from indico.modules.events.abstracts.models.email_logs import AbstractEmailLogEntry
from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.web.rh import json_errors

from indico_openapi.resources.abstracts import AbstractMixin
from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase
from indico_openapi.schemas import UserReferenceSchema


class AbstractEmailSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """Notification an event sent about an abstract, as it was sent.

    The notification log of an abstract is shown to whoever may judge it, so
    that is who this is served to.
    """

    class Meta:
        model = AbstractEmailLogEntry
        fields = (
            'id',
            'abstract_id',
            'email_template_id',
            'template_title',
            'sent_dt',
            'sent_by',
            'recipients',
            'subject',
            'body',
        )
        descriptions = {
            'id': 'Numeric identifier of the log entry, unique across the whole instance.',
            'abstract_id': 'Identifier of the abstract the email was about.',
            'email_template_id': 'Identifier of the template the email was built from, or `null` when the template '
            'was deleted.',
            'template_title': 'Name the template had when the email was sent, or `null` when it was not sent from one.',
            'sent_dt': 'Moment the email was sent, in UTC.',
            'sent_by': 'User whose action sent the email, or `null` when it was not sent by a person.',
            'recipients': 'Every address the email was sent to, in copy included.',
            'subject': 'Subject of the email, with the placeholders already filled in.',
            'body': 'Body of the email, with the placeholders already filled in.',
        }

    template_title = fields.String(attribute='data.template_name', allow_none=True, dump_default=None)
    sent_by = fields.Nested(UserReferenceSchema, attribute='user')


class AbstractEmailMixin(AbstractMixin):
    """The notification log of an abstract, served to whoever may judge it."""

    def _process_args(self):
        RHProtectedEventBase._process_args(self)
        self.abstract = self._abstract_query().filter_by(id=request.view_args['abstract_id']).first_or_404()

    def _check_access(self):
        RHProtectedEventBase._check_access(self)
        if not self.abstract.can_judge(session.user):
            raise Forbidden

    def _email_query(self):
        return AbstractEmailLogEntry.query.with_parent(self.abstract).order_by(
            AbstractEmailLogEntry.sent_dt, AbstractEmailLogEntry.id
        )


@json_errors
class RHAbstractEmail(AbstractEmailMixin, RHProtectedEventBase):
    def _process_args(self):
        AbstractEmailMixin._process_args(self)
        self.entry = (
            self._email_query().filter(AbstractEmailLogEntry.id == request.view_args['email_id']).first_or_404()
        )

    def _process_GET(self):
        return AbstractEmailSchema().jsonify(self.entry)


@json_errors
class RHAbstractEmailList(AbstractEmailMixin, RHListBase, RHProtectedEventBase):
    schema = AbstractEmailSchema

    def _query(self):
        return self._email_query()

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(
        rule='/events/<int:event_id>/abstracts/<int:abstract_id>/emails',
        name='abstract_emails',
        rh=RHAbstractEmailList,
        schema=AbstractEmailSchema,
        many=True,
        summary='List the notifications sent about an abstract',
        tag='Abstracts',
    ),
    Endpoint(
        rule='/events/<int:event_id>/abstracts/<int:abstract_id>/emails/<int:email_id>',
        name='abstract_email',
        rh=RHAbstractEmail,
        schema=AbstractEmailSchema,
        summary='Details of one notification sent about an abstract',
        tag='Abstracts',
    ),
]
