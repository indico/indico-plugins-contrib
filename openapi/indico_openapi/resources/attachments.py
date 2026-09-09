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
from indico.modules.attachments.models.attachments import Attachment, AttachmentType
from indico.modules.attachments.models.folders import AttachmentFolder
from indico.modules.categories.controllers.base import RHDisplayCategoryBase
from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase
from indico_openapi.resources.contributions import RHContribution
from indico_openapi.resources.sessions import RHSession
from indico_openapi.resources.subcontributions import RHSubContribution


def _file_attribute(name):
    return fields.Function(lambda att: getattr(att.file, name) if att.type == AttachmentType.file else None)


class AttachmentFolderReferenceSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    class Meta:
        model = AttachmentFolder
        fields = ('id', 'title', 'description', 'is_default', 'is_protected')
        descriptions = {
            'id': 'Numeric identifier of the folder.',
            'title': 'Title of the folder, or `null` for the default folder.',
            'description': 'Description of the folder.',
            'is_default': 'Whether this is the default folder, which holds the files uploaded outside any folder.',
            'is_protected': 'Whether reading the folder requires permissions beyond those of the object it hangs on.',
        }


class AttachmentSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    class Meta:
        model = Attachment
        fields = ('id', 'type', 'title', 'description', 'modified_dt', 'is_protected', 'download_url', 'link_url',
                  'filename', 'content_type', 'size', 'checksum', 'folder')
        descriptions = {
            'id': 'Numeric identifier of the attachment, unique across the whole instance.',
            'type': 'Kind of attachment: `file` for an uploaded file, `link` for an external URL.',
            'title': 'Title of the attachment, which defaults to the file name.',
            'description': 'Description of the attachment.',
            'modified_dt': 'Moment the attachment was last modified, in UTC.',
            'is_protected': 'Whether reading the attachment requires permissions beyond those of its folder.',
            'download_url': 'Absolute URL to download the file, or to follow the link.',
            'link_url': 'Target of a link attachment, or `null` for a file.',
            'filename': 'Name of the uploaded file, or `null` for a link.',
            'content_type': 'MIME type of the uploaded file, such as `application/pdf`, or `null` for a link.',
            'size': 'Size of the uploaded file in bytes, or `null` for a link.',
            'checksum': 'MD5 hash of the uploaded file, or `null` for a link.',
            'folder': 'Folder holding the attachment.',
        }

    download_url = fields.String(attribute='absolute_download_url')
    filename = _file_attribute('filename')
    content_type = _file_attribute('content_type')
    size = _file_attribute('size')
    checksum = _file_attribute('md5')
    folder = fields.Nested(AttachmentFolderReferenceSchema)


class AttachmentMixin:
    """Attachments hang on an event, session, contribution, subcontribution or category.

    A folder can be visible while its contents are not, so the two checks are
    independent: the folder decides whether the attachment is listed at all,
    the attachment itself whether it can be read.
    """

    @property
    def linked_object(self):
        raise NotImplementedError

    def _attachment_query(self):
        folder_ids = (self.linked_object.attachment_folders
                      .filter_by(is_deleted=False)
                      .with_entities(AttachmentFolder.id))
        return (Attachment.query
                .filter(~Attachment.is_deleted, Attachment.folder_id.in_(folder_ids))
                .join(Attachment.folder)
                .order_by(AttachmentFolder.is_default.desc(), db.func.lower(Attachment.title), Attachment.id))

    def _is_visible(self, attachment):
        return attachment.folder.can_view(session.user) and attachment.can_access(session.user)


class AttachmentListMixin(AttachmentMixin):
    schema = AttachmentSchema

    def _query(self):
        return self._attachment_query()

    def _can_access(self, obj):
        return self._is_visible(obj)


class AttachmentDetailMixin(AttachmentMixin):
    def _process_GET(self):
        attachment = self._attachment_query().filter(Attachment.id == request.view_args['attachment_id']).first_or_404()
        if not self._is_visible(attachment):
            raise Forbidden
        return AttachmentSchema().jsonify(attachment)


@json_errors
class RHEventAttachmentList(AttachmentListMixin, RHListBase, RHProtectedEventBase):
    @property
    def linked_object(self):
        return self.event


