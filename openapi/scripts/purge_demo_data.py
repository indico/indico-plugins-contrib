# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

"""Remove everything ``seed_demo_data.py`` created, so it can be run again.

Indico deletes events, rooms and users by flagging them, and a flagged row still
holds the titles and identities the seed asks for, so the demo data has to go
for real. No foreign key in the schema cascades, so every row is removed by
walking the foreign keys that point at its table and deleting the children
first.
"""

from sqlalchemy import bindparam, text

from indico.core.db import db


CATEGORY_TITLE = 'OpenAPI demo data'
EMAIL_PATTERN = 'openapi.%@example.test'
IDENTITY_PATTERN = 'openapi.%'
LOCATION_NAMES = ('Meyrin', 'Prevessin', 'Remote')

CATEGORY_TREE = """
    WITH RECURSIVE tree AS (
        SELECT id FROM categories.categories WHERE title = :title
        UNION ALL
        SELECT c.id FROM categories.categories c JOIN tree ON c.parent_id = tree.id
    )
    SELECT id FROM tree
"""

DEMO_USERS = """
    SELECT user_id FROM users.emails WHERE email LIKE :emails
    UNION
    SELECT user_id FROM users.identities WHERE provider = 'indico' AND identifier LIKE :identities
"""

LISTS = ('categories', 'locations', 'users')

FOREIGN_KEYS = """
    SELECT rn.nspname || '.' || rc.relname AS parent,
           tn.nspname || '.' || tc.relname AS child,
           (SELECT array_agg(a.attname ORDER BY k.ord)
            FROM unnest(c.conkey) WITH ORDINALITY AS k(num, ord)
            JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.num) AS child_columns,
           (SELECT array_agg(a.attname ORDER BY k.ord)
            FROM unnest(c.confkey) WITH ORDINALITY AS k(num, ord)
            JOIN pg_attribute a ON a.attrelid = c.confrelid AND a.attnum = k.num) AS parent_columns,
           (SELECT bool_and(NOT a.attnotnull)
            FROM unnest(c.conkey) AS k(num)
            JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.num) AS nullable
    FROM pg_constraint c
    JOIN pg_class tc ON tc.oid = c.conrelid
    JOIN pg_namespace tn ON tn.oid = tc.relnamespace
    JOIN pg_class rc ON rc.oid = c.confrelid
    JOIN pg_namespace rn ON rn.oid = rc.relnamespace
    WHERE c.contype = 'f'
"""

# the rows to remove are picked before anything is deleted, because a predicate
# reading another table stops matching as soon as that table loses its rows
TARGETS = (
    ('events.events', 'category_id IN :categories'),
    ('categories.categories', 'id IN :categories'),
    # a break hangs off its timetable entry and nothing else, so it only becomes
    # reachable once the entry is gone
    ('events.breaks', ('id IN (SELECT b.id FROM events.breaks b WHERE NOT EXISTS '
                       '(SELECT 1 FROM events.timetable_entries t WHERE t.break_id = b.id))')),
    ('roombooking.locations', 'name IN :locations'),
    ('users.users', 'id IN :users'),
)


def read_foreign_keys():
    keys = {}
    for parent, child, child_columns, parent_columns, nullable in db.session.execute(text(FOREIGN_KEYS)):
        keys.setdefault(parent, []).append((child, child_columns, parent_columns, nullable))
    return keys


def run(statement, params):
    query = text(statement)
    for name in LISTS:
        if f':{name}' in statement:
            query = query.bindparams(bindparam(name, expanding=True))
    return db.session.execute(query, params)


def release(keys, table, child, where, params):
    """Blank out the pointers from ``table`` to ``child`` so ``child`` can go first."""
    edges = [key for key in keys.get(child, ()) if key[0] == table and key[3]]
    for edge in edges:
        assignment = ', '.join(f'{name} = NULL' for name in edge[1])
        run(f'UPDATE {table} SET {assignment} WHERE {where}', params)  # noqa: S608
    return bool(edges)


# every identifier in the statements below comes from the catalog, and the
# values the demo data is matched on travel as bind parameters
def purge(keys, table, where, params, stack=()):
    deleted = {}
    for child, child_columns, parent_columns, nullable in keys.get(table, ()):
        columns = ', '.join(child_columns)
        source = ', '.join(f'p.{name}' for name in parent_columns)
        condition = f'({columns}) IN (SELECT {source} FROM {table} p WHERE {where})'  # noqa: S608
        if child in (*stack, table):
            if nullable:
                assignment = ', '.join(f'{name} = NULL' for name in child_columns)
                # rows inside the target set go away with it, and a self reference
                # is often the one thing a check constraint will not let us blank out
                # NOT would let through rows whose predicate is unknown rather
                # than false, and a null foreign key makes it unknown
                kept = f'{condition} AND ({where}) IS NOT TRUE' if child == table else condition
                run(f'UPDATE {child} SET {assignment} WHERE {kept}', params)  # noqa: S608
                continue
            if not release(keys, table, child, where, params):
                raise SystemExit(f'cannot break the cycle between {table} and {child} on {columns}')
        for name, count in purge(keys, child, condition, params, (*stack, table)).items():
            deleted[name] = deleted.get(name, 0) + count
    count = run(f'DELETE FROM {table} WHERE {where}', params).rowcount  # noqa: S608
    if count:
        deleted[table] = deleted.get(table, 0) + count
    return deleted


def main():
    categories = db.session.execute(text(CATEGORY_TREE), {'title': CATEGORY_TITLE}).scalars().all()
    users = db.session.execute(text(DEMO_USERS),
                               {'emails': EMAIL_PATTERN, 'identities': IDENTITY_PATTERN}).scalars().all()
    params = {'categories': categories, 'locations': list(LOCATION_NAMES), 'users': users}
    keys = read_foreign_keys()
    deleted = {}
    for table, where in TARGETS:
        for name, count in purge(keys, table, where, params).items():
            deleted[name] = deleted.get(name, 0) + count
    db.session.commit()
    print('PURGE_OK', sorted(deleted.items()))


if __name__ == '__main__':
    main()
