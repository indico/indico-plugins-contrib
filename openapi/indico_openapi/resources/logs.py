# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from flask import request, session
from marshmallow import fields, post_dump
from werkzeug.exceptions import Forbidden

from indico.core.db import db
from indico.core.marshmallow import mm
from indico.modules.categories.controllers.base import RHManageCategoryBase
from indico.modules.events.management.controllers import RHManageEventBase
from indico.modules.logs.controllers import _contains
from indico.modules.logs.models.entries import CategoryLogEntry, CategoryLogRealm, EventLogEntry, EventLogRealm, LogKind
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, ListArgs, RHListBase


class LogEntryUserSchema(DescribedFieldsMixin, mm.Schema):
    """Who performed a logged action, as the log itself records them."""

    class Meta:
        descriptions = {
            'full_name': 'Full name of the user, or `null` when no user performed the action.',
            'avatar_url': 'URL of the profile picture of the user, or `null` when no user performed the action.',
        }

    full_name = fields.String(allow_none=True)
    avatar_url = fields.String(allow_none=True)


class LogEntrySchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """One action recorded in the log of an event."""

    class Meta:
        model = EventLogEntry
        fields = ('id', 'logged_dt', 'realm', 'kind', 'module', 'type', 'summary', 'data', 'meta', 'user')
        descriptions = {
            'id': 'Numeric identifier of the entry, unique across the whole instance.',
            'logged_dt': 'Moment the action was performed, in UTC.',
            'realm': 'Area of the event the action belongs to: `event`, `management`, `participants`, '
                     '`reviewing` or `emails`.',
            'kind': 'What the action did: `positive` for something created, `negative` for something removed, '
                    '`change` for something modified, `other` for anything else.',
            'module': 'Part of Indico the action came from, such as `Protection`, in English regardless of the '
                      'language of the caller.',
            'type': 'Shape of `data`: `simple` for a list of values or of changes, `email` for a sent email.',
            'summary': 'One line describing the action, in English regardless of the language of the caller.',
            'data': 'Values the action recorded, as a mapping of label to value. A value given as a three item '
                    'list is a change, holding the old value, the new value and their type.',
            'meta': 'Identifiers of the objects the action was about, such as `registration_id`. They are what '
                    'the filters of this endpoint match on.',
            'user': 'Who performed the action.',
        }

    realm = fields.Enum(EventLogRealm)
    kind = fields.Enum(LogKind)
    data = fields.Raw()
    meta = fields.Raw()
    user = fields.Nested(LogEntryUserSchema)

    @post_dump(pass_original=True)
    def _keep_the_user_shape(self, data, entry, **kwargs):
        if entry.user is None:
            data['user'] = {'full_name': None, 'avatar_url': None}
        return data


class CategoryLogEntrySchema(LogEntrySchema):
    """One action recorded in the log of a category."""

    class Meta(LogEntrySchema.Meta):
        model = CategoryLogEntry
        descriptions = {**LogEntrySchema.Meta.descriptions,
                        'realm': 'Area of the category the action belongs to: `category` for the category itself, '
                                 '`events` for the events held in it.'}

    realm = fields.Enum(CategoryLogRealm)


SEARCHED_TEXT = ('Only list entries matching this text in their module, type or summary, in the name of the user '
                 'who performed the action, or in the addresses, subject and body of a sent email.')


def matching_text(query, model, q):
    """Filter a log query the way the log interface searches it, over the same columns."""
    return query.filter(db.or_(_contains(model.module, q),
                               _contains(model.type, q),
                               _contains(model.summary, q),
                               _contains(db.m.User.first_name + ' ' + db.m.User.last_name, q),
                               _contains(model.data['body'].astext, q),
                               _contains(model.data['subject'].astext, q),
                               _contains(model.data['from'].astext, q),
                               _contains(model.data['to'].astext, q),
                               _contains(model.data['cc'].astext, q))
                        ).outerjoin(db.m.User, db.m.User.id == model.user_id)


class LogListArgs(ListArgs):
    realm = fields.List(fields.Enum(EventLogRealm), load_default=(),
                        metadata={'description': 'Only list entries belonging to these areas of the event.'})
    q = fields.String(load_default=None, metadata={'description': SEARCHED_TEXT})
    registration_id = fields.Integer(load_default=None,
                                     metadata={'description': 'Only list entries about this registration. A caller '
                                                              'who only manages the registrations of the event has '
                                                              'to pass it.'})


