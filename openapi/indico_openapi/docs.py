# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from flask import jsonify, session

from indico.core.plugins import render_plugin_template, url_for_plugin
from indico.web.rh import RHProtected, json_errors

from indico_openapi.spec import build_spec


@json_errors
class RHSpec(RHProtected):
    def _process(self):
        return jsonify(build_spec())


class RHDocs(RHProtected):
    def _process(self):
        return render_plugin_template('docs.html', spec_url=url_for_plugin('openapi.spec'), user=session.user)
