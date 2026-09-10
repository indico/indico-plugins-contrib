# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from flask import request, session
from marshmallow import fields
from werkzeug.exceptions import Forbidden

from indico.modules.users import User
from indico.modules.users.schemas import UserSchema as CoreUserSchema
from indico.web.rh import RHProtected, json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase
from indico_openapi.schemas import AffiliationSchema, UserReferenceSchema


class UserSchema(DescribedFieldsMixin, CoreUserSchema):
    class Meta(CoreUserSchema.Meta):
        fields = CoreUserSchema.Meta.fields
        descriptions = {
            **UserReferenceSchema.Meta.descriptions,
            'affiliation_id': 'Identifier of the predefined affiliation, or `null` when typed by hand.',
            'phone': 'Phone number of the user.',
        }

    affiliation_meta = fields.Nested(AffiliationSchema, attribute='affiliation_link')


class UserMixin:
    """Access checks shared by the user endpoints.

    A profile holds personal data, so it is only readable by the user it
    belongs to and by Indico administrators. This is the same rule the profile
    page applies. Deleted users are never returned.
    """

    def _user_query(self):
        return User.query.filter(~User.is_deleted).order_by(User.last_name, User.first_name, User.id)

    def _can_see(self, user):
        return user.can_be_modified(session.user)


@json_errors
class RHCurrentUser(RHProtected):
    def _process_GET(self):
        return UserSchema().jsonify(session.user)


@json_errors
class RHUser(UserMixin, RHProtected):
    def _process_args(self):
        self.user = self._user_query().filter(User.id == request.view_args['user_id']).first_or_404()

    def _check_access(self):
        RHProtected._check_access(self)
        if not self._can_see(self.user):
            raise Forbidden

    def _process_GET(self):
        return UserSchema().jsonify(self.user)


@json_errors
class RHUserList(UserMixin, RHListBase, RHProtected):
    schema = UserSchema

    def _query(self):
        query = self._user_query()
        if not session.user.is_admin:
            query = query.filter(User.id == session.user.id)
        return query

    def _can_access(self, obj):
        return self._can_see(obj)


ENDPOINTS = [
    Endpoint(rule='/users', name='users', rh=RHUserList, schema=UserSchema, many=True,
             summary='List users', tag='Users'),
    Endpoint(rule='/users/me', name='current_user', rh=RHCurrentUser, schema=UserSchema,
             summary='Details of the authenticated user', tag='Users'),
    Endpoint(rule='/users/<int:user_id>', name='user', rh=RHUser, schema=UserSchema,
             summary='User details', tag='Users'),
]
