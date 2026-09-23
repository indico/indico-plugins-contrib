# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from flask import request, session
from werkzeug.exceptions import Forbidden

from indico.modules.files.models.files import File
from indico.modules.files.schemas import FileSchema as CoreFileSchema
from indico.web.rh import RHProtected, json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase


class FileSchema(DescribedFieldsMixin, CoreFileSchema):
    class Meta(CoreFileSchema.Meta):
        descriptions = {
            'uuid': 'Identifier of the file, unique across the whole instance. It is also what authorises '
                    'reading the file, so it is never handed out to somebody who may not.',
            'filename': 'Name the file was uploaded under.',
            'content_type': 'MIME type of the file, such as `application/pdf`.',
            'size': 'Size of the file in bytes.',
            'claimed': 'Whether the file is attached to something. Unclaimed files are leftovers of an upload '
                       'that went nowhere and get deleted automatically.',
            'created_dt': 'Moment the file was uploaded, in UTC.',
        }


@json_errors
class RHFile(RHProtected):
    """Serve one uploaded file by its identifier.

    A file has no access list of its own: Indico protects it by keeping its
    identifier secret, and hands it out through the receipt, editing revision or
    data export that holds it. So knowing the identifier is the permission, which
    is the same rule the file info page applies.
    """

    def _process_args(self):
        self.file = File.query.filter_by(uuid=request.view_args['uuid']).first_or_404()

    def _process_GET(self):
        return FileSchema().jsonify(self.file)


@json_errors
class RHFileList(RHListBase, RHProtected):
    """List every uploaded file.

    Listing hands out the identifiers that authorise reading the files, so it is
    restricted to administrators, who can already reach every object holding one.
    """

    schema = FileSchema

    def _check_access(self):
        RHProtected._check_access(self)
        if not session.user.is_admin:
            raise Forbidden

    def _query(self):
        return File.query.order_by(File.id)

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(rule='/files', name='files', rh=RHFileList, schema=FileSchema, many=True,
             summary='List the files uploaded to the instance', tag='Files'),
    Endpoint(rule='/files/<uuid:uuid>', name='file', rh=RHFile, schema=FileSchema,
             summary='Details of one file uploaded to the instance', tag='Files'),
]
