# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from flask import request
from marshmallow import fields

from indico.core.db import db
from indico.core.marshmallow import mm
from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.modules.events.papers.models.templates import PaperTemplate
from indico.web.flask.util import url_for
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase


class PaperTemplateSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """File the organisers ask authors to write their paper from.

    The call for papers page lists the templates to whoever can see it, so
    they are served to whoever can see the event.
    """

    class Meta:
        model = PaperTemplate
        fields = ('id', 'event_id', 'name', 'description', 'filename', 'content_type', 'size', 'download_url')
        descriptions = {
            'id': 'Numeric identifier of the template, unique across the whole instance.',
            'event_id': 'Identifier of the event offering the template.',
            'name': 'Name of the template as the call for papers page shows it.',
            'description': 'What the template is for, as plain text.',
            'filename': 'Name of the file as uploaded.',
            'content_type': 'MIME type of the file, such as `application/x-tex`.',
            'size': 'Size of the file, in bytes.',
            'download_url': 'URL the file is downloaded from, relative to the Indico instance.',
        }

    download_url = fields.Function(lambda template: url_for('papers.download_template', template))


class PaperTemplateMixin:
    EVENT_FEATURE = 'papers'

    def _template_query(self):
        return (PaperTemplate.query.with_parent(self.event)
                .order_by(db.func.lower(PaperTemplate.name), PaperTemplate.id))


@json_errors
class RHPaperTemplate(PaperTemplateMixin, RHProtectedEventBase):
    def _process_args(self):
        RHProtectedEventBase._process_args(self)
        self.template = (self._template_query()
                         .filter(PaperTemplate.id == request.view_args['template_id']).first_or_404())

    def _process_GET(self):
        return PaperTemplateSchema().jsonify(self.template)


@json_errors
class RHPaperTemplateList(PaperTemplateMixin, RHListBase, RHProtectedEventBase):
    schema = PaperTemplateSchema

    def _query(self):
        return self._template_query()

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(rule='/events/<int:event_id>/paper-templates', name='paper_templates', rh=RHPaperTemplateList,
             schema=PaperTemplateSchema, many=True, summary='List the paper templates of an event', tag='Papers'),
    Endpoint(rule='/events/<int:event_id>/paper-templates/<int:template_id>', name='paper_template',
             rh=RHPaperTemplate, schema=PaperTemplateSchema, summary='Paper template details', tag='Papers'),
]
