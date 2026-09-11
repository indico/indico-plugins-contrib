# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from flask import request, session
from marshmallow import fields
from werkzeug.exceptions import Forbidden

from indico.core.marshmallow import mm
from indico.modules.events.controllers.base import RHProtectedEventBase
from indico.modules.events.layout import layout_settings
from indico.modules.events.layout.models.images import ImageFile
from indico.modules.events.layout.models.menu import EventPage, MenuEntry, MenuEntryType
from indico.modules.events.layout.util import get_css_url, get_js_url, menu_entries_for_event
from indico.modules.events.management.controllers import RHManageEventBase
from indico.modules.users.models.users import NameFormat
from indico.web.flask.util import url_for
from indico.web.rh import json_errors

from indico_openapi.resources.base import DescribedFieldsMixin, Endpoint, RHListBase, jsonify_results


SETTING_FIELDS = ('is_searchable', 'show_nav_bar', 'show_social_badges', 'show_banner', 'header_logo_as_banner',
                  'header_text_color', 'header_background_color', 'name_format', 'timetable_theme_settings',
                  'timetable_by_room', 'timetable_detailed', 'show_vc_rooms')


def _layout_data(event):
    settings = layout_settings.get_all(event)
    return {
        'event_id': event.id,
        'theme': settings['theme'],
        'css_url': get_css_url(event),
        'js_url': get_js_url(event),
        'logo_url': event.logo_url if event.has_logo else None,
        # the page only renders the announcement while it is published, and a draft must stay hidden
        'announcement': settings['announcement'] if settings['show_announcement'] else None,
        'timetable_theme': event.theme,
        **{name: settings[name] for name in SETTING_FIELDS},
    }


class VisibleEntries(fields.List):
    """Serialize the child entries the caller is allowed to see, and only those.

    A hidden entry cannot be dumped at all: one whose definition is no longer
    provided by Indico has neither a title nor a URL to serialize.
    """

    def get_value(self, obj, attr, **kwargs):
        return [entry for entry in obj.children if entry.is_visible]


class EventLayoutSchema(DescribedFieldsMixin, mm.Schema):
    """How the page of an event looks.

    Core has no schema for this: the management form writes the settings one by
    one and the display page reads them the same way. The settings only a
    manager acts on, such as whether a custom stylesheet or a custom menu is in
    use, are left out; what the page ends up rendering is served instead.
    """

    class Meta:
        descriptions = {
            'event_id': 'Identifier of the event the settings belong to.',
            'theme': 'Identifier of the conference theme the event uses, or `null` when it uses the default look. '
                     'A theme coming from a plugin is prefixed with the plugin name, such as `mytheme:dark`.',
            'css_url': 'URL of the stylesheet the event page loads, relative to the Indico instance, or `null` '
                       'when the event adds no stylesheet of its own.',
            'js_url': 'URL of the script the conference theme loads, relative to the Indico instance, or `null` '
                      'when the theme has none.',
            'logo_url': 'URL of the logo of the event, relative to the Indico instance, or `null` when the event '
                        'has no logo.',
            'announcement': 'Text shown at the top of the event page, or `null` when the event announces nothing.',
            'is_searchable': 'Whether search engines are allowed to index the event.',
            'show_nav_bar': 'Whether the page shows the navigation bar.',
            'show_social_badges': 'Whether the page shows the social network badges.',
            'show_banner': 'Whether the header of the page shows the banner of the event.',
            'header_logo_as_banner': 'Whether the banner is the logo of the event rather than a separate image.',
            'header_text_color': 'Colour of the text in the header, as a hex triplet such as `#ffffff`, or an '
                                 'empty string when the theme decides.',
            'header_background_color': 'Colour of the background of the header, as a hex triplet such as '
                                       '`#000000`, or an empty string when the theme decides.',
            'name_format': 'How the names of people are rendered: `first_last`, `last_first`, `last_f`, `f_last` '
                           'or any of those with `_upper` appended, or `null` to follow the instance default.',
            'timetable_theme': 'Identifier of the theme the timetable is rendered with, falling back to the '
                               'default of this event type.',
            'timetable_theme_settings': 'Options of the timetable theme the event overrides, as a mapping of '
                                        'option name to value.',
            'timetable_by_room': 'Whether the timetable opens grouped by room instead of by day.',
            'timetable_detailed': 'Whether the timetable opens in its detailed view.',
            'show_vc_rooms': 'Whether the timetable shows the videoconference rooms of the event.',
        }

    event_id = fields.Integer()
    theme = fields.String(allow_none=True)
    css_url = fields.String(allow_none=True)
    js_url = fields.String(allow_none=True)
    logo_url = fields.String(allow_none=True)
    announcement = fields.String(allow_none=True)
    is_searchable = fields.Boolean()
    show_nav_bar = fields.Boolean()
    show_social_badges = fields.Boolean()
    show_banner = fields.Boolean()
    header_logo_as_banner = fields.Boolean()
    header_text_color = fields.String()
    header_background_color = fields.String()
    name_format = fields.Enum(NameFormat, allow_none=True)
    timetable_theme = fields.String()
    timetable_theme_settings = fields.Dict(keys=fields.String())
    timetable_by_room = fields.Boolean()
    timetable_detailed = fields.Boolean()
    show_vc_rooms = fields.Boolean()


