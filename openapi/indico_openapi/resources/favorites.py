# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 Unconventional
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from flask import session
from sqlalchemy.orm import undefer

from indico.modules.categories.models.categories import Category
from indico.modules.events import Event
from indico.modules.rb.controllers import RHRoomBookingBase
from indico.modules.rb.models.rooms import Room
from indico.modules.users import User
from indico.web.rh import RHProtected, json_errors

from indico_openapi.resources.base import Endpoint, RHListBase
from indico_openapi.resources.categories import CategorySchema
from indico_openapi.resources.events import EventSchema
from indico_openapi.resources.rooms import RoomMixin, RoomSchema
from indico_openapi.schemas import MemberSchema


class FavoriteListBase(RHListBase, RHProtected):
    """Base for the lists of objects the caller marked as favourites.

    Favourites are personal: they are shown on the profile of the user who
    picked them and nowhere else, so every list answers about whoever holds the
    token and never about anybody else.
    """


@json_errors
class RHFavoriteUserList(FavoriteListBase):
    schema = MemberSchema

    def _query(self):
        ids = [user.id for user in session.user.favorite_users]
        return User.query.filter(User.id.in_(ids), ~User.is_deleted).order_by(User.last_name, User.first_name, User.id)

    def _can_access(self, obj):
        return True


@json_errors
class RHFavoriteCategoryList(FavoriteListBase):
    schema = CategorySchema

    def _query(self):
        ids = [category.id for category in session.user.favorite_categories]
        return (
            Category.query
            .filter(Category.id.in_(ids), ~Category.is_deleted)
            .options(undefer('chain_titles'), undefer('deep_events_count'))
            .order_by(Category.title, Category.id)
        )


@json_errors
class RHFavoriteEventList(FavoriteListBase):
    schema = EventSchema

    def _query(self):
        ids = [event.id for event in session.user.favorite_events]
        return Event.query.filter(Event.id.in_(ids), ~Event.is_deleted).order_by(Event.start_dt.desc(), Event.id)


@json_errors
class RHFavoriteRoomList(RoomMixin, RHListBase, RHRoomBookingBase):
    """Rooms the caller starred in the room booking system."""

    schema = RoomSchema

    def _query(self):
        ids = [room.id for room in session.user.favorite_rooms]
        return self._room_query().filter(Room.id.in_(ids))

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(
        rule='/users/me/favorite-users',
        name='favorite_users',
        rh=RHFavoriteUserList,
        schema=MemberSchema,
        many=True,
        summary='List the users the caller marked as favourites',
        tag='Personal data',
    ),
    Endpoint(
        rule='/users/me/favorite-categories',
        name='favorite_categories',
        rh=RHFavoriteCategoryList,
        schema=CategorySchema,
        many=True,
        summary='List the categories the caller marked as favourites',
        tag='Personal data',
    ),
    Endpoint(
        rule='/users/me/favorite-events',
        name='favorite_events',
        rh=RHFavoriteEventList,
        schema=EventSchema,
        many=True,
        summary='List the events the caller marked as favourites',
        tag='Personal data',
    ),
    Endpoint(
        rule='/users/me/favorite-rooms',
        name='favorite_rooms',
        rh=RHFavoriteRoomList,
        schema=RoomSchema,
        many=True,
        summary='List the rooms the caller marked as favourites',
        tag='Personal data',
    ),
]
