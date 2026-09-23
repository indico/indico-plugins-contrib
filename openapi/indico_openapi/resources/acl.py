# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from flask import request, session
from marshmallow import fields
from werkzeug.exceptions import Forbidden, NotFound

from indico.core.db.sqlalchemy.principals import PrincipalType
from indico.core.marshmallow import mm
from indico.core.permissions import get_available_permissions
from indico.modules.attachments.models.attachments import Attachment
from indico.modules.attachments.util import can_manage_attachments
from indico.modules.categories.controllers.base import RHDisplayCategoryBase
from indico.modules.categories.models.categories import Category
from indico.modules.events.contributions.models.contributions import Contribution
from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.modules.events.layout.models.menu import MenuEntry
from indico.modules.events.models.events import Event
from indico.modules.events.sessions.models.sessions import Session
from indico.modules.events.tracks.models.tracks import Track
from indico.modules.rb.models.locations import Location
from indico.modules.rb.models.rooms import Room
from indico.web.rh import RHProtected, json_errors

from indico_openapi.resources.attachments import AttachmentMixin
from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, jsonify_results
from indico_openapi.resources.contributions import RHContribution
from indico_openapi.resources.locations import RHLocation
from indico_openapi.resources.rooms import RHRoom
from indico_openapi.resources.sessions import RHSession
from indico_openapi.resources.subcontributions import RHSubContribution
from indico_openapi.resources.tracks import RHTrack


TAG = 'Permissions'

PERMISSION_OBJECTS = {
    'category': Category,
    'event': Event,
    'session': Session,
    'contribution': Contribution,
    'track': Track,
    'room': Room,
    'location': Location,
}

PRINCIPAL_TYPES = ('`user` for a single account, `local_group` for a group of the instance, `multipass_group` for '
                   'a group of an external provider, `email` for an address no account has claimed yet, `network` '
                   'for a range of IP addresses, `event_role` and `category_role` for a role of the event or of '
                   'the category holding it, `registration_form` for everybody registered through that form')


def granted_permissions(entry):
    """List the permissions of an entry that its object still defines.

    Nothing removes a permission from the array when the module registering it
    is gone, and a name no longer registered grants nothing, so the answer only
    holds what the object understands.
    """
    return sorted(set(entry.permissions) & set(get_available_permissions(type(entry).principal_for_obj)))


class ACLEntrySchema(DescribedFieldsMixin, mm.Schema):
    """One principal named in the ACL of an object."""

    class Meta:
        descriptions = {
            'type': f'Kind of principal the entry names: {PRINCIPAL_TYPES}.',
            'identifier': 'Identifier of the principal, such as `User:42`, `Group::7`, `EventRole:3` or '
                          '`Email:someone@example.org`.',
            'name': 'Name of the principal, as Indico shows it on the protection page.',
        }

    type = fields.Enum(PrincipalType)
    identifier = fields.Function(lambda entry: entry.principal.persistent_identifier)
    name = fields.Function(lambda entry: entry.principal.name)


class PermissionACLEntrySchema(ACLEntrySchema):
    """One principal named in the ACL of an object that grants permissions."""

    class Meta(ACLEntrySchema.Meta):
        descriptions = ACLEntrySchema.Meta.descriptions | {
            'read_access': 'Whether the principal may read the object while it is protected.',
            'full_access': 'Whether the principal manages the object, which covers every permission below.',
            'permissions': 'Names of the permissions granted on top of reading, such as `["submit"]`. The '
                           '`/permissions` endpoint describes what each name allows.',
        }

    read_access = fields.Boolean()
    full_access = fields.Boolean()
    permissions = fields.Function(granted_permissions)


class PermissionSchema(DescribedFieldsMixin, mm.Schema):
    """One permission an ACL entry of a given kind of object can grant."""

    class Meta:
        descriptions = {
            'object_type': 'Kind of object the permission applies to, such as `event`.',
            'name': 'Name the permission is stored under in an ACL entry.',
            'title': 'Name of the permission, as Indico shows it on the protection page.',
            'description': 'What the permission allows, or `null` when Indico documents it nowhere.',
            'user_selectable': 'Whether the protection page offers the permission, as opposed to a permission '
                               'only another part of Indico grants.',
            'default': 'Whether the permission is the one given to a principal added with no choice made.',
            'color': 'Colour Indico paints the permission with, or `null` for the default one.',
        }

    object_type = fields.String()
    name = fields.String()
    title = fields.String()
    description = fields.String(allow_none=True)
    user_selectable = fields.Boolean()
    default = fields.Boolean()
    color = fields.String(allow_none=True)


class ACLMixin:
    """Serve the principals an object names in its own ACL.

    Indico shows an ACL on the protection page of its object, which only the
    managers of that object reach, so every endpoint here answers the same
    audience. What a parent grants is not repeated: the caller walks up the
    chain to collect it, exactly as the access check does.
    """

    schema = PermissionACLEntrySchema

    def _process_args(self):
        super()._process_args()
        self.acl_object = self._find_acl_object()

    def _find_acl_object(self):
        raise NotImplementedError

    def _can_read_acl(self):
        return self.acl_object.can_manage(session.user)

    def _check_access(self):
        super()._check_access()
        if not self._can_read_acl():
            raise Forbidden

    def _process_GET(self):
        entries = sorted(self.acl_object.acl_entries,
                         key=lambda entry: (entry.principal.principal_order, entry.principal.name.lower()))
        return jsonify_results(self.schema(many=True), entries)


