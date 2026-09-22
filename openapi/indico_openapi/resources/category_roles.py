# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from operator import itemgetter

from flask import request
from marshmallow import fields, post_dump
from sqlalchemy.orm import joinedload

from indico.core.marshmallow import mm
from indico.modules.categories.controllers.base import RHManageCategoryBase
from indico.modules.categories.models.roles import CategoryRole
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase
from indico_openapi.schemas import MemberSchema


class CategoryRoleSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """Role a category defines to grant permissions to a group of people.

    Events held in the category can grant permissions to a category role, which
    is how a series of events shares one list of people.
    """

    class Meta:
        model = CategoryRole
        fields = ('id', 'category_id', 'name', 'code', 'color', 'members')
        descriptions = {
            'id': 'Numeric identifier of the role, unique across the whole instance.',
            'category_id': 'Identifier of the category defining the role.',
            'name': 'Name of the role, such as `Programme Committee`.',
            'code': 'Short uppercase code of the role, unique within the category, such as `PC`.',
            'color': 'Colour the role is shown in, as a six digit hex triplet without the leading `#`.',
            'members': 'Users holding the role, sorted by identifier.',
        }

    members = fields.List(fields.Nested(MemberSchema))

    @post_dump
    def _sort_members(self, data, **kwargs):
        # the relationship is a set, so without this the order changes from one request to the next
        data['members'].sort(key=itemgetter('id'))
        return data


class CategoryRoleMixin:
    """Query shared by the category role endpoints.

    A role carries the email address of everybody holding it, which is what makes
    it manager only, the same way event roles are.
    """

    def _role_query(self):
        return (CategoryRole.query.with_parent(self.category)
                .options(joinedload('members'))
                .order_by(CategoryRole.code))


@json_errors
class RHCategoryRole(CategoryRoleMixin, RHManageCategoryBase):
    def _process_args(self):
        RHManageCategoryBase._process_args(self)
        self.role = self._role_query().filter(CategoryRole.id == request.view_args['role_id']).first_or_404()

    def _process_GET(self):
        return CategoryRoleSchema().jsonify(self.role)


@json_errors
class RHCategoryRoleList(CategoryRoleMixin, RHListBase, RHManageCategoryBase):
    schema = CategoryRoleSchema

    def _query(self):
        return self._role_query()

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(rule='/categories/<int:category_id>/roles', name='category_roles', rh=RHCategoryRoleList,
             schema=CategoryRoleSchema, many=True, summary='List the roles of a category', tag='Categories'),
    Endpoint(rule='/categories/<int:category_id>/roles/<int:role_id>', name='category_role', rh=RHCategoryRole,
             schema=CategoryRoleSchema, summary='Category role details', tag='Categories'),
]