class LogMixin:
    """Access checks shared by the log endpoints.

    The log records every management action of an event, including the values
    that changed, so it is served to the managers of the event and to nobody
    else. A caller who only manages its registrations gets the entries of one
    registration, which is the rule the log interface applies as well.
    """

    PERMISSION = 'registration'

    def _check_scope(self, registration_id):
        if not registration_id and not self.event.can_manage(session.user):
            raise Forbidden

    def _entry_query(self):
        return (EventLogEntry.query.with_parent(self.event)
                .order_by(EventLogEntry.logged_dt.desc(), EventLogEntry.id.desc()))


@json_errors
class RHEventLogEntry(LogMixin, RHManageEventBase):
    def _process_args(self):
        RHManageEventBase._process_args(self)
        self.entry = self._entry_query().filter(EventLogEntry.id == request.view_args['entry_id']).first_or_404()

    def _check_access(self):
        RHManageEventBase._check_access(self)
        self._check_scope(self.entry.meta.get('registration_id'))

    def _process_GET(self):
        return LogEntrySchema().jsonify(self.entry)


@json_errors
class RHEventLogEntryList(LogMixin, RHListBase, RHManageEventBase):
    args_schema = LogListArgs
    schema = LogEntrySchema

    def _check_access(self):
        RHManageEventBase._check_access(self)
        self._check_scope(request.args.get('registration_id'))

    def _query(self, realm, q, registration_id):
        query = self._entry_query()
        if realm:
            query = query.filter(EventLogEntry.realm.in_(realm))
        if q:
            query = matching_text(query, EventLogEntry, q)
        if registration_id is not None:
            query = query.filter(EventLogEntry.meta.contains({'registration_id': registration_id}))
        return query

    def _can_access(self, obj):
        return True


class CategoryLogListArgs(ListArgs):
    realm = fields.List(fields.Enum(CategoryLogRealm), load_default=(),
                        metadata={'description': 'Only list entries belonging to these areas of the category.'})
    q = fields.String(load_default=None, metadata={'description': SEARCHED_TEXT})


class CategoryLogMixin:
    """Access checks shared by the category log endpoints.

    The log records every management action of a category, including the values
    that changed, so it is served to the managers of the category and to nobody
    else, which is the rule the log interface applies as well.
    """

    def _entry_query(self):
        return (self.category.log_entries
                .order_by(CategoryLogEntry.logged_dt.desc(), CategoryLogEntry.id.desc()))


@json_errors
class RHCategoryLogEntry(CategoryLogMixin, RHManageCategoryBase):
    def _process_args(self):
        RHManageCategoryBase._process_args(self)
        self.entry = (self._entry_query()
                      .filter(CategoryLogEntry.id == request.view_args['entry_id']).first_or_404())

    def _process_GET(self):
        return CategoryLogEntrySchema().jsonify(self.entry)


@json_errors
class RHCategoryLogEntryList(CategoryLogMixin, RHListBase, RHManageCategoryBase):
    args_schema = CategoryLogListArgs
    schema = CategoryLogEntrySchema

    def _query(self, realm, q):
        query = self._entry_query()
        if realm:
            query = query.filter(CategoryLogEntry.realm.in_(realm))
        if q:
            query = matching_text(query, CategoryLogEntry, q)
        return query

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(rule='/events/<int:event_id>/logs', name='logs', rh=RHEventLogEntryList, schema=LogEntrySchema,
             many=True, summary='List the log entries of an event', tag='Logs'),
    Endpoint(rule='/events/<int:event_id>/logs/<int:entry_id>', name='log_entry', rh=RHEventLogEntry,
             schema=LogEntrySchema, summary='Details of one log entry of an event', tag='Logs'),
    Endpoint(rule='/categories/<int:category_id>/logs', name='category_logs', rh=RHCategoryLogEntryList,
             schema=CategoryLogEntrySchema, many=True, summary='List the log entries of a category', tag='Logs'),
    Endpoint(rule='/categories/<int:category_id>/logs/<int:entry_id>', name='category_log_entry',
             rh=RHCategoryLogEntry, schema=CategoryLogEntrySchema,
             summary='Details of one log entry of a category', tag='Logs'),
]
