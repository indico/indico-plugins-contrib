# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


import importlib
import pkgutil


ENDPOINTS = []

for _module_info in pkgutil.iter_modules(__path__):
    if _module_info.name != 'base':
        ENDPOINTS += importlib.import_module(f'{__name__}.{_module_info.name}').ENDPOINTS
