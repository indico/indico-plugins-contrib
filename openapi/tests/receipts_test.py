# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


import pytest

from indico.modules.events.features.util import set_feature_enabled
from indico.modules.receipts.models.files import ReceiptFile
from indico.modules.receipts.models.templates import ReceiptTemplate
from indico.modules.receipts.settings import receipt_defaults


TEMPLATE_YAML = """
custom_fields:
  - name: reason
    type: input
    attributes:
      label: Reason
  - name: tier
    type: dropdown
    attributes:
      label: Tier
      options: [gold, silver]
"""


@pytest.fixture(autouse=True)
def registration_enabled(db, dummy_event):
    set_feature_enabled(dummy_event, 'registration', True)
    db.session.flush()


@pytest.fixture
def registration_manager(db, dummy_event, dummy_user):
    dummy_event.update_principal(dummy_user, permissions={'registration'})
    db.session.flush()


@pytest.fixture
def create_template(db):
    def _create(title, *, event=None, category=None, yaml='', default_filename='invoice'):
        tpl = ReceiptTemplate(title=title, event=event, category=category, html='<p>Hello</p>', css='', yaml=yaml,
                              default_filename=default_filename)
        db.session.add(tpl)
        db.session.flush()
        return tpl

    return _create


@pytest.fixture
def event_template(dummy_event, create_template):
    return create_template('Invoice', event=dummy_event, yaml=TEMPLATE_YAML)


@pytest.fixture
def category_template(dummy_category, create_template):
    return create_template('Attendance certificate', category=dummy_category, default_filename='certificate')


@pytest.fixture
def create_document(db, dummy_reg, event_template, create_file):
    def _create(filename, published=True, registration=None, template=None):
        file = create_file(filename, 'application/pdf', 'test', 'hello')
        document = ReceiptFile(registration=registration or dummy_reg, template=template or event_template,
                               is_published=published, file=file)
        db.session.add(document)
        db.session.flush()
        return document

    return _create


@pytest.mark.usefixtures('registration_manager')
def test_document_template_details(dummy_event, event_template, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/document-templates/{event_template.id}',
                           headers=token_headers)
    assert resp.status_code == 200
    assert resp.json == {
        'id': event_template.id,
        'title': 'Invoice',
        'default_filename': 'invoice',
        'custom_fields': [
            {'name': 'reason', 'type': 'input', 'attributes': {'label': 'Reason'}},
            {'name': 'tier', 'type': 'dropdown', 'attributes': {'label': 'Tier', 'options': ['gold', 'silver']}},
        ],
    }


@pytest.mark.usefixtures('registration_manager')
def test_document_template_list_includes_inherited_templates(dummy_event, event_template, category_template,
                                                             token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/document-templates', headers=token_headers)
    assert resp.status_code == 200
    assert [tpl['id'] for tpl in resp.json['results']] == [category_template.id, event_template.id]
    assert resp.json['count'] == 2
    assert resp.json['next_offset'] is None


@pytest.mark.usefixtures('registration_manager')
def test_deleted_templates_are_not_served(db, dummy_event, event_template, token_headers, test_client):
    event_template.is_deleted = True
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/document-templates', headers=token_headers)
    assert resp.json['results'] == []
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/document-templates/{event_template.id}',
                           headers=token_headers)
    assert resp.status_code == 404


@pytest.mark.usefixtures('registration_manager')
def test_event_defaults_are_applied(dummy_event, event_template, token_headers, test_client):
    receipt_defaults.set(dummy_event, f'custom_fields:{event_template.id}', {'reason': 'Fee', 'tier': 'silver'})
    receipt_defaults.set(dummy_event, f'filename:{event_template.id}', 'custom-invoice')
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/document-templates/{event_template.id}',
                           headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['default_filename'] == 'custom-invoice'
    reason, tier = resp.json['custom_fields']
    assert reason['attributes']['value'] == 'Fee'
    assert tier['attributes']['default'] == 1


def test_document_templates_are_manager_only(dummy_event, event_template, outsider_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/document-templates', headers=outsider_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/document-templates/{event_template.id}',
                           headers=outsider_headers)
    assert resp.status_code == 403


@pytest.mark.usefixtures('registration_manager')
def test_template_of_an_unrelated_category_is_not_found(dummy_event, create_category, create_template, token_headers,
                                                        test_client):
    other = create_template('Elsewhere', category=create_category(title='elsewhere'))
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/document-templates/{other.id}', headers=token_headers)
    assert resp.status_code == 404


@pytest.mark.usefixtures('registration_manager')
def test_document_details(dummy_event, dummy_reg, event_template, create_document, token_headers, test_client):
    document = create_document('invoice.pdf')
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/registrations/{dummy_reg.id}/documents/{document.file_id}',
        headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == document.file_id
    assert resp.json['registration_id'] == dummy_reg.id
    assert resp.json['template_id'] == event_template.id
    assert resp.json['filename'] == 'invoice.pdf'
    assert resp.json['content_type'] == 'application/pdf'
    assert resp.json['size'] == 5
    assert resp.json['is_published']
    assert resp.json['created_dt']


@pytest.mark.usefixtures('registration_manager')
def test_document_list_is_ordered_by_filename(dummy_event, dummy_reg, create_document, token_headers, test_client):
    second = create_document('b.pdf')
    first = create_document('a.pdf')
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registrations/{dummy_reg.id}/documents',
                           headers=token_headers)
    assert resp.status_code == 200
    assert [doc['id'] for doc in resp.json['results']] == [first.file_id, second.file_id]


