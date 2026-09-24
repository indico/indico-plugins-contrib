# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from indico.modules.events.features.util import set_feature_enabled
from indico.modules.events.payment.models.transactions import TransactionStatus


@pytest.fixture(autouse=True)
def registration_enabled(db, dummy_event):
    set_feature_enabled(dummy_event, 'registration', True)
    db.session.flush()


@pytest.fixture
def create_payment(db, dummy_reg, create_transaction):
    def _create(status=TransactionStatus.successful, registration=None, timestamp=None, **kwargs):
        kwargs.setdefault('amount', Decimal('10.50'))
        transaction = create_transaction(status, **kwargs)
        (registration or dummy_reg).transactions.append(transaction)
        if timestamp is not None:
            transaction.timestamp = timestamp
        db.session.flush()
        return transaction

    return _create


@pytest.fixture
def dummy_payment(create_payment):
    return create_payment(timestamp=datetime(2026, 9, 1, 8, 0, tzinfo=UTC))


@pytest.fixture
def registration_manager(db, dummy_event, dummy_user):
    dummy_event.update_principal(dummy_user, permissions={'registration'})
    db.session.flush()


@pytest.mark.usefixtures('event_manager')
def test_payment_details(dummy_event, dummy_reg, dummy_payment, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/payments/{dummy_payment.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json == {
        'id': dummy_payment.id,
        'registration_id': dummy_reg.id,
        'status': 'successful',
        'amount': '10.50',
        'currency': 'USD',
        'provider': '_manual',
        'timestamp': '2026-09-01T08:00:00+00:00',
    }


@pytest.mark.usefixtures('event_manager')
def test_payment_list_is_newest_first(dummy_event, dummy_payment, create_payment, token_headers, test_client):
    later = create_payment(TransactionStatus.cancelled, timestamp=datetime(2026, 9, 2, 8, 0, tzinfo=UTC))
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/payments', headers=token_headers)
    assert resp.status_code == 200
    assert [payment['id'] for payment in resp.json['results']] == [later.id, dummy_payment.id]
    assert resp.json['count'] == 2


@pytest.mark.usefixtures('event_manager')
def test_payment_list_filters_by_registration(
    dummy_event,
    dummy_regform,
    dummy_payment,
    create_payment,
    create_registration,
    create_user,
    db,
    token_headers,
    test_client,
):
    other_reg = create_registration(create_user(43), dummy_regform)
    db.session.add(other_reg)
    db.session.flush()
    other_payment = create_payment(registration=other_reg, timestamp=datetime(2026, 9, 2, 8, 0, tzinfo=UTC))
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/payments?registration_id={other_reg.id}', headers=token_headers
    )
    assert [payment['id'] for payment in resp.json['results']] == [other_payment.id]


@pytest.mark.usefixtures('event_manager')
def test_payment_list_filters_by_status(dummy_event, dummy_payment, create_payment, token_headers, test_client):
    pending = create_payment(TransactionStatus.pending, timestamp=datetime(2026, 9, 2, 8, 0, tzinfo=UTC))
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/payments?status=pending', headers=token_headers)
    assert [payment['id'] for payment in resp.json['results']] == [pending.id]


@pytest.mark.usefixtures('registration_manager')
def test_registration_managers_can_see_payments(dummy_event, dummy_payment, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/payments', headers=token_headers)
    assert resp.status_code == 200
    assert [payment['id'] for payment in resp.json['results']] == [dummy_payment.id]


def test_payments_are_manager_only_even_for_the_registrant(
    dummy_event, dummy_reg, dummy_payment, dummy_user, token_headers, test_client
):
    assert dummy_reg.user == dummy_user
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/payments/{dummy_payment.id}', headers=token_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/payments', headers=token_headers)
    assert resp.status_code == 403


@pytest.mark.usefixtures('event_manager')
def test_payments_need_the_registration_feature(db, dummy_event, dummy_payment, token_headers, test_client):
    set_feature_enabled(dummy_event, 'registration', False)
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/payments', headers=token_headers)
    assert resp.status_code == 404


@pytest.mark.usefixtures('event_manager')
def test_payment_of_a_deleted_registration_is_not_served(
    db, dummy_event, dummy_reg, dummy_payment, token_headers, test_client
):
    dummy_reg.is_deleted = True
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/payments', headers=token_headers)
    assert resp.json['results'] == []
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/payments/{dummy_payment.id}', headers=token_headers)
    assert resp.status_code == 404


def test_payment_of_another_event_is_not_found(db, dummy_payment, create_event, dummy_user, token_headers, test_client):
    other = create_event()
    other.update_principal(dummy_user, full_access=True)
    set_feature_enabled(other, 'registration', True)
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{other.id}/payments/{dummy_payment.id}', headers=token_headers)
    assert resp.status_code == 404
