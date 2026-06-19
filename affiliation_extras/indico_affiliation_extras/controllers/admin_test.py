# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from io import BytesIO


def _login(test_client, user):
    with test_client.session_transaction() as sess:
        sess.set_session_user(user)


def test_email_image_upload_returns_url(test_client, db, create_user, no_csrf_check):
    admin = create_user(1, admin=True)
    _login(test_client, admin)

    resp = test_client.post(
        '/admin/plugins/affiliation_extras/representatives/email/image',
        data={'upload': (BytesIO(b'\x89PNG\r\n\x1a\n' + bytes(64)), 'logo.png')},
        content_type='multipart/form-data',
    )

    assert resp.status_code == 200
    assert resp.json['url']
