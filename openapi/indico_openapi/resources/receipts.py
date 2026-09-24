# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from flask import request, session
from marshmallow import fields, post_dump
from werkzeug.exceptions import Forbidden, NotFound

from indico.core.marshmallow import mm
from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.modules.events.management.controllers import RHManageEventBase
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.registrations import Registration
from indico.modules.files.models.files import File
from indico.modules.receipts.controllers.event import RHAllEventTemplates
from indico.modules.receipts.models.files import ReceiptFile
from indico.modules.receipts.schemas import ReceiptTemplateDBSchema
from indico.modules.receipts.settings import receipt_defaults
from indico.modules.receipts.util import get_inherited_templates
from indico.web.flask.util import url_for
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase, jsonify_results


class DocumentTemplateSchema(DescribedFieldsMixin, ReceiptTemplateDBSchema):
    """Template the organisers render a document from, such as an invoice or a certificate.

    Core also keeps the HTML body, the stylesheet, the raw metadata and the
    object the template belongs to, but it only serves them to the interface
    editing them. What the interface generating a document reads is served
    instead: the title, the filename and the fields the caller has to fill in.
    """

    class Meta(ReceiptTemplateDBSchema.Meta):
        fields = ('id', 'title', 'custom_fields', 'default_filename')
        descriptions = {
            'id': 'Numeric identifier of the template, unique across the whole instance.',
            'title': 'Title of the template.',
            'custom_fields': 'Values the template asks for before it can be rendered, in the order it declares '
            'them. Each one carries a `name`, a `type` of `input`, `textarea`, `checkbox`, '
            '`dropdown` or `image`, the `attributes` that type takes, and the `validations` it '
            'applies. The defaults the event set are already applied.',
            'default_filename': 'Name the generated file gets, without extension, or an empty string when the '
            'template sets none. The override the event set is already applied.',
        }

    @post_dump
    def _apply_event_defaults(self, data, **kwargs):
        event = self.context['event']
        if defaults := receipt_defaults.get(event, f'custom_fields:{data["id"]}'):
            RHAllEventTemplates._apply_event_defaults(self, data, defaults)
        if filename := receipt_defaults.get(event, f'filename:{data["id"]}'):
            data['default_filename'] = filename
        return data


class DocumentSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """Document generated from a template for one registration.

    Core has no schema for one: both the management list and the registration
    page render the files straight from the model. The values the document was
    rendered with are left out, because they are a snapshot of the registration
    taken when it was generated, and the registration itself has its own
    endpoints.
    """

    class Meta:
        model = ReceiptFile
        fields = (
            'id',
            'registration_id',
            'template_id',
            'filename',
            'content_type',
            'size',
            'created_dt',
            'is_published',
            'download_url',
        )
        descriptions = {
            'id': 'Numeric identifier of the document, unique across the whole instance.',
            'registration_id': 'Identifier of the registration the document was generated for.',
            'template_id': 'Identifier of the template the document was generated from.',
            'filename': 'Name of the generated file.',
            'content_type': 'MIME type of the document, always `application/pdf`.',
            'size': 'Size of the document in bytes.',
            'created_dt': 'Moment the document was generated, in UTC.',
            'is_published': 'Whether the registrant can see the document. An unpublished one is only listed '
            'for managers.',
            'download_url': 'Absolute URL the document is downloaded from. A manager gets the management URL, '
            'a registrant the one their own registration page uses.',
        }

    id = fields.Integer(attribute='file_id')
    filename = fields.String(attribute='file.filename')
    content_type = fields.String(attribute='file.content_type')
    size = fields.Integer(attribute='file.size')
    created_dt = fields.DateTime(attribute='file.created_dt')
    download_url = fields.Method('_download_url')

    def _download_url(self, receipt):
        if self.context['can_manage']:
            return url_for('event_registration.download_receipt', receipt.locator.filename, _external=True)
        return receipt.external_registrant_download_url


