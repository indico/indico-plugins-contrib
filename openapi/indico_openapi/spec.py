# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import re

from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin

from indico_openapi.resources import ENDPOINTS


SPEC_VERSION = '1.0.0'
OPENAPI_VERSION = '3.0.3'
BASE_PATH = '/api/v1'
DESCRIPTION = """
Read-only access to Indico resources.

Every request is resolved with the permissions of the token owner, so a
response never contains anything the same person could not see in the web
interface.

Authenticate with a personal token created under your Indico profile with the
`read:everything` scope, sent as a bearer token.
""".strip()

_PARAM_RE = re.compile(r'<(?:(?P<converter>[^:>]+):)?(?P<name>[^>]+)>')
_CONVERTER_TYPES = {'int': 'integer', 'float': 'number'}


def _path_and_params(rule):
    params = [
        {
            'name': match.group('name'),
            'in': 'path',
            'required': True,
            'schema': {'type': _CONVERTER_TYPES.get(match.group('converter'), 'string')},
        }
        for match in _PARAM_RE.finditer(rule)
    ]
    return _PARAM_RE.sub(lambda m: f'{{{m.group("name")}}}', rule), params


def _operation(endpoint, params):
    content = None
    if endpoint.schema:
        schema = {'type': 'array', 'items': endpoint.schema} if endpoint.many else endpoint.schema
        content = {'application/json': {'schema': schema}}
    responses = {
        '200': {'description': 'Success', **({'content': content} if content else {})},
        '403': {'description': 'The token owner cannot access this resource'},
        '404': {'description': 'The resource does not exist'},
    }
    query_params = [
        {'name': name, 'in': 'query', 'required': False, 'schema': schema}
        for name, schema in endpoint.query_args.items()
    ]
    return {'get': {'summary': endpoint.summary, 'tags': [endpoint.tag],
                    'parameters': params + query_params, 'responses': responses}}


def build_spec():
    spec = APISpec(title='Indico REST API', version=SPEC_VERSION, openapi_version=OPENAPI_VERSION,
                   plugins=[MarshmallowPlugin()], info={'description': DESCRIPTION})
    spec.components.security_scheme('bearer', {'type': 'http', 'scheme': 'bearer',
                                               'description': 'Indico personal token or OAuth access token'})
    for endpoint in ENDPOINTS:
        path, params = _path_and_params(endpoint.rule)
        spec.path(path=BASE_PATH + path, operations=_operation(endpoint, params))
    data = spec.to_dict()
    data['security'] = [{'bearer': []}]
    return data
