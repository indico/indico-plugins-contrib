# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from flask import request, session
from marshmallow import fields, post_dump
from werkzeug.exceptions import Forbidden, NotFound

from indico.core.marshmallow import mm
from indico.modules.events.contributions.models.contributions import Contribution
from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.modules.events.editing.models.editable import Editable, EditableState, EditableType
from indico.modules.events.editing.models.review_conditions import EditingReviewCondition
from indico.modules.events.editing.models.revisions import RevisionType
from indico.modules.events.editing.schemas import EditableSchema as CoreEditableSchema
from indico.modules.events.editing.schemas import EditingFileTypeSchema as CoreEditingFileTypeSchema
from indico.modules.events.editing.schemas import EditingRevisionCommentSchema as CoreEditingCommentSchema
from indico.modules.events.editing.schemas import EditingRevisionFileSchema as CoreEditingFileSchema
from indico.modules.events.editing.schemas import EditingRevisionSchema as CoreEditingRevisionSchema
from indico.modules.events.editing.schemas import EditingTagSchema as CoreEditingTagSchema
from indico.modules.users.schemas import BasicUserSchema
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, ListArgs, RHListBase, jsonify_results
from indico_openapi.resources.papers import ContributionReferenceSchema


ANONYMOUS_USER = {'id': None, 'identifier': None, 'full_name': None, 'anonymous': True}


def visible_revisions(editable):
    """Keep the revisions of an editable the caller is allowed to read, oldest first.

    An undone revision is one the editing team took back, and the timeline only
    draws it for the team itself.
    """
    if editable.can_see_restricted_revisions(session.user):
        return editable.revisions
    return [revision for revision in editable.revisions if not revision.is_undone]


class EditingUserSchema(DescribedFieldsMixin, BasicUserSchema):
    """Whoever acted on an editable, which an event may choose to keep anonymous."""

    class Meta(BasicUserSchema.Meta):
        fields = ('id', 'identifier', 'full_name', 'anonymous')
        descriptions = {
            'id': 'Numeric identifier of the user, or `null` when the name is hidden.',
            'identifier': 'Identifier of the user as used by Indico ACLs, or `null` when the name is hidden.',
            'full_name': 'Full name of the user, or `null` when the name is hidden.',
            'anonymous': 'Whether the event hides who this is, which it does for its editing team.',
        }

    anonymous = fields.Constant(False)


class EditingTagSchema(DescribedFieldsMixin, CoreEditingTagSchema):
    """One tag the editing team marks a revision with."""

    class Meta(CoreEditingTagSchema.Meta):
        fields = ('id', 'code', 'title', 'color', 'verbose_title', 'system')
        descriptions = {
            'id': 'Numeric identifier of the tag, unique across the whole instance.',
            'code': 'Short code shown on the tag, such as `REV`.',
            'title': 'Name of the tag.',
            'color': 'Colour the tag is shown in, as a colour name such as `blue`.',
            'verbose_title': 'Code and name together, which is how the tag is listed.',
            'system': 'Whether Indico manages the tag itself instead of the editing managers.',
        }


class EditingFileTypeSchema(DescribedFieldsMixin, CoreEditingFileTypeSchema):
    """One kind of file a revision of an editable is made of."""

    class Meta(CoreEditingFileTypeSchema.Meta):
        fields = ('id', 'name', 'extensions', 'allow_multiple_files', 'required', 'publishable', 'filename_template')
        descriptions = {
            'id': 'Numeric identifier of the file type, unique across the whole instance.',
            'name': 'Name of the file type, such as `PDF`.',
            'extensions': 'Extensions a file of this type may have, without the dot, or an empty list for any.',
            'allow_multiple_files': 'Whether a revision may carry more than one file of this type.',
            'required': 'Whether a revision has to carry a file of this type.',
            'publishable': 'Whether a file of this type is published with the contribution once accepted.',
            'filename_template': 'Template the files of this type are renamed after, or `null` when kept as '
                                 'uploaded.',
        }


class EditingReviewConditionSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """One combination of file types a revision may be reviewed with."""

    class Meta:
        model = EditingReviewCondition
        fields = ('id', 'file_type_ids')
        descriptions = {
            'id': 'Numeric identifier of the condition, unique across the whole instance.',
            'file_type_ids': 'File types a revision has to carry to meet this condition.',
        }

    file_type_ids = fields.Function(lambda condition: sorted(ft.id for ft in condition.file_types))


class EditingFileSchema(DescribedFieldsMixin, CoreEditingFileSchema):
    """One file uploaded with a revision."""

    class Meta(CoreEditingFileSchema.Meta):
        fields = ('id', 'uuid', 'filename', 'size', 'content_type', 'file_type_id', 'download_url')
        descriptions = {
            'id': 'Numeric identifier of the file.',
            'uuid': 'Identifier the file is read with, which is what `/files/{uuid}` takes.',
            'filename': 'Name of the file, after the template of its type has been applied.',
            'size': 'Size of the file in bytes.',
            'content_type': 'MIME type of the file, such as `application/pdf`.',
            'file_type_id': 'File type the file was uploaded as.',
            'download_url': 'URL the file is downloaded from, relative to the Indico instance.',
        }


class EditingCommentSchema(DescribedFieldsMixin, CoreEditingCommentSchema):
    """One comment left on a revision of an editable."""

    class Meta(CoreEditingCommentSchema.Meta):
        fields = ('id', 'revision_id', 'user', 'text', 'internal', 'system', 'created_dt', 'modified_dt')
        descriptions = {
            'id': 'Numeric identifier of the comment.',
            'revision_id': 'Identifier of the revision the comment was left on.',
            'user': 'User who wrote the comment, or `null` when Indico wrote it itself.',
            'text': 'The comment itself, as Markdown.',
            'internal': 'Whether the comment is only readable by the editing team.',
            'system': 'Whether Indico wrote the comment itself, to record what happened.',
            'created_dt': 'Moment the comment was written, in UTC.',
            'modified_dt': 'Moment the comment was last edited, in UTC, or `null` when never edited.',
        }

    user = fields.Nested(EditingUserSchema)
    text = fields.String()

    @post_dump(pass_original=True)
    def _hide_anonymous_user(self, data, comment, **kwargs):
        if data['user'] and not comment.revision.editable.can_see_editor_names(session.user, comment.user):
            data['user'] = ANONYMOUS_USER
        return data


class EditingRevisionSchema(DescribedFieldsMixin, CoreEditingRevisionSchema):
    """One revision of an editable, which is a set of files plus what was done with them."""

    class Meta(CoreEditingRevisionSchema.Meta):
        fields = ('id', 'created_dt', 'modified_dt', 'user', 'type', 'comment', 'is_undone', 'is_editor_revision',
                  'tags', 'files')
        descriptions = {
            'id': 'Numeric identifier of the revision, unique across the whole instance.',
            'created_dt': 'Moment the revision was created, in UTC.',
            'modified_dt': 'Moment the revision was last changed, in UTC, or `null` when never changed.',
            'user': 'User the revision is the action of, or `null` when Indico created it itself.',
            'type': 'What the revision does: `new`, `ready_for_review`, `needs_submitter_confirmation`, '
                    '`changes_acceptance`, `changes_rejection`, `needs_submitter_changes`, `acceptance`, '
                    '`rejection`, `replacement` or `reset`.',
            'comment': 'Comment left with the revision, as Markdown.',
            'is_undone': 'Whether the revision was undone, which keeps it out of the timeline of the submitter.',
            'is_editor_revision': 'Whether the revision is an action of the editing team rather than of the '
                                  'submitter.',
            'tags': 'Tags the editing team marked the revision with.',
            'files': 'Files the revision is made of.',
        }

    user = fields.Nested(EditingUserSchema)
    type = fields.Enum(RevisionType)
    comment = fields.String()
    is_editor_revision = fields.Boolean()
    tags = fields.List(fields.Nested(EditingTagSchema))
    files = fields.List(fields.Nested(EditingFileSchema))

    @post_dump(pass_original=True)
    def _hide_anonymous_user(self, data, revision, **kwargs):
        if data['user'] and not revision.editable.can_see_editor_names(session.user, revision.user):
            data['user'] = ANONYMOUS_USER
        return data


