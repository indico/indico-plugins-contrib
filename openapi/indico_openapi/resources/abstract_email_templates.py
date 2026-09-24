# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 Unconventional
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from flask import request

from indico.core.marshmallow import mm
from indico.modules.events.abstracts.models.email_templates import AbstractEmailTemplate
from indico.modules.events.management.controllers import RHManageEventBase
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase


class AbstractEmailTemplateSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """Email an event sends automatically when an abstract reaches a given state.

    The templates are written and read on the management page of the call for
    abstracts, so they are served to the abstract managers alone.
    """

    class Meta:
        model = AbstractEmailTemplate
        fields = (
            'id',
            'event_id',
            'position',
            'title',
            'subject',
            'body',
            'reply_to_address',
            'extra_cc_emails',
            'include_submitter',
            'include_authors',
            'include_coauthors',
            'stop_on_match',
            'rules',
        )
        descriptions = {
            'id': 'Numeric identifier of the template, unique across the whole instance.',
            'event_id': 'Identifier of the event the template belongs to.',
            'position': 'Place of the template among the others, starting at 1. Templates are checked in order.',
            'title': 'Name of the template, as the management page lists it.',
            'subject': 'Subject of the email, with the placeholders left in.',
            'body': 'Body of the email, with the placeholders left in.',
            'reply_to_address': 'Address replies are sent to, or an empty string to use the one of the event.',
            'extra_cc_emails': 'Addresses put in copy on top of the people the template includes.',
            'include_submitter': 'Whether the submitter of the abstract is a recipient.',
            'include_authors': 'Whether the primary authors are recipients.',
            'include_coauthors': 'Whether the co-authors are put in copy.',
            'stop_on_match': 'Whether a match stops the templates after this one from being checked.',
            'rules': 'Conditions an abstract has to meet for the email to be sent, as stored: each rule is an '
            'object keyed by condition (`state`, `track`, `contribution_type`) whose values are the '
            'identifiers that match, and any rule matching is enough.',
        }


class AbstractEmailTemplateMixin:
    EVENT_FEATURE = 'abstracts'
    PERMISSION = 'abstracts'

    def _template_query(self):
        return AbstractEmailTemplate.query.with_parent(self.event).order_by(
            AbstractEmailTemplate.position, AbstractEmailTemplate.id
        )


@json_errors
class RHAbstractEmailTemplate(AbstractEmailTemplateMixin, RHManageEventBase):
    def _process_args(self):
        RHManageEventBase._process_args(self)
        self.template = (
            self._template_query().filter(AbstractEmailTemplate.id == request.view_args['template_id']).first_or_404()
        )

    def _process_GET(self):
        return AbstractEmailTemplateSchema().jsonify(self.template)


@json_errors
class RHAbstractEmailTemplateList(AbstractEmailTemplateMixin, RHListBase, RHManageEventBase):
    schema = AbstractEmailTemplateSchema

    def _query(self):
        return self._template_query()

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(
        rule='/events/<int:event_id>/abstract-email-templates',
        name='abstract_email_templates',
        rh=RHAbstractEmailTemplateList,
        schema=AbstractEmailTemplateSchema,
        many=True,
        summary='List the notification templates of a call for abstracts',
        tag='Abstracts',
    ),
    Endpoint(
        rule='/events/<int:event_id>/abstract-email-templates/<int:template_id>',
        name='abstract_email_template',
        rh=RHAbstractEmailTemplate,
        schema=AbstractEmailTemplateSchema,
        summary='Details of one notification template of a call for abstracts',
        tag='Abstracts',
    ),
]
