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
from operator import itemgetter
from pathlib import Path
from urllib.parse import quote

import pytz
import requests


PLUGIN_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_DIR))
sys.path.insert(0, str(PLUGIN_DIR / 'tests'))

import abstracts_test  # noqa: E402
import affiliations_test  # noqa: E402
import attachments_test  # noqa: E402
import blockings_test  # noqa: E402
import categories_test  # noqa: E402
import category_logs_test  # noqa: E402
import category_roles_test  # noqa: E402
import contribution_fields_test  # noqa: E402
import contributions_test  # noqa: E402
import designer_test  # noqa: E402
import equipment_test  # noqa: E402
import events_test  # noqa: E402
import files_test  # noqa: E402
import groups_test  # noqa: E402
import locations_test  # noqa: E402
import logs_test  # noqa: E402
import map_areas_test  # noqa: E402
import move_requests_test  # noqa: E402
import notes_test  # noqa: E402
import paper_file_types_test  # noqa: E402
import papers_test  # noqa: E402
import persons_test  # noqa: E402
import receipts_test  # noqa: E402
import registration_tags_test  # noqa: E402
import registrations_test  # noqa: E402
import reservation_edit_logs_test  # noqa: E402
import reservation_links_test  # noqa: E402
import reservations_test  # noqa: E402
import roles_test  # noqa: E402
import room_attributes_test  # noqa: E402
import room_availability_test  # noqa: E402
import rooms_test  # noqa: E402
import series_test  # noqa: E402
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


def compare_answers(ours, theirs):
    """Compare the answers of a registration against the check-in API.

    That API lists every field of the form, answered or not, while only the
    answers given are served here, so each answer is looked up instead of the
    two lists being compared as a whole.
    """
    their_sections = {section['id']: section for section in theirs}
    for section in ours:
        their_section = their_sections[section['id']]
        assert section['title'] == their_section['title']
        their_fields = {field['id']: field for field in their_section['fields']}
        for field in section['fields']:
            compare(registrations_test.comparable(field), their_fields[field['id']],
                    same=registrations_test.ANSWER_FIELDS, renamed=registrations_test.ANSWER_KEYS)


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


def merged_roles(api, event_id):
    # only the management API serves the members, and only the protection API serves the id,
    # so the two payloads are zipped together on the code both of them order by
    detailed = sorted(api.get(f'/event/{event_id}/manage/roles/api/roles/'), key=itemgetter('code'))
    basic = api.get(f'/event/{event_id}/manage/api/event-roles')
    return [{**role, **extra} for role, extra in zip(detailed, basic, strict=True)]


def current_log_entries(api, path, realms):
    # the management log serves fixed pages, so every page is read
    entries = []
    page = 1
    while True:
        data = api.get(f'{path}?{realms}&page={page}')
        entries += data['entries']
        if page >= data['total_page_count']:
            return entries
        page += 1


def designer_template_data(api, event_id, template_id):
    current = api.get(f'/event/{event_id}/manage/designer/{template_id}/data')
    return current['template'] | {'backside_template_id': current['backside_template_id']}


