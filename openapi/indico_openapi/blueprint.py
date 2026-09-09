# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from pathlib import Path

import flask_swagger_ui

from indico.core.plugins import IndicoPluginBlueprint

from indico_openapi.docs import RHDocs, RHSpec
from indico_openapi.resources import ENDPOINTS


SWAGGER_UI_DIST = Path(flask_swagger_ui.__file__).parent / 'dist'

blueprint = IndicoPluginBlueprint('openapi', __name__, url_prefix='/api/v1',
                                  static_folder=str(SWAGGER_UI_DIST))

blueprint.add_url_rule('/openapi.json', 'spec', RHSpec)
blueprint.add_url_rule('/docs', 'docs', RHDocs)

for _endpoint in ENDPOINTS:
    blueprint.add_url_rule(_endpoint.rule, _endpoint.name, _endpoint.rh)