@pytest.mark.usefixtures('registration_manager')
def test_managers_see_unpublished_documents(dummy_event, dummy_reg, create_document, token_headers, test_client):
    document = create_document('invoice.pdf', published=False)
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registrations/{dummy_reg.id}/documents',
                           headers=token_headers)
    assert [doc['id'] for doc in resp.json['results']] == [document.file_id]
    assert not resp.json['results'][0]['is_published']
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/registrations/{dummy_reg.id}/documents/{document.file_id}',
        headers=token_headers)
    assert resp.status_code == 200


def test_registrants_only_see_their_published_documents(dummy_event, dummy_reg, create_document, token_headers,
                                                        test_client):
    published = create_document('published.pdf')
    hidden = create_document('hidden.pdf', published=False)
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registrations/{dummy_reg.id}/documents',
                           headers=token_headers)
    assert resp.status_code == 200
    assert [doc['id'] for doc in resp.json['results']] == [published.file_id]
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/registrations/{dummy_reg.id}/documents/{hidden.file_id}',
        headers=token_headers)
    assert resp.status_code == 404


@pytest.mark.usefixtures('registration_manager')
def test_managers_get_the_management_download_url(dummy_event, dummy_reg, create_document, token_headers, test_client):
    document = create_document('invoice.pdf')
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/registrations/{dummy_reg.id}/documents/{document.file_id}',
        headers=token_headers)
    assert resp.json['download_url'].endswith(
        f'/event/{dummy_event.id}/manage/registration/{dummy_reg.registration_form_id}'
        f'/registrations/{dummy_reg.id}/receipts/{document.file_id}/invoice.pdf')


def test_registrants_get_the_display_download_url(dummy_event, dummy_reg, create_document, token_headers, test_client):
    document = create_document('invoice.pdf')
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/registrations/{dummy_reg.id}/documents/{document.file_id}',
        headers=token_headers)
    assert resp.json['download_url'].endswith(
        f'/event/{dummy_event.id}/registrations/{dummy_reg.registration_form_id}'
        f'/receipts/{document.file_id}/invoice.pdf')
    assert 'token' not in resp.json['download_url']


@pytest.mark.usefixtures('registration_manager')
def test_deleted_documents_are_not_served(db, dummy_event, dummy_reg, create_document, token_headers, test_client):
    document = create_document('invoice.pdf')
    document.is_deleted = True
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registrations/{dummy_reg.id}/documents',
                           headers=token_headers)
    assert resp.json['results'] == []
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/registrations/{dummy_reg.id}/documents/{document.file_id}',
        headers=token_headers)
    assert resp.status_code == 404


def test_documents_of_somebody_else_are_forbidden(dummy_event, dummy_reg, create_document, outsider_headers,
                                                  test_client):
    document = create_document('invoice.pdf')
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/registrations/{dummy_reg.id}/documents',
                           headers=outsider_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/registrations/{dummy_reg.id}/documents/{document.file_id}',
        headers=outsider_headers)
    assert resp.status_code == 403


@pytest.mark.usefixtures('registration_manager')
def test_document_of_another_registration_is_not_found(dummy_event, dummy_reg, dummy_regform, create_document,
                                                       create_registration, db, outsider, token_headers,
                                                       test_client):
    other_reg = create_registration(outsider, dummy_regform)
    dummy_event.registrations.append(other_reg)
    db.session.flush()
    document = create_document('invoice.pdf', registration=other_reg)
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/registrations/{dummy_reg.id}/documents/{document.file_id}',
        headers=token_headers)
    assert resp.status_code == 404


TEMPLATE_FIELDS = ('id', 'title', 'custom_fields', 'default_filename')


@pytest.fixture
def current_templates(dummy_event, indico_api):
    def _fetch():
        return indico_api(f'/event/{dummy_event.id}/manage/receipts/templates')

    return _fetch


@pytest.mark.usefixtures('registration_manager')
def test_document_template_matches_current_api(dummy_event, event_template, token_headers, test_client,
                                               current_templates, same_json):
    current = next(tpl for tpl in current_templates() if tpl['id'] == event_template.id)
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/document-templates/{event_template.id}',
                          headers=token_headers).json
    same_json(new, current, same=TEMPLATE_FIELDS)


@pytest.mark.usefixtures('registration_manager')
def test_document_template_defaults_match_current_api(dummy_event, event_template, token_headers, test_client,
                                                      current_templates, same_json):
    receipt_defaults.set(dummy_event, f'custom_fields:{event_template.id}', {'reason': 'Fee', 'tier': 'silver'})
    receipt_defaults.set(dummy_event, f'filename:{event_template.id}', 'custom-invoice')
    current = next(tpl for tpl in current_templates() if tpl['id'] == event_template.id)
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/document-templates/{event_template.id}',
                          headers=token_headers).json
    same_json(new, current, same=TEMPLATE_FIELDS)


@pytest.mark.usefixtures('registration_manager')
def test_document_template_list_matches_current_api(dummy_event, event_template, category_template, token_headers,
                                                    test_client, current_templates, same_json_list):
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/document-templates',
                          headers=token_headers).json['results']
    same_json_list(new, current_templates(), same=TEMPLATE_FIELDS)
