# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from indico.core.db import db
from indico.modules.users.models.affiliations import Affiliation

from indico_patcher import patch


@patch(Affiliation)
class _Affiliation:
    contact_emails = db.Column(
        db.ARRAY(db.String),
        nullable=False,
        default=[]
    )
