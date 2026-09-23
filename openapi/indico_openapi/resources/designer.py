# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from operator import attrgetter

from flask import request
from marshmallow import fields
from werkzeug.exceptions import NotFound

from indico.core import signals
from indico.core.marshmallow import mm
from indico.modules.designer.controllers import RHListEventTemplates
from indico.modules.designer.models.images import DesignerImageFile
from indico.modules.designer.models.templates import DesignerTemplate
from indico.modules.designer.util import get_inherited_templates
from indico.modules.events.management.controllers import RHManageEventBase
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, jsonify_results


class DesignerImageSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """Image a designer template places on the badge or poster it draws."""

    class Meta:
        model = DesignerImageFile
        fields = ('id', 'download_url')
        descriptions = {
            'id': 'Numeric identifier of the image, unique across the whole instance. The items of `data` '
                  'reference it.',
            'download_url': 'URL the image is downloaded from, relative to the Indico instance.',
        }

    download_url = fields.String()


class SortedImages(fields.List):
    """Serialize the images of a template in a stable order.

    They come from a relationship with no ordering of its own, and a list whose
    order changes between calls is of no use to a caller.
    """

    def get_value(self, obj, attr, **kwargs):
        return sorted(obj.images, key=attrgetter('id'))


class DesignerTemplateSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """Template the organisers draw a badge or a poster from.

    Core has no schema for one: the management page renders the templates
    straight from the model and the editor reads the drawing through its own
    endpoint. What that endpoint serves is served here, which leaves out the
    settings only the management page acts on, such as whether the template is
    a ticket, whether it can be cloned and which registration form it is
    linked to.
    """

    class Meta:
        model = DesignerTemplate
        fields = ('id', 'title', 'data', 'background_url', 'images')
        descriptions = {
            'id': 'Numeric identifier of the template, unique across the whole instance.',
            'title': 'Title of the template.',
            'data': 'The drawing itself: the page format under `width`, `height` and `landscape`, the background '
                    'position under `background_position`, and the text and image boxes under `items`. Each item '
                    'carries its `type`, its position under `x` and `y`, its size, and the styling it renders '
                    'with.',
            'background_url': 'URL of the image drawn behind everything else, relative to the Indico instance, '
                              'or `null` when the template has no background.',
            'images': 'Images the items of the template reference.',
        }

    data = fields.Raw()
    background_url = fields.Function(lambda template: (template.background_image.download_url
                                                       if template.background_image else None))
    images = SortedImages(fields.Nested(DesignerImageSchema))


class DesignerTemplateMixin:
    """Scope and access checks shared by the designer template endpoints.

    Indico only enumerates the templates of an event on its management page, so
    they stay restricted to its managers. The scope is the one that page offers:
    the templates of the event plus the ones it inherits from its categories,
    after the plugins filtering the inherited ones have had their say.
    """

    def _templates(self):
        inherited = list(get_inherited_templates(self.event))
        signals.event.filter_selectable_badges.send(RHListEventTemplates, badge_templates=inherited)
        templates = set(inherited) | set(self.event.designer_templates)
        return sorted(templates, key=lambda template: (template.title.lower(), template.id))


@json_errors
class RHDesignerTemplate(DesignerTemplateMixin, RHManageEventBase):
    def _process_args(self):
        RHManageEventBase._process_args(self)
        template_id = request.view_args['template_id']
        template = next((tpl for tpl in self._templates() if tpl.id == template_id), None)
        if template is None:
            raise NotFound
        self.template = template

    def _process_GET(self):
        return DesignerTemplateSchema().jsonify(self.template)


@json_errors
class RHDesignerTemplateList(DesignerTemplateMixin, RHManageEventBase):
    def _process_GET(self):
        return jsonify_results(DesignerTemplateSchema(many=True), self._templates())


ENDPOINTS = [
    Endpoint(rule='/events/<int:event_id>/designer-templates', name='designer_templates',
             rh=RHDesignerTemplateList, schema=DesignerTemplateSchema, many=True,
             summary='List the badge and poster templates available to an event', tag='Designer'),
    Endpoint(rule='/events/<int:event_id>/designer-templates/<int:template_id>', name='designer_template',
             rh=RHDesignerTemplate, schema=DesignerTemplateSchema, summary='Details of one badge or poster template',
             tag='Designer'),
]
