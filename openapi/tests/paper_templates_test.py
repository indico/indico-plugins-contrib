# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 Unconventional
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest

from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.modules.events.features.util import set_feature_enabled
from indico.modules.events.papers.models.templates import PaperTemplate


@pytest.fixture(autouse=True)
def papers_enabled(db, dummy_event):
    set_feature_enabled(dummy_event, 'papers', True)
    db.session.flush()


@pytest.fixture
def create_paper_template(db, dummy_event):
    def _create(name, filename, content_type, description=''):
        template = PaperTemplate(
            event=dummy_event, name=name, description=description, filename=filename, content_type=content_type
        )
        template.save(b'\\documentclass{article}')
        db.session.add(template)
        db.session.flush()
        return template

    return _create


@pytest.fixture
def latex_template(create_paper_template):
    return create_paper_template('LaTeX template', 'template.tex', 'application/x-tex', 'Use the article class.')


def test_paper_template_details(dummy_event, latex_template, token_headers, test_client):
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/paper-templates/{latex_template.id}', headers=token_headers
    )
    assert resp.status_code == 200
    assert resp.json == {
        'id': latex_template.id,
        'event_id': dummy_event.id,
        'name': 'LaTeX template',
        'description': 'Use the article class.',
        'filename': 'template.tex',
        'content_type': 'application/x-tex',
        'size': latex_template.size,
        'download_url': f'/event/{dummy_event.id}/papers/templates/{latex_template.id}-template.tex',
    }


def test_paper_template_list_is_sorted_by_name(
    dummy_event, latex_template, create_paper_template, token_headers, test_client
):
    word = create_paper_template('Word template', 'template.docx', 'application/msword')
    abstract = create_paper_template('abstract', 'abstract.txt', 'text/plain')
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/paper-templates', headers=token_headers)
    assert resp.status_code == 200
    assert [t['id'] for t in resp.json['results']] == [abstract.id, latex_template.id, word.id]


def test_paper_templates_need_the_papers_feature(db, dummy_event, latex_template, token_headers, test_client):
    set_feature_enabled(dummy_event, 'papers', False)
    db.session.flush()
    url = f'/api/v1/events/{dummy_event.id}/paper-templates'
    assert test_client.get(url, headers=token_headers).status_code == 404
    assert test_client.get(f'{url}/{latex_template.id}', headers=token_headers).status_code == 404


def test_paper_template_denied_without_event_access(db, dummy_event, latex_template, outsider_headers, test_client):
    dummy_event.protection_mode = ProtectionMode.protected
    db.session.flush()
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/paper-templates/{latex_template.id}', headers=outsider_headers
    )
    assert resp.status_code == 403
    assert 'error' in resp.json
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/paper-templates', headers=outsider_headers)
    assert resp.status_code == 403


def test_paper_template_of_another_event_is_not_found(db, latex_template, create_event, token_headers, test_client):
    other = create_event()
    set_feature_enabled(other, 'papers', True)
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{other.id}/paper-templates/{latex_template.id}', headers=token_headers)
    assert resp.status_code == 404
