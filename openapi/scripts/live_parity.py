# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

"""Compare this API against the current one on a running Indico instance.

The unit tests pin the two APIs together on data built by fixtures. This script
does the same over HTTP against a real instance filled by ``seed_demo_data.py``,
so a divergence that only shows up on real rows still fails.

The comparison mappings are imported from the test modules instead of being
copied, so the live check cannot drift away from the tests.

    python scripts/live_parity.py <manifest.json>
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import pytz
import requests


PLUGIN_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_DIR))
sys.path.insert(0, str(PLUGIN_DIR / 'tests'))

import abstracts_test  # noqa: E402
import attachments_test  # noqa: E402
import blockings_test  # noqa: E402
import categories_test  # noqa: E402
import contributions_test  # noqa: E402
import events_test  # noqa: E402
import locations_test  # noqa: E402
import notes_test  # noqa: E402
import papers_test  # noqa: E402
import persons_test  # noqa: E402
import registrations_test  # noqa: E402
import reservations_test  # noqa: E402
import rooms_test  # noqa: E402
import sessions_test  # noqa: E402
import subcontributions_test  # noqa: E402
import timetable_test  # noqa: E402
import tracks_test  # noqa: E402
import users_test  # noqa: E402
from parity import compare, compare_list, rename_keys  # noqa: E402


class Api:
    """Both APIs of one running instance, seen through the same personal token."""

    def __init__(self, base_url, token):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers['Authorization'] = f'Bearer {token}'
        self.calls = 0
        self._cache = {}

    def get(self, path):
        self.calls += 1
        resp = self.session.get(f'{self.base_url}{path}', timeout=60)
        if resp.status_code != 200:
            raise RuntimeError(f'GET {path} returned {resp.status_code}: {resp.text[:200]}')
        return resp.json()

    def cached(self, path):
        if path not in self._cache:
            self._cache[path] = self.get(path)
        return self._cache[path]

    def ours(self, path):
        return self.get(f'/api/v1{path}')

    def list(self, path, limit=100):
        joiner = '&' if '?' in path else '?'
        results = []
        offset = 0
        while True:
            page = self.ours(f'{path}{joiner}limit={limit}&offset={offset}')
            results += page['results']
            if page['next_offset'] is None:
                return results
            offset = page['next_offset']


def legacy_date(timezone):
    tz = pytz.timezone(timezone)

    def convert(value):
        if value is None:
            return None
        local = datetime.fromisoformat(value).astimezone(tz)
        return {'date': str(local.date()), 'time': str(local.time()), 'tz': str(local.tzinfo)}

    return convert


def timetable_date(timezone):
    tz = pytz.timezone(timezone)

    def convert(value):
        local = datetime.fromisoformat(value).astimezone(tz)
        return {'date': local.strftime('%Y-%m-%d'), 'time': local.strftime('%H:%M:%S'), 'tz': str(tz)}

    return convert


def merged_registrations(api, event_id, regform_id):
    legacy = {int(reg['registrant_id']): reg
              for reg in api.get(f'/api/events/{event_id}/registrants')['registrants']}
    checkin = api.get(f'/api/checkin/event/{event_id}/forms/{regform_id}/registrations/')
    return [{**legacy[reg['id']], **reg} for reg in checkin]


def event_people(api, event_id):
    event = api.get(f'/export/event/{event_id}.json?detail=contributions')['results'][0]
    sessions = api.get(f'/export/event/{event_id}.json?detail=sessions')['results'][0]['sessions']
    return persons_test.as_people(event, sessions)


def subcontributions_by_contribution(api, event_id):
    current = api.cached(f'/export/event/{event_id}.json?detail=subcontributions')['results'][0]
    return {int(contrib['db_id']): contrib['subContributions'] for contrib in current['contributions']}


LEGACY_RESERVATION_PAGE = 100


def legacy_reservations(api):
    # the export ignores the locations in the path and serves at most 100 rows per call
    names = '-'.join(location['name'] for location in api.get('/rooms/api/locations'))
    results = []
    while True:
        page = api.get(f'/export/reservation/{names}.json'
                       f'?limit={LEGACY_RESERVATION_PAGE}&offset={len(results)}')['results']
        results += page
        if len(page) < LEGACY_RESERVATION_PAGE:
            return results


def note_url(event_id, link_type=None, link_id=None):
    if link_type is None:
        return f'/export/note/{event_id}.json'
    return f'/export/note/{event_id}/{link_type}/{link_id}.json'


class Checker:
    """Run every comparison and collect the outcome of each one."""

    def __init__(self, api, manifest):
        self.api = api
        self.manifest = manifest
        self.as_legacy_date = legacy_date(manifest['default_timezone'])
        self.as_timetable_date = timetable_date(manifest['default_timezone'])
        self.results = []
        self.compared = {}

    def check(self, entity, label, count, run):
        try:
            run()
        except Exception as exc:
            self.results.append((entity, label, count, exc))
        else:
            self.results.append((entity, label, count, None))
        self.compared[entity] = self.compared.get(entity, 0) + count

    def run(self):
        self.area('events', self.check_events)
        self.area('categories', self.check_categories)
        for event in self.manifest['events']:
            self.area('events', self.check_event_contents, event)
        self.area('users', self.check_users)
        self.area('rooms', self.check_rooms)
        self.area('locations', self.check_locations)
        self.area('blockings', self.check_blockings)
        self.area('reservations', self.check_reservations)
        return self.results

    def area(self, entity, method, *args):
        # a comparison that cannot even be set up must not take the rest of the run with it
        try:
            method(*args)
        except Exception as exc:
            self.results.append((entity, f'{method.__name__}{args or ""}', 0, exc))
            self.compared.setdefault(entity, 0)

    def _event_mappings(self):
        return {'same': events_test.EVENT_FIELDS,
                'renamed': {**events_test.EVENT_KEYS, **events_test.date_keys(self.as_legacy_date)},
                'derived': {'category_chain': events_test.as_category_chain}}

    def _with_chain(self, current):
        path = self.api.cached(f'/category/{current["categoryId"]}/info')['category']['path']
        return {**current, 'chain': path}

    def check_events(self):
        ours = self.api.list('/events')
        ids = '-'.join(str(event['id']) for event in ours)
        theirs = [self._with_chain(event)
                  for event in self.api.get(f'/export/event/{ids}.json')['results']]
        self.check('events', 'list', len(ours),
                   lambda: compare_list(ours, theirs, **self._event_mappings()))
        for event in self.manifest['events']:
            one = self.api.ours(f'/events/{event["id"]}')
            current = self._with_chain(self.api.get(f'/export/event/{event["id"]}.json')['results'][0])
            self.check('events', f'detail {event["id"]}', 1,
                       lambda one=one, current=current: compare(one, current, **self._event_mappings()))

    def _category_mappings(self):
        return {'same': categories_test.CATEGORY_FIELDS,
                'renamed': {'deep_events_count': ('deep_event_count', None)},
                'derived': {'chain_titles': categories_test.as_chain_titles,
                            'parent_id': categories_test.as_parent_id}}

    def check_categories(self):
        root = self.manifest['category_id']
        ours = self.api.list(f'/categories?parent_id={root}')
        theirs = self.api.cached(f'/category/{root}/info')['subcategories']
        self.check('categories', 'list', len(ours),
                   lambda: compare_list(ours, theirs, **self._category_mappings()))
        for category in ours:
            one = self.api.ours(f'/categories/{category["id"]}')
            current = self.api.cached(f'/category/{category["id"]}/info')['category']
            self.check('categories', f'detail {category["id"]}', 1,
                       lambda one=one, current=current: compare(one, current, **self._category_mappings()))

    def check_event_contents(self, event):
        event_id = event['id']
        self.check_contributions(event_id)
        self.check_subcontributions(event_id)
        self.check_persons(event_id)
        self.check_sessions(event_id)
        self.check_timetable(event_id)
        self.check_notes(event)
        self.check_attachments(event)
        if event['type'] != 'conference':
            return
        self.check_tracks(event_id)
        self.check_abstracts(event_id)
        self.check_papers(event_id)
        self.check_registrations(event_id)

    def check_contributions(self, event_id):
        ours = self.api.list(f'/events/{event_id}/contributions')
        theirs = self.api.get(f'/event/{event_id}/manage/contributions/contributions.json')
        self.check('contributions', f'list {event_id}', len(ours),
                   lambda: compare_list(ours, theirs, same=contributions_test.CONTRIBUTION_FIELDS))
        first = ours[0]
        current = self.api.get(f'/event/{event_id}/contributions/{first["id"]}.json')
        self.check('contributions', f'detail {first["id"]}', 1,
                   lambda: compare(first, current, same=contributions_test.CONTRIBUTION_FIELDS))

    def _subcontribution_mappings(self):
        return {'same': subcontributions_test.SUBCONTRIBUTION_FIELDS,
                'renamed': {'id': ('db_id', None), 'duration': ('duration', subcontributions_test.as_minutes),
                            'persons': ('speakers', rename_keys(subcontributions_test.FOSSIL_PERSON_KEYS))}}

    def check_subcontributions(self, event_id):
        by_contribution = subcontributions_by_contribution(self.api, event_id)
        for contrib_id, theirs in by_contribution.items():
            if not theirs:
                continue
            ours = self.api.list(f'/events/{event_id}/contributions/{contrib_id}/subcontributions')
            self.check('subcontributions', f'list {contrib_id}', len(ours),
                       lambda ours=ours, theirs=theirs: compare_list(ours, theirs,
                                                                     **self._subcontribution_mappings()))

    def _person_mappings(self):
        return {'same': (*persons_test.PERSON_FIELDS, 'roles'),
                'renamed': {'id': ('person_id', None), 'email_hash': ('emailHash', None)}}

    def check_persons(self, event_id):
        ours = self.api.list(f'/events/{event_id}/persons')
        theirs = list(event_people(self.api, event_id).values())
        self.check('persons', f'list {event_id}', len(ours),
                   lambda: compare_list(ours, theirs, **self._person_mappings()))

    def _session_mappings(self):
        return {'same': sessions_test.SESSION_FIELDS,
                'renamed': {**sessions_test.SESSION_KEYS,
                            'blocks': ('blocks', sessions_test.as_blocks(self.as_legacy_date))}}

    def check_sessions(self, event_id):
        ours = self.api.list(f'/events/{event_id}/sessions')
        if not ours:
            return
        ids = '-'.join(str(sess['id']) for sess in ours)
        slots = self.api.get(f'/export/event/{event_id}/session/{ids}.json')['results']
        theirs = sessions_test.as_sessions(slots)
        self.check('sessions', f'list {event_id}', len(ours),
                   lambda: compare_list(ours, list(theirs.values()), **self._session_mappings()))
        first = ours[0]
        self.check('sessions', f'detail {first["id"]}', 1,
                   lambda: compare(first, theirs[first['id']], **self._session_mappings()))

    def _timetable_mappings(self):
        return {'same': ('title',), 'renamed': timetable_test.entry_keys(self.as_timetable_date),
                'derived': timetable_test.DERIVED}

    def check_timetable(self, event_id):
        ours = self.api.list(f'/events/{event_id}/timetable')
        days = self.api.get(f'/export/timetable/{event_id}.json')['results'][str(event_id)]
        entries = timetable_test.flatten(days)
        theirs = [timetable_test.as_current(entry) for entry in entries.values()]
        self.check('timetable', f'list {event_id}', len(ours),
                   lambda: compare_list(ours, theirs, **self._timetable_mappings()))

    def check_notes(self, event):
        event_id = event['id']
        ours = self.api.list(f'/events/{event_id}/notes')
        theirs = [self.api.get(note_url(event_id))['results']]
        theirs += [self.api.get(note_url(event_id, 'contribution', contrib_id))['results']
                   for contrib_id in event['note_contributions']]
        theirs += [self.api.get(note_url(event_id, 'session', session_id))['results']
                   for session_id in event['note_sessions']]
        self.check('notes', f'list {event_id}', len(ours),
                   lambda: compare_list(ours, theirs, same=notes_test.NOTE_FIELDS,
                                        renamed={'author_id': ('user', None)}, key='url'))

    def _attachment_mappings(self, fields):
        return {'same': fields,
                'renamed': {'folder': ('folder', rename_keys(attachments_test.FOLDER_KEYS))}}

    def _check_attachment_scope(self, ours_path, theirs_path, label):
        ours = self.api.list(ours_path)
        theirs = attachments_test.flatten(self.api.get(theirs_path)['results']['folders'])
        files = [att for att in ours if att['type'] == 'file']
        links = [att for att in ours if att['type'] == 'link']
        by_id = {att['id']: att for att in theirs}
        self.check('attachments', label, len(ours), lambda: (
            compare_list(files, [by_id[att['id']] for att in files],
                         **self._attachment_mappings(attachments_test.FILE_FIELDS)),
            compare_list(links, [by_id[att['id']] for att in links],
                         **self._attachment_mappings(attachments_test.LINK_FIELDS))))

    def check_attachments(self, event):
        event_id = event['id']
        self._check_attachment_scope(f'/events/{event_id}/attachments',
                                     f'/export/attachments/{event_id}.json', f'event {event_id}')
        for contrib_id in event['attachment_contributions']:
            self._check_attachment_scope(
                f'/events/{event_id}/contributions/{contrib_id}/attachments',
                f'/export/attachments/{event_id}/contribution/{contrib_id}.json', f'contribution {contrib_id}')
        for session_id in event['attachment_sessions']:
            self._check_attachment_scope(
                f'/events/{event_id}/sessions/{session_id}/attachments',
                f'/export/attachments/{event_id}/session/{session_id}.json', f'session {session_id}')

    def check_tracks(self, event_id):
        ours = self.api.list(f'/events/{event_id}/tracks')
        current = self.api.get(f'/event/{event_id}/program.json')
        mappings = {'same': tracks_test.TRACK_FIELDS,
                    'derived': {'track_group': tracks_test.as_track_group(current)}}
        self.check('tracks', f'list {event_id}', len(ours),
                   lambda: compare_list(ours, current['tracks'], **mappings))
        first = ours[0]
        theirs = next(track for track in current['tracks'] if track['id'] == first['id'])
        self.check('tracks', f'detail {first["id"]}', 1, lambda: compare(first, theirs, **mappings))

    def check_abstracts(self, event_id):
        ours = self.api.list(f'/events/{event_id}/abstracts')
        current = self.api.get(f'/event/{event_id}/manage/abstracts/abstracts.json')['abstracts']
        mappings = {'same': abstracts_test.ABSTRACT_FIELDS, 'derived': abstracts_test.ABSTRACT_LINKS}
        self.check('abstracts', f'list {event_id}', len(ours),
                   lambda: compare_list(ours, current, **mappings))
        first = ours[0]
        theirs = next(abstract for abstract in current if abstract['id'] == first['id'])
        self.check('abstracts', f'detail {first["id"]}', 1, lambda: compare(first, theirs, **mappings))

    def check_papers(self, event_id):
        ours = self.api.list(f'/events/{event_id}/papers')
        current = self.api.get(f'/event/{event_id}/manage/papers/assignment-list/export-json')['papers']
        self.check('papers', f'list {event_id}', len(ours),
                   lambda: compare_list(ours, current, same=papers_test.PAPER_FIELDS,
                                        derived={**papers_test.PAPER_DERIVED,
                                                 'last_revision': papers_test.as_last_revision},
                                        key=lambda paper: paper['contribution']['id']))
        contrib_id = ours[0]['contribution']['id']
        one = self.api.ours(f'/events/{event_id}/contributions/{contrib_id}/paper')
        theirs = next(paper for paper in current if paper['contribution']['id'] == contrib_id)
        self.check('papers', f'detail {contrib_id}', 1,
                   lambda: compare(one, theirs, same=(*papers_test.PAPER_FIELDS, 'revisions'),
                                   derived=papers_test.PAPER_DERIVED))

    def check_registrations(self, event_id):
        ours = self.api.list(f'/events/{event_id}/registration-forms')
        theirs = self.api.get(f'/api/checkin/event/{event_id}/forms/')
        self.check('registration-forms', f'list {event_id}', len(ours),
                   lambda: compare_list(ours, theirs, same=registrations_test.REGFORM_FIELDS))
        regform_id = ours[0]['id']
        one = self.api.ours(f'/events/{event_id}/registration-forms/{regform_id}')
        current = next(form for form in theirs if form['id'] == regform_id)
        self.check('registration-forms', f'detail {regform_id}', 1,
                   lambda: compare(one, current, same=registrations_test.REGFORM_FIELDS))

        mappings = {'same': registrations_test.REGISTRATION_FIELDS,
                    'renamed': registrations_test.REGISTRATION_KEYS,
                    'derived': registrations_test.PERSONAL_DATA}
        our_regs = self.api.list(f'/events/{event_id}/registrations')
        their_regs = merged_registrations(self.api, event_id, regform_id)
        self.check('registrations', f'list {event_id}', len(our_regs),
                   lambda: compare_list(our_regs, their_regs, **mappings))
        first = our_regs[0]
        one = self.api.ours(f'/events/{event_id}/registrations/{first["id"]}')
        current = next(reg for reg in their_regs if reg['id'] == first['id'])
        self.check('registrations', f'detail {first["id"]}', 1, lambda: compare(one, current, **mappings))

    def check_users(self):
        me = self.api.ours('/users/me')
        current = self.api.get(f'/export/user/{me["id"]}.json')['results'][0]
        self.check('users', 'me', 1, lambda: compare(me, current, same=users_test.USER_FIELDS))
        ours = self.api.list('/users')
        # the legacy export serves one user per call
        theirs = [self.api.get(f'/export/user/{user["id"]}.json')['results'][0] for user in ours]
        self.check('users', 'list', len(ours),
                   lambda: compare_list(ours, theirs, same=users_test.USER_FIELDS))

    def check_rooms(self):
        as_ids = rooms_test.as_equipment_ids(self.api.get)
        mappings = {'same': rooms_test.ROOM_FIELDS,
                    'renamed': {'available_equipment': ('available_equipment', as_ids)}}
        ours = self.api.list('/rooms')
        theirs = self.api.get('/rooms/api/rooms/')
        for room in theirs:
            room['available_equipment'].sort()
        self.check('rooms', 'list', len(ours), lambda: compare_list(ours, theirs, **mappings))
        first = ours[0]
        current = self.api.get(f'/rooms/api/rooms/{first["id"]}')
        current['available_equipment'].sort()
        self.check('rooms', f'detail {first["id"]}', 1, lambda: compare(first, current, **mappings))

    def check_locations(self):
        ours = self.api.list('/locations')
        theirs = self.api.get('/rooms/api/locations')
        self.check('locations', 'list', len(ours),
                   lambda: compare_list(ours, theirs, same=locations_test.LOCATION_FIELDS))
        for location in ours:
            one = self.api.ours(f'/locations/{location["id"]}')
            current = next(loc for loc in theirs if loc['id'] == location['id'])
            self.check('locations', f'detail {location["id"]}', 1,
                       lambda one=one, current=current: compare(one, current,
                                                                same=(*locations_test.LOCATION_FIELDS, 'rooms')))

    def check_blockings(self):
        ours = self.api.list('/blockings')
        theirs = self.api.get('/rooms/api/blockings/')
        self.check('blockings', 'list', len(ours),
                   lambda: compare_list(ours, theirs, same=blockings_test.BLOCKING_FIELDS))
        first = ours[0]
        current = self.api.get(f'/rooms/api/blockings/{first["id"]}')
        self.check('blockings', f'detail {first["id"]}', 1,
                   lambda: compare(first, current, same=blockings_test.BLOCKING_FIELDS))

    def check_reservations(self):
        mappings = {'same': reservations_test.RESERVATION_FIELDS,
                    'renamed': reservations_test.RESERVATION_KEYS}
        ours = self.api.list('/reservations')
        legacy = legacy_reservations(self.api)
        theirs = [reservations_test.with_details(self.api.get, booking) for booking in legacy]
        self.check('reservations', 'list', len(ours),
                   lambda: compare_list(ours, theirs, **mappings,
                                        derived={'is_repeating': reservations_test.as_is_repeating}))
        first = ours[0]
        one = self.api.ours(f'/reservations/{first["id"]}')
        current = next(booking for booking in theirs if booking['id'] == first['id'])
        self.check('reservations', f'detail {first["id"]}', 1,
                   lambda: compare(one, current, **mappings,
                                   derived={'is_repeating': reservations_test.as_is_repeating,
                                            'occurrences': reservations_test.as_occurrences}))


def report(results, compared, calls):
    failures = [entry for entry in results if entry[3] is not None]
    entities = sorted(compared)
    width = max(len(entity) for entity in entities)
    print()
    print(f'{"entity".ljust(width)}  checks  objects  result')
    for entity in entities:
        checks = [entry for entry in results if entry[0] == entity]
        broken = [entry for entry in checks if entry[3] is not None]
        status = 'ok' if not broken else f'{len(broken)} FAILED'
        print(f'{entity.ljust(width)}  {len(checks):6}  {compared[entity]:7}  {status}')
    print()
    print(f'{len(results)} checks, {sum(compared.values())} objects compared, {calls} requests')
    for entity, label, _count, error in failures:
        print()
        print(f'FAILED {entity} [{label}]')
        print(f'  {type(error).__name__}: {error}')
    return not failures


def main(manifest_path):
    manifest = json.loads(Path(manifest_path).read_text())
    api = Api(manifest['base_url'], manifest['token'])
    checker = Checker(api, manifest)
    checker.run()
    return 0 if report(checker.results, checker.compared, api.calls) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
