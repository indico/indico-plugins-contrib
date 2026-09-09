# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


import re

from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from marshmallow import fields

from indico.core.marshmallow import mm

from indico_openapi.resources import ENDPOINTS


SPEC_VERSION = '1.0.0'
OPENAPI_VERSION = '3.0.3'
BASE_PATH = '/api/v1'
DESCRIPTION = """
Read-only access to Indico resources.

Every request is resolved with the permissions of the authenticated user, so a
response never contains anything the same person could not see in the web
interface. Objects the user cannot access are omitted from lists rather than
reported as an error.

From this page requests are authenticated with your Indico session cookie, so
there is nothing to fill in. From outside, use a personal token created under
your Indico profile with the `read:everything` scope, sent as a bearer token.
Do not send both: Indico rejects a request that carries a token and a session
cookie at the same time.
""".strip()

_PARAM_RE = re.compile(r'<(?:(?P<converter>[^:>]+):)?(?P<name>[^>]+)>')
_CONVERTER_TYPES = {'int': 'integer', 'float': 'number'}
_page_schemas = {}


def page_schema(schema_cls):
    """Build (once) the paginated envelope wrapping a resource schema."""
    if schema_cls not in _page_schemas:
        name = re.sub(r'Schema$', '', schema_cls.__name__)
        _page_schemas[schema_cls] = type(f'{name}PageSchema', (mm.Schema,), {
            'results': fields.List(fields.Nested(schema_cls),
                                   metadata={'description': 'The results of this page.'}),
            'count': fields.Integer(metadata={'description': 'Number of results in this page.'}),
            'next_offset': fields.Integer(allow_none=True,
                                          metadata={'description': 'Value to pass as `offset` to get the next '
                                                                   'page, or `null` when this is the last one.'}),
        })
    return _page_schemas[schema_cls]


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
        schema = page_schema(endpoint.schema) if endpoint.many else endpoint.schema
        content = {'application/json': {'schema': schema}}
    responses = {
        '200': {'description': 'Success', **({'content': content} if content else {})},
        '403': {'description': 'The user cannot access this resource'},
        '404': {'description': 'The resource does not exist'},
    }
    if args_schema := getattr(endpoint.rh, 'args_schema', None):
        params = [*params, {'in': 'query', 'schema': args_schema}]
    return {'get': {'summary': endpoint.summary, 'tags': [endpoint.tag],
                    'parameters': params, 'responses': responses}}


def build_spec():
    spec = APISpec(title='Indico REST API', version=SPEC_VERSION, openapi_version=OPENAPI_VERSION,
                   plugins=[MarshmallowPlugin()], info={'description': DESCRIPTION})
    spec.components.security_scheme('bearer', {'type': 'http', 'scheme': 'bearer',
                                               'description': 'Indico personal token or OAuth access token'})
    for endpoint in ENDPOINTS:
        path, params = _path_and_params(endpoint.rule)
        spec.path(path=BASE_PATH + path, operations=_operation(endpoint, params))
    data = spec.to_dict()
    data['security'] = [{'bearer': []}, {}]
    return data
