# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from flask import request

from indico.core.db import db
from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.modules.events.papers.file_types import PaperFileType
from indico.modules.events.papers.schemas import PaperFileTypeSchema as CorePaperFileTypeSchema
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase


class PaperFileTypeSchema(DescribedFieldsMixin, CorePaperFileTypeSchema):
    """Kind of file a paper may be submitted with, and the rules each one is checked against.

    The URL core adds points at the management endpoint editing the type, so it
    is left out.
    """

    class Meta(CorePaperFileTypeSchema.Meta):
        fields = (
            'id',
            'event_id',
            'name',
            'extensions',
            'allow_multiple_files',
            'required',
            'publishable',
            'filename_template',
            'is_used',
        )
        descriptions = {
            'id': 'Numeric identifier of the file type, unique across the whole instance.',
            'event_id': 'Identifier of the event defining the file type.',
            'name': 'Name of the file type, such as `Paper` or `Slides`.',
            'extensions': 'File extensions accepted, without the dot, or an empty list to accept any.',
            'allow_multiple_files': 'Whether a revision may carry more than one file of this type.',
            'required': 'Whether every revision has to carry a file of this type.',
            'publishable': 'Whether files of this type are shown to the readers of an accepted paper.',
            'filename_template': 'Pattern the name of an uploaded file has to follow, or `null` for any name.',
            'is_used': 'Whether a file of this type has been uploaded already.',
        }


class PaperFileTypeMixin:
    EVENT_FEATURE = 'papers'

    def _file_type_query(self):
        return PaperFileType.query.with_parent(self.event).order_by(db.func.lower(PaperFileType.name), PaperFileType.id)


@json_errors
class RHPaperFileType(PaperFileTypeMixin, RHProtectedEventBase):
    def _process_args(self):
        RHProtectedEventBase._process_args(self)
        self.file_type = (
            self._file_type_query().filter(PaperFileType.id == request.view_args['file_type_id']).first_or_404()
        )

    def _process_GET(self):
        return PaperFileTypeSchema().jsonify(self.file_type)


@json_errors
class RHPaperFileTypeList(PaperFileTypeMixin, RHListBase, RHProtectedEventBase):
    schema = PaperFileTypeSchema

    def _query(self):
        return self._file_type_query()

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(
        rule='/events/<int:event_id>/paper-file-types',
        name='paper_file_types',
        rh=RHPaperFileTypeList,
        schema=PaperFileTypeSchema,
        many=True,
        summary='List the file types papers are submitted as',
        tag='Papers',
    ),
    Endpoint(
        rule='/events/<int:event_id>/paper-file-types/<int:file_type_id>',
        name='paper_file_type',
        rh=RHPaperFileType,
        schema=PaperFileTypeSchema,
        summary='Details of one file type papers are submitted as',
        tag='Papers',
    ),
]