class MembershipACLMixin(ACLMixin):
    """An ACL that names principals and grants them nothing beyond reading."""

    schema = ACLEntrySchema


class AttachmentACLMixin(MembershipACLMixin, AttachmentMixin):
    def _find_acl_object(self):
        return (self._attachment_query()
                .filter(Attachment.id == request.view_args['attachment_id'])
                .first_or_404())

    def _can_read_acl(self):
        return can_manage_attachments(self.acl_object.folder.object, session.user)


class AttachmentFolderACLMixin(MembershipACLMixin, AttachmentMixin):
    def _find_acl_object(self):
        folder = (self.linked_object.attachment_folders
                  .filter_by(id=request.view_args['folder_id'], is_deleted=False)
                  .first())
        if folder is None:
            raise NotFound
        return folder

    def _can_read_acl(self):
        return can_manage_attachments(self.acl_object.object, session.user)


@json_errors
class RHCategoryACL(ACLMixin, RHDisplayCategoryBase):
    def _find_acl_object(self):
        return self.category


@json_errors
class RHEventACL(ACLMixin, RHProtectedEventBase):
    def _find_acl_object(self):
        return self.event


@json_errors
class RHSessionACL(ACLMixin, RHSession):
    def _find_acl_object(self):
        return self.sess


@json_errors
class RHContributionACL(ACLMixin, RHContribution):
    def _find_acl_object(self):
        return self.contrib


@json_errors
class RHTrackACL(ACLMixin, RHTrack):
    def _find_acl_object(self):
        return self.track

    def _can_read_acl(self):
        # a track is managed from the programme of the event, and its own entries
        # only hand out the permissions of the abstract reviewing workflow
        return self.event.can_manage(session.user)


@json_errors
class RHRoomACL(ACLMixin, RHRoom):
    def _find_acl_object(self):
        return self.room


@json_errors
class RHLocationACL(ACLMixin, RHLocation):
    def _find_acl_object(self):
        return self.location


@json_errors
class RHMenuEntryACL(MembershipACLMixin, RHProtectedEventBase):
    def _find_acl_object(self):
        return (MenuEntry.query
                .filter_by(event_id=self.event.id, id=request.view_args['entry_id'])
                .first_or_404())

    def _can_read_acl(self):
        return self.event.can_manage(session.user)


@json_errors
class RHEventAttachmentACL(AttachmentACLMixin, RHProtectedEventBase):
    @property
    def linked_object(self):
        return self.event


@json_errors
class RHEventAttachmentFolderACL(AttachmentFolderACLMixin, RHProtectedEventBase):
    @property
    def linked_object(self):
        return self.event


@json_errors
class RHSessionAttachmentACL(AttachmentACLMixin, RHSession):
    @property
    def linked_object(self):
        return self.sess


@json_errors
class RHSessionAttachmentFolderACL(AttachmentFolderACLMixin, RHSession):
    @property
    def linked_object(self):
        return self.sess


@json_errors
class RHContributionAttachmentACL(AttachmentACLMixin, RHContribution):
    @property
    def linked_object(self):
        return self.contrib


@json_errors
class RHContributionAttachmentFolderACL(AttachmentFolderACLMixin, RHContribution):
    @property
    def linked_object(self):
        return self.contrib


@json_errors
class RHSubContributionAttachmentACL(AttachmentACLMixin, RHSubContribution):
    @property
    def linked_object(self):
        return self.subcontrib


@json_errors
class RHSubContributionAttachmentFolderACL(AttachmentFolderACLMixin, RHSubContribution):
    @property
    def linked_object(self):
        return self.subcontrib


@json_errors
class RHCategoryAttachmentACL(AttachmentACLMixin, RHDisplayCategoryBase):
    @property
    def linked_object(self):
        return self.category


@json_errors
class RHCategoryAttachmentFolderACL(AttachmentFolderACLMixin, RHDisplayCategoryBase):
    @property
    def linked_object(self):
        return self.category


@json_errors
class RHPermissionList(RHProtected):
    def _process_GET(self):
        permissions = [
            {
                'object_type': object_type,
                'name': permission.name,
                'title': str(permission.friendly_name),
                'description': str(permission.description) if permission.description else None,
                'user_selectable': permission.user_selectable,
                'default': permission.default,
                'color': permission.color,
            }
            for object_type, model in PERMISSION_OBJECTS.items()
            for permission in sorted(get_available_permissions(model).values(), key=lambda p: p.name)
        ]
        return jsonify_results(PermissionSchema(many=True), permissions)