class Checker:
    """Run every comparison and collect the outcome of each one."""

    def __init__(self, api, manifest):
        self.api = api
        self.manifest = manifest
        self.tzinfo = pytz.timezone(manifest['default_timezone'])
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
        self.area('groups', self.check_groups)
        self.area('files', self.check_files)
        self.area('event-series', self.check_series)
        self.area('category-roles', self.check_category_roles)
        self.area('category-logs', self.check_category_logs)
        self.area('move-requests', self.check_move_requests)
        self.area('affiliations', self.check_affiliations)
        self.area('reference-types', self.check_catalogues)
        self.area('rooms', self.check_rooms)
        self.area('locations', self.check_locations)
        self.area('map-areas', self.check_map_areas)
        self.area('equipment-types', self.check_equipment)
        self.area('room-features', self.check_room_features)
        self.area('room-attributes', self.check_room_attributes)
        self.area('room-availability', self.check_room_availability)
        self.area('blockings', self.check_blockings)
        self.area('reservations', self.check_reservations)
        self.area('reservation-edit-logs', self.check_reservation_edit_logs)
        self.area('reservation-links', self.check_reservation_links)
        return self.results

    def check_count(self, entity, path, expected):
        """Check that a list endpoint the current API has no counterpart for serves the seeded rows."""
        def run():
            if len(listed) != expected:
                raise AssertionError(f'{path} served {len(listed)} rows instead of {expected}')

        listed = self.api.list(path)
        self.check(entity, f'count {path}', len(listed), run)

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
                'derived': events_test.DERIVED}

    def _with_chain(self, current):
        path = self.api.cached(f'/category/{current["categoryId"]}/info')['category']['path']
        return {**current, 'chain': path}

    def _with_extras(self, current):
        # the legacy export only carries the contact of an event next to its sessions
        event_id = current['id']
        sessions = self.api.cached(f'/api/v1/events/{event_id}/sessions?limit=1')['results']
        slots = self.api.cached(f'/export/event/{event_id}/session/{sessions[0]["id"]}.json')['results']
        return {**self._with_chain(current), 'supportInfo': slots[0]['conference']['supportInfo']}

    def check_events(self):
        ours = self.api.list('/events')
        ids = '-'.join(str(event['id']) for event in ours)
        theirs = [self._with_chain(event) for event in self.api.get(f'/export/event/{ids}.json')['results']]
        # an event without sessions has no contact to compare against, so the whole list is compared
        # without it and the contact is compared for the demo events, which all have sessions
        mappings = self._event_mappings()
        listed = [{key: value for key, value in event.items() if key != 'contact'} for event in ours]
        without_contact = {**mappings, 'derived': {key: fn for key, fn in mappings['derived'].items()
                                                   if key != 'contact'}}
        self.check('events', 'list', len(listed), lambda: compare_list(listed, theirs, **without_contact))
        for event in self.manifest['events']:
            one = self.api.ours(f'/events/{event["id"]}')
            current = self._with_extras(self.api.get(f'/export/event/{event["id"]}.json')['results'][0])
            self.check('events', f'detail {event["id"]}', 1,
                       lambda one=one, current=current: compare(one, current, **mappings))

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
        self.check_logs(event_id)
        self.check_count('reminders', f'/events/{event_id}/reminders', event['reminders'])
        self.check_count('note-revisions', f'/events/{event_id}/notes/{event["note_id"]}/revisions',
                         event['note_revisions'])
        self.check_count('videoconference-rooms', f'/events/{event_id}/videoconference-rooms', event['vc_rooms'])
        if event['type'] != 'conference':
            return
        self.check_tracks(event_id)
        self.check_abstracts(event_id)
        self.check_abstract_emails(event)
        self.check_papers(event_id)
        self.check_paper_setup(event)
        self.check_contribution_setup(event)
        self.check_registrations(event_id)
        self.check_registration_tags(event)
        self.check_count('registration-invitations',
                         f'/events/{event_id}/registration-forms/{event["regform_id"]}/invitations',
                         event['invitations'])
        self.check_roles(event_id)
        self.check_layout(event)
        self.check_features(event)
        self.check_document_templates(event_id)
        self.check_designer_templates(event_id)
        self.check_count('payments', f'/events/{event_id}/payments', event['payments'])
        self.check_count('offline-copies', f'/events/{event_id}/offline-copies', event['offline_copies'])
        self.check_count('pages', f'/events/{event_id}/pages', event['pages'])
        self.check_count('images', f'/events/{event_id}/images', event['images'])
        for registration_id, expected in event['documents'].items():
            self.check_count('documents', f'/events/{event_id}/registrations/{registration_id}/documents', expected)

    def check_contributions(self, event_id):
        ours = self.api.list(f'/events/{event_id}/contributions')
        add_references = contributions_test.with_references(self.api.cached, event_id)
        theirs = [add_references(contrib)
                  for contrib in self.api.get(f'/event/{event_id}/manage/contributions/contributions.json')]
        self.check('contributions', f'list {event_id}', len(ours),
                   lambda: compare_list(ours, theirs, same=contributions_test.CONTRIBUTION_FIELDS))
        first = ours[0]
        current = add_references(self.api.get(f'/event/{event_id}/contributions/{first["id"]}.json'))
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

    def _as_displayed(self, event_id, entries):
        """Stretch the contributions of a poster session over their block.

        A poster is shown for as long as the session it is presented in, and
        that displayed span is what the current API answers with. The schedule
        as stored is what this API serves, so the difference is applied here.
        """
        sessions = self.api.list(f'/events/{event_id}/sessions')
        posters = {block['id'] for session in sessions if session['is_poster'] for block in session['blocks']}
        slots = {entry['id']: entry for entry in entries
                 if entry['type'] == 'session_block' and entry['session_block_id'] in posters}
        return [{**entry, **{key: slots[entry['parent_id']][key] for key in ('start_dt', 'end_dt', 'duration')}}
                if entry['type'] == 'contribution' and entry['parent_id'] in slots else entry
                for entry in entries]

    def check_timetable(self, event_id):
        ours = self._as_displayed(event_id, self.api.list(f'/events/{event_id}/timetable'))
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
        answers = one.pop('sections')
        self.check('registrations', f'detail {first["id"]}', 1, lambda: compare(one, current, **mappings))
        their_data = self.api.get(f'/api/checkin/event/{event_id}/forms/{regform_id}/registrations/'
                                  f'{first["id"]}')['registration_data']
        self.check('registration-answers', f'detail {first["id"]}',
                   sum(len(section['fields']) for section in answers),
                   lambda: compare_answers(answers, their_data))

    def check_logs(self, event_id):
        mappings = {'same': logs_test.LOG_FIELDS, 'renamed': logs_test.log_keys(self.tzinfo)}
        ours = self.api.list(f'/events/{event_id}/logs')
        theirs = current_log_entries(self.api, f'/event/{event_id}/manage/logs/api/logs', logs_test.ALL_REALMS)
        self.check('logs', f'list {event_id}', len(ours), lambda: compare_list(ours, theirs, **mappings))
        first = ours[0]
        one = self.api.ours(f'/events/{event_id}/logs/{first["id"]}')
        current = next(entry for entry in theirs if entry['id'] == first['id'])
        self.check('logs', f'detail {first["id"]}', 1, lambda: compare(one, current, **mappings))

    def check_roles(self, event_id):
        mappings = {'same': roles_test.ROLE_FIELDS, 'derived': {'members': roles_test.by_id}}
        ours = self.api.list(f'/events/{event_id}/roles')
        theirs = merged_roles(self.api, event_id)
        self.check('roles', f'list {event_id}', len(ours), lambda: compare_list(ours, theirs, **mappings))
        first = ours[0]
        one = self.api.ours(f'/events/{event_id}/roles/{first["id"]}')
        current = next(role for role in theirs if role['id'] == first['id'])
        self.check('roles', f'detail {first["id"]}', 1, lambda: compare(one, current, **mappings))

    def check_contribution_setup(self, event):
        event_id = event['id']
        self.check_count('contribution-types', f'/events/{event_id}/contribution-types', event['contribution_types'])
        self.check_count('session-types', f'/events/{event_id}/session-types', event['session_types'])
        ours = self.api.list(f'/events/{event_id}/contribution-fields')
        theirs = self.api.get(f'/event/{event_id}/manage/contributions/api/fields/')
        self.check('contribution-fields', f'list {event_id}', len(ours),
                   lambda: compare_list(ours, theirs, same=contribution_fields_test.FIELD_FIELDS,
                                        derived={'event_id': lambda _: event_id}))

    def check_paper_setup(self, event):
        event_id = event['id']
        self.check_count('paper-templates', f'/events/{event_id}/paper-templates', event['paper_templates'])
        ours = self.api.list(f'/events/{event_id}/paper-file-types')
        theirs = self.api.get(f'/event/{event_id}/papers/api/file-types/')
        self.check('paper-file-types', f'list {event_id}', len(ours),
                   lambda: compare_list(ours, theirs, same=paper_file_types_test.FILE_TYPE_FIELDS,
                                        derived={'event_id': lambda _: event_id}))

    def check_abstract_emails(self, event):
        event_id = event['id']
        self.check_count('abstract-email-templates', f'/events/{event_id}/abstract-email-templates',
                         event['abstract_email_templates'])
        for abstract_id, expected in event['abstract_emails'].items():
            self.check_count('abstract-emails', f'/events/{event_id}/abstracts/{abstract_id}/emails', expected)

    def check_category_roles(self):
        category_id = self.manifest['category_id']
        ours = self.api.list(f'/categories/{category_id}/roles')
        theirs = self.api.get(f'/category/{category_id}/manage/roles/api/roles/')
        ids = {role['code']: role['id'] for role in ours}
        self.check('category-roles', f'list {category_id}', len(ours),
                   lambda: compare_list(ours, theirs, same=category_roles_test.CATEGORY_ROLE_FIELDS,
                                        derived={'members': category_roles_test.by_id,
                                                 'id': lambda current: ids[current['code']],
                                                 'category_id': lambda _: category_id},
                                        key='code'))
        first = ours[0]
        one = self.api.ours(f'/categories/{category_id}/roles/{first["id"]}')
        current = next(role for role in theirs if role['code'] == first['code'])
        self.check('category-roles', f'detail {first["id"]}', 1,
                   lambda: compare(one, current, same=category_roles_test.CATEGORY_ROLE_FIELDS,
                                   derived={'members': category_roles_test.by_id,
                                            'id': lambda _: first['id'],
                                            'category_id': lambda _: category_id}))

    def check_move_requests(self):
        category_id = self.manifest['category_id']
        mappings = {'same': move_requests_test.MOVE_REQUEST_FIELDS,
                    'renamed': {'requestor': ('requestor', move_requests_test.as_requestor)},
                    'derived': {'event_id': lambda current: current['event']['id'],
                                'category_id': lambda _: category_id,
                                'moderator': lambda _: None, 'moderator_comment': lambda _: ''}}
        ours = self.api.list(f'/categories/{category_id}/move-requests?state=pending')
        theirs = self.api.get(f'/category/{category_id}/api/event-move-requests')
        self.check('move-requests', f'list {category_id}', len(ours),
                   lambda: compare_list(ours, theirs, **mappings))
        first = ours[0]
        one = self.api.ours(f'/categories/{category_id}/move-requests/{first["id"]}')
        current = next(request for request in theirs if request['id'] == first['id'])
        self.check('move-requests', f'detail {first["id"]}', 1, lambda: compare(one, current, **mappings))
        self.check_count('move-requests', f'/categories/{category_id}/move-requests',
                         self.manifest['counts']['move_requests'])

    def check_map_areas(self):
        ours = self.api.list('/map-areas')
        theirs = self.api.get('/rooms/api/map-areas')
        self.check('map-areas', 'list', len(ours),
                   lambda: compare_list(ours, theirs, same=map_areas_test.MAP_AREA_FIELDS))
        first = ours[0]
        one = self.api.ours(f'/map-areas/{first["id"]}')
        current = next(area for area in theirs if area['id'] == first['id'])
        self.check('map-areas', f'detail {first["id"]}', 1,
                   lambda: compare(one, current, same=map_areas_test.MAP_AREA_FIELDS))

    def check_room_attributes(self):
        room_id = self.manifest['attributed_room_id']
        ours = self.api.list(f'/rooms/{room_id}/attributes')
        theirs = self.api.get(f'/rooms/api/rooms/{room_id}/attributes')
        ids = {attribute['name']: attribute['attribute_id'] for attribute in ours}
        # the hidden attributes are served to the managers of the room, and the current API drops them for everybody
        visible = [attribute for attribute in ours if not attribute['is_hidden']]
        self.check('room-attributes', f'list {room_id}', len(ours),
                   lambda: compare_list(visible, theirs, same=room_attributes_test.ATTRIBUTE_FIELDS,
                                        derived={'attribute_id': lambda current: ids[current['name']],
                                                 'is_hidden': lambda _: False},
                                        key='name'))

    def check_room_availability(self):
        room_id = self.manifest['attributed_room_id']
        current = self.api.get(f'/rooms/api/admin/rooms/{room_id}/availability')
        ours = self.api.list(f'/rooms/{room_id}/bookable-hours')
        ids = {hours['start_time']: hours['id'] for hours in ours}
        self.check('room-availability', f'bookable hours {room_id}', len(ours),
                   lambda: compare_list(ours, current['bookable_hours'],
                                        same=room_availability_test.BOOKABLE_HOURS_FIELDS,
                                        derived={'id': lambda current: ids[current['start_time']],
                                                 'room_id': lambda _: room_id},
                                        key='start_time'))
        ours = self.api.list(f'/rooms/{room_id}/nonbookable-periods')
        # the administration interface only edits whole days, so it drops the time of both ends
        self.check('room-availability', f'nonbookable periods {room_id}', len(ours),
                   lambda: compare_list(ours, current['nonbookable_periods'],
                                        renamed={'start_dt': ('start_dt', room_availability_test.as_day),
                                                 'end_dt': ('end_dt', room_availability_test.as_day)},
                                        derived={'room_id': lambda _: room_id}, key='start_dt'))

    def check_reservation_edit_logs(self):
        reservation_id = self.manifest['reservation_id']
        ours = self.api.list(f'/reservations/{reservation_id}/edit-logs')
        theirs = self.api.cached(f'/rooms/api/bookings/{reservation_id}')['edit_logs']
        self.check('reservation-edit-logs', f'list {reservation_id}', len(ours),
                   lambda: compare_list(ours, theirs, same=reservation_edit_logs_test.EDIT_LOG_FIELDS,
                                        derived={'reservation_id': lambda _: reservation_id}))

    def check_reservation_links(self):
        for reservation_id in self.manifest['linked_reservation_ids']:
            ours = self.api.list(f'/reservations/{reservation_id}/links')
            theirs = self.api.get(f'/rooms/api/bookings/{reservation_id}/links')
            self.check('reservation-links', f'list {reservation_id}', len(ours),
                       lambda ours=ours, theirs=theirs: compare_list(
                           ours, theirs, same=reservation_links_test.LINK_FIELDS,
                           renamed=reservation_links_test.LINK_KEYS,
                           derived=reservation_links_test.link_derived(ours)))

    def check_category_logs(self):
        category_id = self.manifest['category_id']
        mappings = {'same': logs_test.LOG_FIELDS, 'renamed': logs_test.log_keys(self.tzinfo)}
        ours = self.api.list(f'/categories/{category_id}/logs')
        theirs = current_log_entries(self.api, f'/category/{category_id}/manage/logs/api/logs',
                                     category_logs_test.ALL_REALMS)
        self.check('category-logs', f'list {category_id}', len(ours),
                   lambda: compare_list(ours, theirs, **mappings))
        first = ours[0]
        one = self.api.ours(f'/categories/{category_id}/logs/{first["id"]}')
        current = next(entry for entry in theirs if entry['id'] == first['id'])
        self.check('category-logs', f'detail {first["id"]}', 1, lambda: compare(one, current, **mappings))

    def check_equipment(self):
        ours = self.api.list('/equipment-types')
        theirs = self.api.get('/rooms/api/equipment')
        self.check('equipment-types', 'list', len(ours),
                   lambda: compare_list(ours, theirs, same=equipment_test.EQUIPMENT_TYPE_FIELDS))
        first = ours[0]
        one = self.api.ours(f'/equipment-types/{first["id"]}')
        current = next(equipment for equipment in theirs if equipment['id'] == first['id'])
        self.check('equipment-types', f'detail {first["id"]}', 1,
                   lambda: compare(one, current, same=equipment_test.EQUIPMENT_TYPE_FIELDS))

    def check_room_features(self):
        ours = self.api.list('/room-features')
        # only the administration area lists the features on their own
        theirs = self.api.get('/rooms/api/admin/features')
        self.check('room-features', 'list', len(ours),
                   lambda: compare_list(ours, theirs, same=equipment_test.ROOM_FEATURE_FIELDS))
        first = ours[0]
        one = self.api.ours(f'/room-features/{first["id"]}')
        current = next(feature for feature in theirs if feature['id'] == first['id'])
        self.check('room-features', f'detail {first["id"]}', 1,
                   lambda: compare(one, current, same=equipment_test.ROOM_FEATURE_FIELDS))

    def check_affiliations(self):
        ours = self.api.list('/affiliations')
        # only the administration area lists the catalogue as a whole
        theirs = self.api.get('/api/admin/affiliations')
        self.check('affiliations', 'list', len(ours),
                   lambda: compare_list(ours, theirs, same=affiliations_test.AFFILIATION_FIELDS))
        first = ours[0]
        one = self.api.ours(f'/affiliations/{first["id"]}')
        current = next(affiliation for affiliation in theirs if affiliation['id'] == first['id'])
        self.check('affiliations', f'detail {first["id"]}', 1,
                   lambda: compare(one, current, same=affiliations_test.AFFILIATION_FIELDS))

    def check_catalogues(self):
        counts = self.manifest['counts']
        self.check_count('reference-types', '/reference-types', counts['reference_types'])
        self.check_count('event-labels', '/event-labels', counts['event_labels'])

    def check_registration_tags(self, event):
        event_id = event['id']
        ours = self.api.list(f'/events/{event_id}/registration-tags')
        theirs = self.api.cached(f'/api/checkin/event/{event_id}/')['registration_tags']
        self.check('registration-tags', f'list {event_id}', len(ours),
                   lambda: compare_list(ours, theirs, same=registration_tags_test.TAG_FIELDS))

    def check_layout(self, event):
        event_id = event['id']

        def run():
            if layout['announcement'] != event['announcement']:
                raise AssertionError(f'announcement {layout["announcement"]!r} instead of {event["announcement"]!r}')
            if layout['css_url'] is None:
                raise AssertionError('no stylesheet served')
            pages = [entry for entry in menu if entry['type'] == 'page']
            if len(pages) != event['pages']:
                raise AssertionError(f'{len(pages)} page entries in the menu instead of {event["pages"]}')

        layout = self.api.ours(f'/events/{event_id}/layout')
        menu = self.api.list(f'/events/{event_id}/menu')
        self.check('layout', f'event {event_id}', 1 + len(menu), run)

    def check_features(self, event):
        event_id = event['id']

        def run():
            enabled = sorted(feature['name'] for feature in features if feature['enabled'])
            if enabled != event['features']:
                raise AssertionError(f'enabled features {enabled} instead of {event["features"]}')

        features = self.api.list(f'/events/{event_id}/features')
        self.check('features', f'event {event_id}', len(features), run)

    def check_document_templates(self, event_id):
        ours = self.api.list(f'/events/{event_id}/document-templates')
        theirs = self.api.get(f'/event/{event_id}/manage/receipts/templates')
        self.check('document-templates', f'list {event_id}', len(ours),
                   lambda: compare_list(ours, theirs, same=receipts_test.TEMPLATE_FIELDS))
        first = ours[0]
        one = self.api.ours(f'/events/{event_id}/document-templates/{first["id"]}')
        current = next(template for template in theirs if template['id'] == first['id'])
        self.check('document-templates', f'detail {first["id"]}', 1,
                   lambda: compare(one, current, same=receipts_test.TEMPLATE_FIELDS))

    def check_designer_templates(self, event_id):
        mappings = {'same': ('title', 'data', 'background_url'),
                    'renamed': {'id': ('backside_template_id', None), 'images': ('images', designer_test.as_image_map)}}
        ours = self.api.list(f'/events/{event_id}/designer-templates')
        theirs = [designer_template_data(self.api, event_id, template['id']) for template in ours]
        self.check('designer-templates', f'list {event_id}', len(ours),
                   lambda: compare_list(ours, theirs, **mappings, key='id'))
        first = ours[0]
        one = self.api.ours(f'/events/{event_id}/designer-templates/{first["id"]}')
        self.check('designer-templates', f'detail {first["id"]}', 1, lambda: compare(one, theirs[0], **mappings))

    def check_groups(self):
        ours = self.api.list('/groups')
        theirs = [self.api.get(f'/groups/api/search?name={quote(group["name"])}&exact=true')['groups'][0]
                  for group in ours]
        stripped = [groups_test.without_members(group) for group in ours]
        self.check('groups', 'list', len(ours),
                   lambda: compare_list(stripped, theirs, same=groups_test.GROUP_FIELDS))
        first = ours[0]
        one = groups_test.without_members(self.api.ours(f'/groups/{first["id"]}'))
        self.check('groups', f'detail {first["id"]}', 1,
                   lambda: compare(one, theirs[0], same=groups_test.GROUP_FIELDS))

    def check_files(self):
        ours = self.api.list('/files')
        # the current API serves one file per call
        theirs = [self.api.get(f'/files/{file["uuid"]}') for file in ours]
        self.check('files', 'list', len(ours),
                   lambda: compare_list(ours, theirs, same=files_test.FILE_FIELDS, key='uuid'))

    def check_series(self):
        mappings = {'same': series_test.SERIES_FIELDS, 'derived': {'event_ids': series_test.as_event_ids}}
        ours = self.api.list('/event-series')
        theirs = [self.api.get(f'/event-series/{series["id"]}') for series in ours]
        self.check('event-series', 'list', len(ours), lambda: compare_list(ours, theirs, **mappings))
        first = ours[0]
        one = self.api.ours(f'/event-series/{first["id"]}')
        self.check('event-series', f'detail {first["id"]}', 1, lambda: compare(one, theirs[0], **mappings))

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
                    'renamed': {'available_equipment': ('available_equipment', as_ids)},
                    'derived': {'photo_url': rooms_test.as_photo_url}}
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