class DocumentTemplateMixin:
    """Scope and access checks shared by the document template endpoints.

    Indico only enumerates the templates of an event on its management
    interface, so they stay restricted to whoever manages its registrations.
    The scope is the one that interface offers: the templates of the event plus
    the ones it inherits from its categories.
    """

    PERMISSION = 'registration'

    def _templates(self):
        templates = get_inherited_templates(self.event) | set(self.event.receipt_templates)
        return sorted(templates, key=lambda tpl: (tpl.title.lower(), tpl.id))

    def _template_schema(self, **kwargs):
        return DocumentTemplateSchema(context={'event': self.event}, **kwargs)


@json_errors
class RHDocumentTemplate(DocumentTemplateMixin, RHManageEventBase):
    def _process_args(self):
        RHManageEventBase._process_args(self)
        template_id = request.view_args['template_id']
        template = next((tpl for tpl in self._templates() if tpl.id == template_id), None)
        if template is None:
            raise NotFound
        self.template = template

    def _process_GET(self):
        return self._template_schema().jsonify(self.template)


@json_errors
class RHDocumentTemplateList(DocumentTemplateMixin, RHManageEventBase):
    def _process_GET(self):
        return jsonify_results(self._template_schema(many=True), self._templates())


class DocumentMixin:
    """Access checks shared by the document endpoints.

    The documents of a registration are served to whoever manages the
    registrations of the event and to the registrant themselves, which is what
    the registration page shows. A registrant only gets the published ones,
    because an unpublished document is one the organisers have not released yet.
    """

    EVENT_FEATURE = 'registration'

    def _process_args(self):
        RHProtectedEventBase._process_args(self)
        self.can_manage = self.event.can_manage(session.user, permission='registration')
        self.registration = (
            Registration.query
            .with_parent(self.event)
            .filter(
                Registration.id == request.view_args['registration_id'],
                ~Registration.is_deleted,
                RegistrationForm.query.filter(
                    RegistrationForm.id == Registration.registration_form_id, ~RegistrationForm.is_deleted
                ).exists(),
            )
            .first_or_404()
        )

    def _check_access(self):
        RHProtectedEventBase._check_access(self)
        if not self.can_manage and (not session.user or self.registration.user != session.user):
            raise Forbidden

    def _document_query(self):
        query = (
            ReceiptFile.query
            .filter(ReceiptFile.registration == self.registration, ~ReceiptFile.is_deleted)
            .join(ReceiptFile.file)
            .order_by(File.filename, ReceiptFile.file_id)
        )
        if not self.can_manage:
            query = query.filter(ReceiptFile.is_published)
        return query

    def _document_schema(self, **kwargs):
        return DocumentSchema(context={'can_manage': self.can_manage}, **kwargs)


@json_errors
class RHDocument(DocumentMixin, RHProtectedEventBase):
    def _process_args(self):
        DocumentMixin._process_args(self)
        self.document = (
            self._document_query().filter(ReceiptFile.file_id == request.view_args['file_id']).first_or_404()
        )

    def _process_GET(self):
        return self._document_schema().jsonify(self.document)


@json_errors
class RHDocumentList(DocumentMixin, RHListBase, RHProtectedEventBase):
    schema = DocumentSchema

    def _query(self):
        return self._document_query()

    def _can_access(self, obj):
        return True

    def _dump_schema(self):
        return self._document_schema(many=True)


ENDPOINTS = [
    Endpoint(
        rule='/events/<int:event_id>/document-templates',
        name='document_templates',
        rh=RHDocumentTemplateList,
        schema=DocumentTemplateSchema,
        many=True,
        summary='List the document templates available to an event',
        tag='Documents',
    ),
    Endpoint(
        rule='/events/<int:event_id>/document-templates/<int:template_id>',
        name='document_template',
        rh=RHDocumentTemplate,
        schema=DocumentTemplateSchema,
        summary='Details of one document template of an event',
        tag='Documents',
    ),
    Endpoint(
        rule='/events/<int:event_id>/registrations/<int:registration_id>/documents',
        name='documents',
        rh=RHDocumentList,
        schema=DocumentSchema,
        many=True,
        summary='List the documents generated for a registration',
        tag='Documents',
    ),
    Endpoint(
        rule='/events/<int:event_id>/registrations/<int:registration_id>/documents/<int:file_id>',
        name='document',
        rh=RHDocument,
        schema=DocumentSchema,
        summary='Details of one document generated for a registration',
        tag='Documents',
    ),
]
