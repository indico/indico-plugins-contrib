# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


import hashlib

from flask import request, session
from marshmallow import fields, post_dump
from werkzeug.exceptions import Forbidden

from indico.modules.events.contributions import contribution_settings
from indico.modules.events.contributions.models.persons import AuthorType
from indico.modules.events.contributions.util import has_contributions_with_user_as_submitter
from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.modules.events.models.persons import EventPerson
from indico.modules.events.persons.schemas import EventPersonSchema as CoreEventPersonSchema
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase


ROLE_ORDER = ('chairperson', 'convener', 'speaker', 'author')


class EventPersonSchema(DescribedFieldsMixin, CoreEventPersonSchema):
    class Meta(CoreEventPersonSchema.Meta):
        fields = ('id', 'first_name', 'last_name', 'affiliation', 'email', 'email_hash', 'roles')
        descriptions = {
            'id': 'Numeric identifier of the person within the event, shared by everything they take part in.',
            'first_name': 'First name of the person.',
            'last_name': 'Last name of the person.',
            'affiliation': 'Affiliation as free text, which is what gets displayed.',
            'email': 'Email address. Only present for users who can manage the event.',
            'email_hash': 'MD5 hash of the email address, so an avatar can be fetched without exposing the address.',
            'roles': 'What the person does in the event: `chairperson`, `convener`, `speaker` or `author`. '
                     'Only roles the requesting user can see are listed.',
        }

    email_hash = fields.Function(lambda p: hashlib.md5(p.email.encode()).hexdigest() if p.email else None)
    roles = fields.Function(lambda p, context: sorted(context['roles'][p.id], key=ROLE_ORDER.index))

    @post_dump
    def _hide_sensitive_data(self, data, **kwargs):
        if self.context.get('hide_restricted_data'):
            del data['email']
        return data


class PersonMixin:
    """Access checks shared by the event person endpoints.

    A person is exposed through the things they take part in, so they are only
    visible while at least one of their links is: the event itself for a
    chairperson, the contribution for a speaker or author, the session for a
    convener. Contact details are reserved for event managers.
    """

    def _contributions_published(self):
        return (contribution_settings.get(self.event, 'published') or
                self.event.can_manage(session.user, permission='contributions') or
                has_contributions_with_user_as_submitter(self.event, session.user))

    def _visible_roles(self, person):
        user = session.user
        roles = set()
        if person.event_links:
            roles.add('chairperson')
        if self._contributions_published():
            for link in person.contribution_links:
                if link.contribution.is_deleted or not link.contribution.can_access(user):
                    continue
                if link.is_speaker:
                    roles.add('speaker')
                if link.author_type != AuthorType.none:
                    roles.add('author')
            for link in person.subcontribution_links:
                subcontrib = link.subcontribution
                if (not subcontrib.is_deleted and not subcontrib.contribution.is_deleted
                        and subcontrib.contribution.can_access(user)):
                    roles.add('speaker')
        for link in person.session_block_links:
            if link.session_block.session.can_access(user):
                roles.add('convener')
        return roles

    def _person_query(self):
        return (EventPerson.query.with_parent(self.event)
                .order_by(EventPerson.last_name, EventPerson.first_name, EventPerson.id))

    def _schema(self, roles, **kwargs):
        return EventPersonSchema(context={'roles': roles,
                                          'hide_restricted_data': not self.event.can_manage(session.user)},
                                 **kwargs)


@json_errors
class RHEventPerson(PersonMixin, RHProtectedEventBase):
    def _process_args(self):
        RHProtectedEventBase._process_args(self)
        self.person = self._person_query().filter(EventPerson.id == request.view_args['person_id']).first_or_404()

    def _check_access(self):
        RHProtectedEventBase._check_access(self)
        self.roles = self._visible_roles(self.person)
        if not self.roles:
            raise Forbidden

    def _process_GET(self):
        return self._schema({self.person.id: self.roles}).jsonify(self.person)


@json_errors
class RHEventPersonList(PersonMixin, RHListBase, RHProtectedEventBase):
    schema = EventPersonSchema

    def _process_args(self):
        RHProtectedEventBase._process_args(self)
        self.roles = {}

    def _query(self):
        return self._person_query()

    def _can_access(self, obj):
        if roles := self._visible_roles(obj):
            self.roles[obj.id] = roles
            return True
        return False

    def _dump_schema(self):
        return self._schema(self.roles, many=True)


ENDPOINTS = [
    Endpoint(rule='/events/<int:event_id>/persons', name='persons', rh=RHEventPersonList, schema=EventPersonSchema,
             many=True, summary='List the people taking part in an event', tag='Persons'),
    Endpoint(rule='/events/<int:event_id>/persons/<int:person_id>', name='person', rh=RHEventPerson,
             schema=EventPersonSchema, summary='Event person details', tag='Persons'),
]