class MenuEntrySchema(DescribedFieldsMixin, mm.Schema):
    """One item of the menu of an event, with the items nested under it.

    Core has no schema for this either, and the entries are not necessarily
    rows: unless the organisers customised the menu, Indico builds it in memory
    from the modules that contribute to it. The identifier of an entry is
    therefore not served, since a transient entry has none; `name` identifies
    the entries Indico defines and `page_id` the pages the organisers wrote.
    """

    class Meta:
        descriptions = {
            'name': 'Identifier of the entry within the event for the entries Indico defines, such as '
                    '`timetable`, or `null` for an entry added by the organisers.',
            'title': 'Title of the entry, in the language of the caller, or an empty string for a separator.',
            'type': 'What the entry is: `internal_link` for a page of the event, `plugin_link` for a page a '
                    'plugin adds, `user_link` for a link the organisers typed, `page` for a page they wrote, '
                    '`separator` for a heading grouping the entries below it.',
            'position': 'Position of the entry among its siblings, starting at zero.',
            'new_tab': 'Whether the link is meant to open in a new tab.',
            'url': 'URL the entry points to, relative to the Indico instance, as typed by the organisers for a '
                   '`user_link`, or `null` for a separator.',
            'page_id': 'Identifier of the page the entry shows, or `null` unless the entry is a `page`.',
            'children': 'Entries nested under this one, as a separator and its items.',
        }

    name = fields.String(allow_none=True)
    title = fields.String(attribute='localized_title')
    type = fields.Enum(MenuEntryType)
    position = fields.Integer()
    new_tab = fields.Boolean()
    url = fields.String(allow_none=True)
    page_id = fields.Integer(allow_none=True)
    children = VisibleEntries(fields.Nested(lambda: MenuEntrySchema()))


class CustomPageSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """Page of HTML the organisers wrote and linked from the menu of the event."""

    class Meta:
        model = EventPage
        fields = ('id', 'event_id', 'title', 'html', 'is_default', 'url')
        descriptions = {
            'id': 'Numeric identifier of the page, unique across the whole instance.',
            'event_id': 'Identifier of the event the page belongs to.',
            'title': 'Title of the page, which is the title of the menu entry linking it.',
            'html': 'Body of the page, as HTML.',
            'is_default': 'Whether the page is the one the event opens on instead of its overview.',
            'url': 'Absolute URL the page is served at.',
        }

    title = fields.Function(lambda page: page.menu_entry.title)
    is_default = fields.Boolean()
    url = fields.Function(lambda page: url_for('event_pages.page_display', page, _external=True))


class ImageSchema(DescribedFieldsMixin, mm.SQLAlchemyAutoSchema):
    """Image the organisers uploaded to use it from the HTML of the event.

    Core has no schema for one because the management page renders the images
    straight from the model. The storage backend and the checksum are left out:
    they are internal bookkeeping the caller cannot act on.
    """

    class Meta:
        model = ImageFile
        fields = ('id', 'event_id', 'filename', 'content_type', 'size', 'created_dt', 'download_url')
        descriptions = {
            'id': 'Numeric identifier of the image, unique across the whole instance.',
            'event_id': 'Identifier of the event the image belongs to.',
            'filename': 'Name of the uploaded file.',
            'content_type': 'MIME type of the image, such as `image/png`.',
            'size': 'Size of the image in bytes.',
            'created_dt': 'Moment the image was uploaded, in UTC.',
            'download_url': 'Absolute URL the image is downloaded from.',
        }

    download_url = fields.Function(lambda image: url_for('event_images.image_display', image, _external=True))