class EditableSchema(DescribedFieldsMixin, CoreEditableSchema):
    """The paper, slides or poster of a contribution as the editing workflow handles it."""

    class Meta(CoreEditableSchema.Meta):
        fields = ('id', 'type', 'state', 'contribution', 'editor', 'revision_count', 'has_published_revision',
                  'editing_enabled', 'review_conditions_valid', 'last_update_dt')
        descriptions = {
            'id': 'Numeric identifier of the editable, unique across the whole instance.',
            'type': 'What is being edited: `paper`, `slides` or `poster`.',
            'state': 'Where the editable stands: `new`, `ready_for_review`, `needs_submitter_confirmation`, '
                     '`needs_submitter_changes`, `accepted`, `rejected` or `accepted_submitter`.',
            'contribution': 'Contribution the editable belongs to.',
            'editor': 'User assigned to edit it, or `null` when nobody is.',
            'revision_count': 'Number of revisions carrying files.',
            'has_published_revision': 'Whether a revision was published with the contribution.',
            'editing_enabled': 'Whether the event lets the editing team act on this kind of editable.',
            'review_conditions_valid': 'Whether the files of the latest revision meet one of the review conditions.',
            'last_update_dt': 'Moment the editable last changed, in UTC, or `null` when it has no revision.',
            'revisions': 'Revisions of the editable, oldest first.',
        }

    type = fields.Enum(EditableType)
    state = fields.Enum(EditableState)
    contribution = fields.Nested(ContributionReferenceSchema)
    editor = fields.Nested(EditingUserSchema)
    last_update_dt = fields.DateTime()

    @post_dump(pass_original=True)
    def _hide_anonymous_editor(self, data, editable, **kwargs):
        if data['editor'] and not editable.can_see_editor_names(session.user):
            data['editor'] = ANONYMOUS_USER
        return data


class EditableDetailsSchema(EditableSchema):
    class Meta(EditableSchema.Meta):
        fields = (*EditableSchema.Meta.fields, 'revisions')

    revisions = fields.Method('_get_revisions')

    def _get_revisions(self, editable):
        return EditingRevisionSchema(many=True).dump(visible_revisions(editable))


class EditingMixin:
    """Access checks shared by the endpoints of the editing workflow.

    The tags and the file types are read by whoever can see the event, since
    they name what a revision is made of and what it is marked with, while the
    review conditions are read by the editing managers, the audience of the
    page defining them. An editable itself is read by whoever may see its
    timeline.
    """

    EVENT_FEATURE = 'editing'


class EditableTypeMixin(EditingMixin):
    """Locate the kind of editable an endpoint is about."""

    def _process_args(self):
        super()._process_args()
        try:
            self.editable_type = EditableType[request.view_args['editable_type']]
        except KeyError:
            raise NotFound


class EditableMixin(EditableTypeMixin):
    """Access checks shared by the endpoints serving one editable.

    An editable is readable by the people listed on its contribution, by
    whoever may submit it and by the editing team of the event, which is the
    check the timeline makes before rendering itself.
    """

    def _process_args(self):
        super()._process_args()
        contrib = (Contribution.query.with_parent(self.event)
                   .filter(Contribution.id == request.view_args['contrib_id'], ~Contribution.is_deleted)
                   .first_or_404())
        self.editable = next((e for e in contrib.editables if e.type == self.editable_type), None)
        if self.editable is None:
            raise NotFound

    def _check_access(self):
        RHProtectedEventBase._check_access(self)
        if not self.editable.can_see_timeline(session.user):
            raise Forbidden


