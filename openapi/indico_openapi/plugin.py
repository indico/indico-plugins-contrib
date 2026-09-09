# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from indico.core.plugins import IndicoPlugin

from indico_openapi.blueprint import blueprint


class OpenAPIPlugin(IndicoPlugin):
    """OpenAPI

    Exposes a read-only REST API for Indico resources, described with an
    OpenAPI v3 document and browsable through a Swagger UI page.
    """

    configurable = False

    def get_blueprints(self):
        return blueprint