@json_errors
class RHEventAttachment(AttachmentDetailMixin, RHProtectedEventBase):
    @property
    def linked_object(self):
        return self.event


@json_errors
class RHSessionAttachmentList(AttachmentListMixin, RHListBase, RHSession):
    @property
    def linked_object(self):
        return self.sess


@json_errors
class RHSessionAttachment(AttachmentDetailMixin, RHSession):
    @property
    def linked_object(self):
        return self.sess


@json_errors
class RHContributionAttachmentList(AttachmentListMixin, RHListBase, RHContribution):
    @property
    def linked_object(self):
        return self.contrib


@json_errors
class RHContributionAttachment(AttachmentDetailMixin, RHContribution):
    @property
    def linked_object(self):
        return self.contrib


@json_errors
class RHSubContributionAttachmentList(AttachmentListMixin, RHListBase, RHSubContribution):
    @property
    def linked_object(self):
        return self.subcontrib


@json_errors
class RHSubContributionAttachment(AttachmentDetailMixin, RHSubContribution):
    @property
    def linked_object(self):
        return self.subcontrib


@json_errors
class RHCategoryAttachmentList(AttachmentListMixin, RHListBase, RHDisplayCategoryBase):
    @property
    def linked_object(self):
        return self.category


@json_errors
class RHCategoryAttachment(AttachmentDetailMixin, RHDisplayCategoryBase):
    @property
    def linked_object(self):
        return self.category


_CONTRIB = '/events/<int:event_id>/contributions/<int:contrib_id>'
_SUBCONTRIB = f'{_CONTRIB}/subcontributions/<int:subcontrib_id>'

ENDPOINTS = [
    Endpoint(rule='/events/<int:event_id>/attachments', name='event_attachments', rh=RHEventAttachmentList,
             schema=AttachmentSchema, many=True, summary='List the attachments of an event', tag='Attachments'),
    Endpoint(rule='/events/<int:event_id>/attachments/<int:attachment_id>', name='event_attachment',
             rh=RHEventAttachment, schema=AttachmentSchema, summary='Attachment details', tag='Attachments'),
    Endpoint(rule='/events/<int:event_id>/sessions/<int:session_id>/attachments', name='session_attachments',
             rh=RHSessionAttachmentList, schema=AttachmentSchema, many=True,
             summary='List the attachments of a session', tag='Attachments'),
    Endpoint(rule='/events/<int:event_id>/sessions/<int:session_id>/attachments/<int:attachment_id>',
             name='session_attachment', rh=RHSessionAttachment, schema=AttachmentSchema,
             summary='Attachment details', tag='Attachments'),
    Endpoint(rule=f'{_CONTRIB}/attachments', name='contribution_attachments', rh=RHContributionAttachmentList,
             schema=AttachmentSchema, many=True, summary='List the attachments of a contribution', tag='Attachments'),
    Endpoint(rule=f'{_CONTRIB}/attachments/<int:attachment_id>', name='contribution_attachment',
             rh=RHContributionAttachment, schema=AttachmentSchema, summary='Attachment details', tag='Attachments'),
    Endpoint(rule=f'{_SUBCONTRIB}/attachments', name='subcontribution_attachments',
             rh=RHSubContributionAttachmentList, schema=AttachmentSchema, many=True,
             summary='List the attachments of a subcontribution', tag='Attachments'),
    Endpoint(rule=f'{_SUBCONTRIB}/attachments/<int:attachment_id>', name='subcontribution_attachment',
             rh=RHSubContributionAttachment, schema=AttachmentSchema, summary='Attachment details',
             tag='Attachments'),
    Endpoint(rule='/categories/<int:category_id>/attachments', name='category_attachments',
             rh=RHCategoryAttachmentList, schema=AttachmentSchema, many=True,
             summary='List the attachments of a category', tag='Attachments'),
    Endpoint(rule='/categories/<int:category_id>/attachments/<int:attachment_id>', name='category_attachment',
             rh=RHCategoryAttachment, schema=AttachmentSchema, summary='Attachment details', tag='Attachments'),
]