_CONTRIB = '/events/<int:event_id>/contributions/<int:contrib_id>'
_SUBCONTRIB = f'{_CONTRIB}/subcontributions/<int:subcontrib_id>'
_SESSION = '/events/<int:event_id>/sessions/<int:session_id>'

ENDPOINTS = [
    Endpoint(rule='/permissions', name='permissions', rh=RHPermissionList, schema=PermissionSchema, many=True,
             summary='List the permissions an ACL entry can grant', tag=TAG),
    Endpoint(rule='/categories/<int:category_id>/acl', name='category_acl', rh=RHCategoryACL,
             schema=PermissionACLEntrySchema, many=True, summary='List the ACL of a category', tag=TAG),
    Endpoint(rule='/events/<int:event_id>/acl', name='event_acl', rh=RHEventACL, schema=PermissionACLEntrySchema,
             many=True, summary='List the ACL of an event', tag=TAG),
    Endpoint(rule=f'{_SESSION}/acl', name='session_acl', rh=RHSessionACL, schema=PermissionACLEntrySchema,
             many=True, summary='List the ACL of a session', tag=TAG),
    Endpoint(rule=f'{_CONTRIB}/acl', name='contribution_acl', rh=RHContributionACL,
             schema=PermissionACLEntrySchema, many=True, summary='List the ACL of a contribution', tag=TAG),
    Endpoint(rule='/events/<int:event_id>/tracks/<int:track_id>/acl', name='track_acl', rh=RHTrackACL,
             schema=PermissionACLEntrySchema, many=True, summary='List the ACL of a track', tag=TAG),
    Endpoint(rule='/rooms/<int:room_id>/acl', name='room_acl', rh=RHRoomACL, schema=PermissionACLEntrySchema,
             many=True, summary='List the ACL of a room', tag=TAG),
    Endpoint(rule='/locations/<int:location_id>/acl', name='location_acl', rh=RHLocationACL,
             schema=PermissionACLEntrySchema, many=True, summary='List the ACL of a location', tag=TAG),
    Endpoint(rule='/events/<int:event_id>/menu/<int:entry_id>/acl', name='menu_entry_acl', rh=RHMenuEntryACL,
             schema=ACLEntrySchema, many=True, summary='List the ACL of a menu entry', tag=TAG),
    Endpoint(rule='/events/<int:event_id>/attachments/<int:attachment_id>/acl', name='event_attachment_acl',
             rh=RHEventAttachmentACL, schema=ACLEntrySchema, many=True,
             summary='List the ACL of an attachment', tag=TAG),
    Endpoint(rule='/events/<int:event_id>/attachment-folders/<int:folder_id>/acl', name='event_folder_acl',
             rh=RHEventAttachmentFolderACL, schema=ACLEntrySchema, many=True,
             summary='List the ACL of an attachment folder', tag=TAG),
    Endpoint(rule=f'{_SESSION}/attachments/<int:attachment_id>/acl', name='session_attachment_acl',
             rh=RHSessionAttachmentACL, schema=ACLEntrySchema, many=True,
             summary='List the ACL of an attachment', tag=TAG),
    Endpoint(rule=f'{_SESSION}/attachment-folders/<int:folder_id>/acl', name='session_folder_acl',
             rh=RHSessionAttachmentFolderACL, schema=ACLEntrySchema, many=True,
             summary='List the ACL of an attachment folder', tag=TAG),
    Endpoint(rule=f'{_CONTRIB}/attachments/<int:attachment_id>/acl', name='contribution_attachment_acl',
             rh=RHContributionAttachmentACL, schema=ACLEntrySchema, many=True,
             summary='List the ACL of an attachment', tag=TAG),
    Endpoint(rule=f'{_CONTRIB}/attachment-folders/<int:folder_id>/acl', name='contribution_folder_acl',
             rh=RHContributionAttachmentFolderACL, schema=ACLEntrySchema, many=True,
             summary='List the ACL of an attachment folder', tag=TAG),
    Endpoint(rule=f'{_SUBCONTRIB}/attachments/<int:attachment_id>/acl', name='subcontribution_attachment_acl',
             rh=RHSubContributionAttachmentACL, schema=ACLEntrySchema, many=True,
             summary='List the ACL of an attachment', tag=TAG),
    Endpoint(rule=f'{_SUBCONTRIB}/attachment-folders/<int:folder_id>/acl', name='subcontribution_folder_acl',
             rh=RHSubContributionAttachmentFolderACL, schema=ACLEntrySchema, many=True,
             summary='List the ACL of an attachment folder', tag=TAG),
    Endpoint(rule='/categories/<int:category_id>/attachments/<int:attachment_id>/acl', name='category_attachment_acl',
             rh=RHCategoryAttachmentACL, schema=ACLEntrySchema, many=True,
             summary='List the ACL of an attachment', tag=TAG),
    Endpoint(rule='/categories/<int:category_id>/attachment-folders/<int:folder_id>/acl', name='category_folder_acl',
             rh=RHCategoryAttachmentFolderACL, schema=ACLEntrySchema, many=True,
             summary='List the ACL of an attachment folder', tag=TAG),
]