@json_errors
class RHEventLayout(RHProtectedEventBase):
    def _process_GET(self):
        return EventLayoutSchema().jsonify(_layout_data(self.event))


@json_errors
class RHEventMenu(RHProtectedEventBase):
    def _process_GET(self):
        entries = [entry for entry in menu_entries_for_event(self.event) if entry.is_visible]
        return jsonify_results(MenuEntrySchema(many=True), entries)


class CustomPageMixin:
    """Access checks shared by the custom page endpoints.

    A page is reached through the menu entry linking it, so that entry is what
    decides who may read the page, exactly as the display page does. A page no
    entry links is unreachable in Indico, and the join leaves it out here too.
    """

    def _page_query(self):
        return (EventPage.query
                .join(MenuEntry, MenuEntry.page_id == EventPage.id)
                .filter(EventPage.event_id == self.event.id)
                .order_by(MenuEntry.position, EventPage.id))

    def _can_see_page(self, page):
        return page.menu_entry.can_access(session.user)


@json_errors
class RHCustomPage(CustomPageMixin, RHProtectedEventBase):
    def _process_args(self):
        RHProtectedEventBase._process_args(self)
        self.page = self._page_query().filter(EventPage.id == request.view_args['page_id']).first_or_404()

    def _check_access(self):
        RHProtectedEventBase._check_access(self)
        if not self._can_see_page(self.page):
            raise Forbidden

    def _process_GET(self):
        return CustomPageSchema().jsonify(self.page)


@json_errors
class RHCustomPageList(CustomPageMixin, RHListBase, RHProtectedEventBase):
    schema = CustomPageSchema

    def _query(self):
        return self._page_query()

    def _can_access(self, obj):
        return self._can_see_page(obj)


class ImageMixin:
    """Access checks shared by the image endpoints.

    Indico only enumerates the images of an event on a management page, so the
    listing stays restricted to event managers even though each image is served
    to whoever can read the page embedding it.
    """

    EVENT_FEATURE = 'images'

    def _image_query(self):
        return ImageFile.query.with_parent(self.event).order_by(ImageFile.id)


@json_errors
class RHImage(ImageMixin, RHManageEventBase):
    def _process_args(self):
        RHManageEventBase._process_args(self)
        self.image = self._image_query().filter(ImageFile.id == request.view_args['image_id']).first_or_404()

    def _process_GET(self):
        return ImageSchema().jsonify(self.image)


@json_errors
class RHImageList(ImageMixin, RHListBase, RHManageEventBase):
    schema = ImageSchema

    def _query(self):
        return self._image_query()

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(rule='/events/<int:event_id>/layout', name='layout', rh=RHEventLayout, schema=EventLayoutSchema,
             summary='Layout settings of an event', tag='Layout'),
    Endpoint(rule='/events/<int:event_id>/menu', name='menu', rh=RHEventMenu, schema=MenuEntrySchema, many=True,
             summary='Menu of an event', tag='Layout'),
    Endpoint(rule='/events/<int:event_id>/pages', name='pages', rh=RHCustomPageList, schema=CustomPageSchema,
             many=True, summary='List the custom pages of an event', tag='Layout'),
    Endpoint(rule='/events/<int:event_id>/pages/<int:page_id>', name='page', rh=RHCustomPage,
             schema=CustomPageSchema, summary='Custom page details', tag='Layout'),
    Endpoint(rule='/events/<int:event_id>/images', name='images', rh=RHImageList, schema=ImageSchema, many=True,
             summary='List the images of an event', tag='Layout'),
    Endpoint(rule='/events/<int:event_id>/images/<int:image_id>', name='image', rh=RHImage, schema=ImageSchema,
             summary='Image details', tag='Layout'),
]
