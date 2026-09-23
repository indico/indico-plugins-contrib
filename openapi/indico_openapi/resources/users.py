# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from flask import request, session
from marshmallow import fields

from indico.modules.admin import RHAdminBase
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
    """Query shared by the endpoints answering about somebody else.

    A profile holds personal data, and the only interface listing the accounts
    of an instance is the user management area, so these endpoints are
    restricted to administrators; every other caller reads their own profile at
    `/users/me`. Deleted users are never returned.
    """

    def _user_query(self):
        return User.query.filter(~User.is_deleted).order_by(User.last_name, User.first_name, User.id)


@json_errors
class RHCurrentUser(RHProtected):
    def _process_GET(self):
        return UserSchema().jsonify(session.user)


@json_errors
class RHUser(UserMixin, RHAdminBase):
    def _process_args(self):
        self.user = self._user_query().filter(User.id == request.view_args['user_id']).first_or_404()

    def _process_GET(self):
        return UserSchema().jsonify(self.user)


@json_errors
class RHUserList(UserMixin, RHListBase, RHAdminBase):
    schema = UserSchema

    def _query(self):
        return self._user_query()

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(rule='/users', name='users', rh=RHUserList, schema=UserSchema, many=True,
             summary='List the user accounts of the instance', tag='Users'),
    Endpoint(rule='/users/me', name='current_user', rh=RHCurrentUser, schema=UserSchema,
             summary='Details of the authenticated user', tag='Users'),
    Endpoint(rule='/users/<int:user_id>', name='user', rh=RHUser, schema=UserSchema,
             summary='Details of one user account of the instance', tag='Users'),
]
