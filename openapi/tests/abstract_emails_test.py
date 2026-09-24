# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 Unconventional
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from datetime import UTC, datetime

import pytest

from indico.modules.events.abstracts.models.email_logs import AbstractEmailLogEntry
from indico.modules.events.abstracts.models.email_templates import AbstractEmailTemplate
from indico.modules.events.features.util import set_feature_enabled


@pytest.fixture(autouse=True)
def abstracts_enabled(db, dummy_event):
    set_feature_enabled(dummy_event, 'abstracts', True)
    db.session.flush()


@pytest.fixture
def abstract_manager(db, dummy_event, dummy_user):
    dummy_event.update_principal(dummy_user, permissions={'abstracts'})
    db.session.flush()


@pytest.fixture
def create_email_template(db, dummy_event):
    def _create(title, **kwargs):
        kwargs.setdefault('subject', 'Your abstract was accepted')
        kwargs.setdefault('body', 'Dear {abstract_submitter},')
        kwargs.setdefault('rules', [{'state': [1]}])
        kwargs.setdefault('reply_to_address', '')
        kwargs.setdefault('extra_cc_emails', [])
        template = AbstractEmailTemplate(event=dummy_event, title=title, **kwargs)
        db.session.add(template)
        db.session.flush()
        return template

    return _create


@pytest.fixture
def acceptance_template(create_email_template):
    return create_email_template(
        'Acceptance',
        reply_to_address='chair@example.com',
        extra_cc_emails=['records@example.com'],
        include_authors=True,
        include_submitter=True,
        include_coauthors=False,
        stop_on_match=True,
    )


@pytest.fixture
def sent_email(db, dummy_abstract, acceptance_template):
    entry = AbstractEmailLogEntry(
        abstract=dummy_abstract,
        email_template=acceptance_template,
        sent_dt=datetime(2026, 9, 1, 8, 0, tzinfo=UTC),
        recipients=['doe@example.com', 'records@example.com'],
        subject='Your abstract was accepted',
        body='Dear John Doe,',
        data={'template_name': 'Acceptance'},
    )
    db.session.flush()
    return entry


@pytest.mark.usefixtures('abstract_manager')
def test_abstract_email_template_details(dummy_event, acceptance_template, token_headers, test_client):
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/abstract-email-templates/{acceptance_template.id}', headers=token_headers
    )
    assert resp.status_code == 200
    assert resp.json == {
        'id': acceptance_template.id,
        'event_id': dummy_event.id,
        'position': 1,
        'title': 'Acceptance',
        'subject': 'Your abstract was accepted',
        'body': 'Dear {abstract_submitter},',
        'reply_to_address': 'chair@example.com',
        'extra_cc_emails': ['records@example.com'],
        'include_submitter': True,
        'include_authors': True,
        'include_coauthors': False,
        'stop_on_match': True,
        'rules': [{'state': [1]}],
    }


@pytest.mark.usefixtures('abstract_manager')
def test_abstract_email_template_list_follows_positions(
    dummy_event, acceptance_template, create_email_template, token_headers, test_client
):
    rejection = create_email_template('Rejection', rules=[{'state': [2]}])
    acceptance_template.position = 5
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/abstract-email-templates', headers=token_headers)
    assert resp.status_code == 200
    assert [t['id'] for t in resp.json['results']] == [rejection.id, acceptance_template.id]


def test_abstract_email_templates_are_manager_only(dummy_event, acceptance_template, token_headers, test_client):
    url = f'/api/v1/events/{dummy_event.id}/abstract-email-templates'
    assert test_client.get(url, headers=token_headers).status_code == 403
    resp = test_client.get(f'{url}/{acceptance_template.id}', headers=token_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json


@pytest.mark.usefixtures('abstract_manager')
def test_abstract_email_templates_need_the_abstracts_feature(
    db, dummy_event, acceptance_template, token_headers, test_client
):
    set_feature_enabled(dummy_event, 'abstracts', False)
    db.session.flush()
    url = f'/api/v1/events/{dummy_event.id}/abstract-email-templates'
    assert test_client.get(url, headers=token_headers).status_code == 404
    assert test_client.get(f'{url}/{acceptance_template.id}', headers=token_headers).status_code == 404


@pytest.mark.usefixtures('abstract_manager')
def test_abstract_email_template_of_another_event_is_not_found(
    db, acceptance_template, create_event, dummy_user, token_headers, test_client
):
    other = create_event()
    other.update_principal(dummy_user, permissions={'abstracts'})
    set_feature_enabled(other, 'abstracts', True)
    db.session.flush()
    resp = test_client.get(
        f'/api/v1/events/{other.id}/abstract-email-templates/{acceptance_template.id}', headers=token_headers
    )
    assert resp.status_code == 404


@pytest.mark.usefixtures('abstract_manager')
def test_abstract_email_details(
    dummy_event, dummy_abstract, acceptance_template, sent_email, dummy_user, token_headers, test_client
):
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/abstracts/{dummy_abstract.id}/emails/{sent_email.id}', headers=token_headers
    )
    assert resp.status_code == 200
    assert resp.json == {
        'id': sent_email.id,
        'abstract_id': dummy_abstract.id,
        'email_template_id': acceptance_template.id,
        'template_title': 'Acceptance',
        'sent_dt': '2026-09-01T08:00:00+00:00',
        'sent_by': None,
        'recipients': ['doe@example.com', 'records@example.com'],
        'subject': 'Your abstract was accepted',
        'body': 'Dear John Doe,',
    }


@pytest.mark.usefixtures('abstract_manager')
def test_abstract_email_list_is_oldest_first(
    db, dummy_event, dummy_abstract, sent_email, dummy_user, token_headers, test_client
):
    later = AbstractEmailLogEntry(
        abstract=dummy_abstract,
        user=dummy_user,
        sent_dt=datetime(2026, 9, 2, 8, 0, tzinfo=UTC),
        recipients=['doe@example.com'],
        subject='Reminder',
        body='Dear John Doe,',
        data={},
    )
    db.session.flush()
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/abstracts/{dummy_abstract.id}/emails', headers=token_headers
    )
    assert resp.status_code == 200
    assert [entry['id'] for entry in resp.json['results']] == [sent_email.id, later.id]
    assert resp.json['results'][1]['sent_by']['id'] == dummy_user.id
    assert resp.json['results'][1]['template_title'] is None


def test_abstract_emails_need_judging_rights(
    dummy_event, dummy_abstract, dummy_user, sent_email, token_headers, test_client
):
    # the submitter reads their own abstract but not the notifications sent about it
    assert dummy_abstract.submitter == dummy_user
    url = f'/api/v1/events/{dummy_event.id}/abstracts/{dummy_abstract.id}/emails'
    assert test_client.get(url, headers=token_headers).status_code == 403
    resp = test_client.get(f'{url}/{sent_email.id}', headers=token_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json


@pytest.mark.usefixtures('abstract_manager')
def test_abstract_email_of_another_abstract_is_not_found(
    db, dummy_event, dummy_abstract, dummy_user, sent_email, create_abstract, token_headers, test_client
):
    other = create_abstract(dummy_event, 'Another abstract', friendly_id=315, submitter=dummy_user)
    db.session.flush()
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/abstracts/{other.id}/emails/{sent_email.id}', headers=token_headers
    )
    assert resp.status_code == 404
