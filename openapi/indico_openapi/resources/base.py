# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from dataclasses import dataclass

from flask import jsonify, request, session
from marshmallow import fields, validate

from indico.core.marshmallow import mm
from indico.web.args import parser
from indico.web.rh import RH


PREFETCH_FACTOR = 5


@dataclass(frozen=True)
class Endpoint:
    """One read-only API route, used to build both the blueprint and the spec."""

    rule: str
    name: str
    rh: type[RH]
    summary: str
    tag: str
    schema: type | None = None
    many: bool = False


class DescribedFieldsMixin:
    """Attach the descriptions declared in ``Meta.descriptions`` to the schema fields.

    Fields inherited from the core schemas carry no documentation, and the
    generated spec is the only reference API consumers get.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, description in getattr(self.Meta, 'descriptions', {}).items():
            if field := self.fields.get(name):
                field.metadata.setdefault('description', description)


class ListArgs(mm.Schema):
    limit = fields.Integer(load_default=20, validate=validate.Range(min=1, max=100),
                           metadata={'description': 'Maximum number of results to return.'})
    offset = fields.Integer(load_default=0, validate=validate.Range(min=0),
                            metadata={'description': 'Cursor taken from `next_offset` of the previous page. '
                                                     'It counts rows scanned, not results returned, because '
                                                     'inaccessible rows are skipped without being listed.'})


def paginate(query, predicate, limit, offset):
    """Return up to ``limit`` objects matching ``predicate``, plus the cursor to resume from.

    ``predicate`` is applied in Python because Indico's access checks walk the
    ACL and the protection chain, which cannot be expressed as a SQL filter.
    """
    accepted = []
    scanned = offset
    cutoff = None
    while True:
        batch = query.offset(scanned).limit((limit + 1) * PREFETCH_FACTOR).all()
        if not batch:
            break
        for obj in batch:
            scanned += 1
            if not predicate(obj):
                continue
            accepted.append(obj)
            if len(accepted) == limit:
                cutoff = scanned
            if len(accepted) > limit:
                break
        if len(accepted) > limit:
            break
    has_more = len(accepted) > limit
    return accepted[:limit], (cutoff if has_more else None)


class RHListBase(RH):
    """Base for endpoints listing objects the current user is allowed to see."""

    args_schema = ListArgs
    schema = None

    def _query(self, **filters):
        raise NotImplementedError

    def _can_access(self, obj):
        return obj.can_access(session.user)

    def _dump_schema(self):
        return self.schema(many=True)

    def _process_GET(self):
        args = parser.parse(self.args_schema, request, location='query')
        limit = args.pop('limit')
        offset = args.pop('offset')
        results, next_offset = paginate(self._query(**args), self._can_access, limit, offset)
        return jsonify(results=self._dump_schema().dump(results), count=len(results), next_offset=next_offset)
