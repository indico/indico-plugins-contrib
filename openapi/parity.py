# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

"""Strict comparison between what this API returns and what the current API returns.

Every attribute of our object must be declared in exactly one of ``same``,
``renamed`` or ``derived``, and every declared value must match the current API
down to the last key. Anything the current API does not expose must not be
exposed here either, so an undeclared attribute fails instead of being ignored.

The test fixtures and the live checker both build on this module, so a
divergence cannot pass one and fail the other.
"""

from operator import itemgetter


MISSING = '<not served by the current API>'


def _reduce(mine, theirs):
    """Keep only the parts of ``theirs`` our object also carries.

    The current API nests whole objects where we serve a subset of their keys,
    so the comparison would drown in attributes we deliberately leave out.
    """
    if isinstance(mine, dict) and isinstance(theirs, dict):
        return {key: (_reduce(value, theirs[key]) if key in theirs else MISSING) for key, value in mine.items()}
    if isinstance(mine, list) and isinstance(theirs, list) and len(mine) == len(theirs):
        return [_reduce(value, other) for value, other in zip(mine, theirs, strict=True)]
    return theirs


def _spec(renamed, key):
    spec = renamed.get(key, key)
    return spec if isinstance(spec, tuple) else (spec, None)


def compare(ours, theirs, same=(), renamed=None, derived=None):
    renamed = renamed or {}
    derived = derived or {}
    assert set(ours) == set(same) | set(renamed) | set(derived)
    mine, expected = {}, {}
    for key in same:
        mine[key] = ours[key]
        expected[key] = theirs.get(key, MISSING)
    for key in renamed:
        their_key, convert = _spec(renamed, key)
        mine[key] = convert(ours[key]) if convert else ours[key]
        expected[key] = theirs.get(their_key, MISSING)
    for key, compute in derived.items():
        mine[key] = ours[key]
        expected[key] = compute(theirs)
    assert mine == {key: _reduce(mine[key], value) for key, value in expected.items()}


def _key_getters(renamed, key):
    if callable(key):
        return key, key
    their_key, convert = _spec(renamed, key)
    ours = (lambda obj: convert(obj[key])) if convert else itemgetter(key)
    return ours, itemgetter(their_key)


def compare_list(ours, theirs, same=(), renamed=None, derived=None, key='id'):
    renamed = renamed or {}
    our_key, their_key = _key_getters(renamed, key)
    theirs_by_key = {their_key(obj): obj for obj in theirs}
    assert len(theirs_by_key) == len(theirs) == len(ours)
    for obj in ours:
        compare(obj, theirs_by_key[our_key(obj)], same, renamed, derived)


def rename_keys(mapping):
    def convert(value):
        if isinstance(value, list):
            return [convert(item) for item in value]
        return {mapping.get(key, key): item for key, item in value.items()}

    return convert