class EditableListArgs(ListArgs):
    type = fields.Enum(EditableType, load_default=None, attribute='editable_type',
                       metadata={'description': 'Only list the editables of this kind.'})


@json_errors
class RHEditableList(EditingMixin, RHListBase, RHProtectedEventBase):
    args_schema = EditableListArgs
    schema = EditableSchema

    def _query(self, editable_type):
        query = (Editable.query
                 .join(Editable.contribution)
                 .filter(Contribution.event == self.event, ~Contribution.is_deleted)
                 .order_by(Contribution.friendly_id, Editable.type))
        return query.filter(Editable.type == editable_type) if editable_type is not None else query

    def _can_access(self, editable):
        return editable.can_see_timeline(session.user)


@json_errors
class RHEditable(EditableMixin, RHProtectedEventBase):
    def _process_GET(self):
        return EditableDetailsSchema().jsonify(self.editable)


@json_errors
class RHEditableComments(EditableMixin, RHProtectedEventBase):
    def _process_args(self):
        super()._process_args()
        revision_id = request.view_args['revision_id']
        self.revision = next((r for r in visible_revisions(self.editable) if r.id == revision_id), None)
        if self.revision is None:
            raise NotFound

    def _process_GET(self):
        comments = [comment for comment in self.revision.comments
                    if not comment.internal or self.editable.can_use_internal_comments(session.user)]
        return jsonify_results(EditingCommentSchema(many=True), comments)


@json_errors
class RHEditingTags(EditingMixin, RHProtectedEventBase):
    def _process_GET(self):
        return jsonify_results(EditingTagSchema(many=True), self.event.editing_tags)


@json_errors
class RHEditingFileTypes(EditableTypeMixin, RHProtectedEventBase):
    def _process_GET(self):
        file_types = [ft for ft in self.event.editing_file_types if ft.type == self.editable_type]
        return jsonify_results(EditingFileTypeSchema(many=True), file_types)


@json_errors
class RHEditingReviewConditions(EditableTypeMixin, RHProtectedEventBase):
    def _check_access(self):
        RHProtectedEventBase._check_access(self)
        if not self.event.can_manage(session.user, permission='editing_manager'):
            raise Forbidden

    def _process_GET(self):
        conditions = (EditingReviewCondition.query.with_parent(self.event)
                      .filter_by(type=self.editable_type)
                      .order_by(EditingReviewCondition.id)
                      .all())
        return jsonify_results(EditingReviewConditionSchema(many=True), conditions)


ENDPOINTS = [
    Endpoint(rule='/events/<int:event_id>/editables', name='editables', rh=RHEditableList, schema=EditableSchema,
             many=True, summary='List the editables of an event', tag='Editing'),
    Endpoint(rule='/events/<int:event_id>/contributions/<int:contrib_id>/editables/<editable_type>', name='editable',
             rh=RHEditable, schema=EditableDetailsSchema, summary='Editable of a contribution', tag='Editing'),
    Endpoint(rule='/events/<int:event_id>/contributions/<int:contrib_id>/editables/<editable_type>'
                  '/revisions/<int:revision_id>/comments',
             name='editable_comments', rh=RHEditableComments, schema=EditingCommentSchema, many=True,
             summary='List the comments left on a revision of an editable', tag='Editing'),
    Endpoint(rule='/events/<int:event_id>/editing/tags', name='editing_tags', rh=RHEditingTags,
             schema=EditingTagSchema, many=True, summary='List the tags of the editing workflow', tag='Editing'),
    Endpoint(rule='/events/<int:event_id>/editing/<editable_type>/file-types', name='editing_file_types',
             rh=RHEditingFileTypes, schema=EditingFileTypeSchema, many=True,
             summary='List the file types a revision is made of', tag='Editing'),
    Endpoint(rule='/events/<int:event_id>/editing/<editable_type>/review-conditions', name='editing_review_conditions',
             rh=RHEditingReviewConditions, schema=EditingReviewConditionSchema, many=True,
             summary='List the conditions a revision has to meet to be reviewed', tag='Editing'),
]
