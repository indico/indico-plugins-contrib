# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

def test_spec_requires_login(test_client):
    resp = test_client.get('/api/v1/openapi.json')
    assert resp.status_code == 403


def test_spec_lists_every_endpoint(dummy_user, test_client):
    from indico_openapi.resources import ENDPOINTS
    with test_client.session_transaction() as sess:
        sess.set_session_user(dummy_user)
    resp = test_client.get('/api/v1/openapi.json')
    assert resp.status_code == 200
    assert resp.json['openapi'] == '3.0.3'
    assert len(resp.json['paths']) == len(ENDPOINTS)


def test_docs_page_is_served(dummy_user, test_client):
    with test_client.session_transaction() as sess:
        sess.set_session_user(dummy_user)
    resp = test_client.get('/api/v1/docs')
    assert resp.status_code == 200
    assert 'swagger-ui' in resp.text


def test_spec_documents_every_field(dummy_user, test_client):
    with test_client.session_transaction() as sess:
        sess.set_session_user(dummy_user)
    resp = test_client.get('/api/v1/openapi.json')
    undocumented = [f'{name}.{field}'
                    for name, schema in resp.json['components']['schemas'].items()
                    for field, prop in schema.get('properties', {}).items()
                    if not prop.get('description')]
    assert not undocumented


def test_spec_wraps_list_results(dummy_user, test_client):
    with test_client.session_transaction() as sess:
        sess.set_session_user(dummy_user)
    resp = test_client.get('/api/v1/openapi.json')
    operation = resp.json['paths']['/api/v1/events']['get']
    schema = operation['responses']['200']['content']['application/json']['schema']
    assert schema['$ref'] == '#/components/schemas/EventPage'
    assert {p['name'] for p in operation['parameters']} >= {'limit', 'offset', 'category_id'}
