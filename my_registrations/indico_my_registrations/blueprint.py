# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from indico.core.plugins import IndicoPluginBlueprint

from indico_my_registrations.controllers import RHMyRegistrations


blueprint = IndicoPluginBlueprint('my_registrations', __name__, url_prefix='/user')

with blueprint.add_prefixed_rules('/<int:user_id>'):
    blueprint.add_url_rule('/my-registrations/', 'list', RHMyRegistrations)
