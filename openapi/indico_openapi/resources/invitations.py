# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from flask import request
from marshmallow import fields

from indico.core.db import db
from indico.core.marshmallow import mm
from indico.modules.events.management.controllers import RHManageEventBase
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.invitations import InvitationState, RegistrationInvitation
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, ListArgs, RHListBase


class RegistrationInvitationSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """Invitation to register through a form.

    The UUID of the invitation is left out: it is the secret in the link the
    invitee received, and whoever holds it may register on their behalf.
    """

    class Meta:
        model = RegistrationInvitation
        fields = (
            'id',
            'registration_form_id',
            'registration_id',
            'state',
            'first_name',
            'last_name',
            'email',
            'affiliation',
            'skip_moderation',
            'skip_access_check',
            'lock_email',
        )
        descriptions = {
            'id': 'Numeric identifier of the invitation, unique across the whole instance.',
            'registration_form_id': 'Identifier of the form the invitee was asked to fill in.',
            'registration_id': 'Identifier of the registration made through the invitation, or `null` until the '
            'invitee accepts.',
            'state': 'Whether the invitee has answered: `pending`, `accepted` or `declined`.',
            'first_name': 'First name of the invitee.',
            'last_name': 'Last name of the invitee.',
            'email': 'Email address the invitation was sent to.',
            'affiliation': 'Affiliation of the invitee, as the organisers typed it.',
            'skip_moderation': 'Whether a registration made through the invitation is accepted without review.',
            'skip_access_check': 'Whether the invitee may register without being allowed to access the event.',
            'lock_email': 'Whether the invitee has to register with the address the invitation was sent to.',
        }

    state = fields.Enum(InvitationState)


class InvitationListArgs(ListArgs):
    state = fields.Enum(
        InvitationState, load_default=None, metadata={'description': 'Only list the invitations in this state.'}
    )


class InvitationMixin:
    """Access checks shared by the invitation endpoints.

    An invitation names somebody who may not have registered yet, and whether
    they were let in without moderation or access checks, which only the
    management pages show. So invitations are served to the registration
    managers of the event and nobody else, invitee included.
    """

    EVENT_FEATURE = 'registration'
    PERMISSION = 'registration'

    def _process_args(self):
        RHManageEventBase._process_args(self)
        self.regform = (
            RegistrationForm.query
            .with_parent(self.event)
            .filter(RegistrationForm.id == request.view_args['regform_id'], ~RegistrationForm.is_deleted)
            .first_or_404()
        )

    def _invitation_query(self):
        return RegistrationInvitation.query.with_parent(self.regform).order_by(
            db.func.lower(RegistrationInvitation.first_name),
            db.func.lower(RegistrationInvitation.last_name),
            RegistrationInvitation.id,
        )


@json_errors
class RHRegistrationInvitation(InvitationMixin, RHManageEventBase):
    def _process_args(self):
        InvitationMixin._process_args(self)
        self.invitation = (
            self
            ._invitation_query()
            .filter(RegistrationInvitation.id == request.view_args['invitation_id'])
            .first_or_404()
        )

    def _process_GET(self):
        return RegistrationInvitationSchema().jsonify(self.invitation)


@json_errors
class RHRegistrationInvitationList(InvitationMixin, RHListBase, RHManageEventBase):
    args_schema = InvitationListArgs
    schema = RegistrationInvitationSchema

    def _query(self, state):
        query = self._invitation_query()
        if state is not None:
            query = query.filter(RegistrationInvitation.state == state)
        return query

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(
        rule='/events/<int:event_id>/registration-forms/<int:regform_id>/invitations',
        name='invitations',
        rh=RHRegistrationInvitationList,
        schema=RegistrationInvitationSchema,
        many=True,
        summary='List the invitations to register through a form',
        tag='Registrations',
    ),
    Endpoint(
        rule='/events/<int:event_id>/registration-forms/<int:regform_id>/invitations/<int:invitation_id>',
        name='invitation',
        rh=RHRegistrationInvitation,
        schema=RegistrationInvitationSchema,
        summary='Details of one invitation to register through a form',
        tag='Registrations',
    ),
]
