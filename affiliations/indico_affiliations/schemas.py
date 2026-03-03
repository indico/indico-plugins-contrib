# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from marshmallow import ValidationError, fields, validate, validates
from sqlalchemy import func

from indico.core.marshmallow import mm
from indico.util.i18n import _
from indico.util.marshmallow import LowercaseString, ModelList, not_empty
from indico.util.string import validate_email
from indico.web.forms.colors import get_sui_colors

from indico_affiliations.models.groups import AffiliationGroup
from indico_affiliations.models.tags import AffiliationTag


class AffiliationGroupSchema(mm.SQLAlchemyAutoSchema):
    class Meta:
        model = AffiliationGroup
        fields = ('id', 'name', 'code', 'tags', 'meta', 'system')

    tags = ModelList(AffiliationTag)
    meta = fields.Dict()


class AffiliationGroupArgs(mm.Schema):
    class Meta:
        rh_context = ('group',)

    code = fields.String(required=True, validate=not_empty)
    name = fields.String(required=True, validate=not_empty)
    tags = ModelList(AffiliationTag, filter_deleted=True, collection_class=set)
    meta = fields.Dict()

    @validates('code')
    def _check_for_unique_group_code(self, code, **kwargs):
        query = AffiliationGroup.query.filter(~AffiliationGroup.is_deleted,
                                              func.lower(AffiliationGroup.code) == code.lower())
        if group := self.context['group']:
            query = query.filter(AffiliationGroup.id != group.id)
        if query.has_rows():
            raise ValidationError('Group code must be unique')


class AffiliationTagSchema(mm.SQLAlchemyAutoSchema):
    class Meta:
        model = AffiliationTag
        fields = ('id', 'name', 'code', 'color')


class AffiliationTagArgs(mm.Schema):
    class Meta:
        rh_context = ('tag',)

    code = fields.String(required=True, validate=not_empty)
    name = fields.String(required=True, validate=not_empty)
    color = fields.String(required=True, validate=validate.OneOf(get_sui_colors()))

    @validates('code')
    def _check_for_unique_tag_code(self, code, **kwargs):
        tag = self.context['tag']
        query = AffiliationTag.query.filter(~AffiliationTag.is_deleted, func.lower(AffiliationTag.code) == code.lower())
        if tag:
            query = query.filter(AffiliationTag.id != tag.id)
        if query.has_rows():
            raise ValidationError('Tag code must be unique')


class AffiliationExtraAttrsArgs(mm.Schema):
    contact_emails = fields.List(LowercaseString())
    groups = ModelList(AffiliationGroup, filter_deleted=True, collection_class=set)
    tags = ModelList(AffiliationTag, filter_deleted=True, collection_class=set)

    @validates('contact_emails')
    def _validate_contact_emails(self, emails, **kwargs):
        for email in emails:
            if not validate_email(email):
                raise ValidationError(_('Invalid email address: {email}').format(email=email))
