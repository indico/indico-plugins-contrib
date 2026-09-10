# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from marshmallow import fields
from sqlalchemy.orm import undefer

from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.core.marshmallow import mm
from indico.modules.categories.controllers.base import RHDisplayCategoryBase
from indico.modules.categories.models.categories import Category
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, ListArgs, RHListBase


class CategorySchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    class Meta:
        model = Category
        fields = ('id', 'title', 'parent_id', 'chain_titles', 'deep_events_count', 'is_protected')
        descriptions = {
            'id': 'Numeric identifier of the category. The root category is always `0`.',
            'title': 'Title of the category.',
            'parent_id': 'Identifier of the category holding this one, or `null` for the root category.',
            'chain_titles': 'Titles of every category from the root down to this one, this one included.',
            'deep_events_count': 'Number of events held in this category and in every category below it.',
            'is_protected': 'Whether reading the category requires permissions beyond being logged in.',
        }

    is_protected = fields.Function(lambda category: category.effective_protection_mode != ProtectionMode.public)


class CategoryListArgs(ListArgs):
    parent_id = fields.Integer(load_default=None,
                               metadata={'description': 'Only list the categories held directly in this one.'})


@json_errors
class RHCategory(RHDisplayCategoryBase):
    _category_query_options = (undefer('chain_titles'), undefer('deep_events_count'))

    def _process_GET(self):
        return CategorySchema().jsonify(self.category)


@json_errors
class RHCategoryList(RHListBase):
    args_schema = CategoryListArgs
    schema = CategorySchema

    def _query(self, parent_id):
        query = (Category.query
                 .filter(~Category.is_deleted)
                 .options(undefer('chain_titles'), undefer('deep_events_count')))
        if parent_id is not None:
            query = query.filter(Category.parent_id == parent_id)
        return query.order_by(Category.position, Category.id)


ENDPOINTS = [
    Endpoint(rule='/categories', name='categories', rh=RHCategoryList, schema=CategorySchema, many=True,
             summary='List categories', tag='Categories'),
    Endpoint(rule='/categories/<int:category_id>', name='category', rh=RHCategory, schema=CategorySchema,
             summary='Category details', tag='Categories'),
]
