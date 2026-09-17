# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

"""Fill an Indico instance with demo data for every entity the OpenAPI plugin serves.

Run it inside the Indico application context, passing the path of the manifest
to write:

    indico shell -r <<< "import runpy, sys; sys.argv = ['seed', '/tmp/demo.json']; \
runpy.run_path('scripts/seed_demo_data.py', run_name='__main__')"

``purge_demo_data.py`` removes the whole dataset. The script refuses to run
twice against the same instance, and a run that fails halfway leaves the rows it
already committed behind.

The manifest holds the ids the live parity checker needs plus a personal token
for the demo manager, whose password comes from the SEED_PASSWORD environment
variable.

Service requests are the one entity left out: a request needs a plugin that
defines its type, and none of the plugins shipped with Indico does.
"""

import json
import os
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile

import pytz
from PIL import Image

from indico.core.config import config
from indico.core.db import db
from indico.core.db.sqlalchemy.descriptions import RenderMode
from indico.core.db.sqlalchemy.util.management import DEFAULT_TICKET_DATA
from indico.core.oauth.models.personal_tokens import PersonalToken
from indico.modules.attachments.models.attachments import Attachment, AttachmentFile, AttachmentType
from indico.modules.attachments.models.folders import AttachmentFolder
from indico.modules.auth import Identity
from indico.modules.categories import Category
from indico.modules.designer import TemplateType
from indico.modules.designer.models.images import DesignerImageFile
from indico.modules.designer.models.templates import DesignerTemplate
from indico.modules.events import Event
from indico.modules.events.abstracts.models.abstracts import Abstract, AbstractState
from indico.modules.events.abstracts.models.files import AbstractFile
from indico.modules.events.abstracts.models.persons import AbstractPersonLink
from indico.modules.events.agreements.models.agreements import Agreement, AgreementState
from indico.modules.events.contributions.models.contributions import Contribution
from indico.modules.events.contributions.models.persons import (
    AuthorType,
    ContributionPersonLink,
    SubContributionPersonLink,
)
from indico.modules.events.contributions.models.subcontributions import SubContribution
from indico.modules.events.features.util import get_enabled_features, set_feature_enabled
from indico.modules.events.layout import layout_settings
from indico.modules.events.layout.models.images import ImageFile
from indico.modules.events.layout.models.menu import EventPage, MenuEntry, MenuEntryType
from indico.modules.events.layout.util import menu_entries_for_event
from indico.modules.events.models.events import EventType
from indico.modules.events.models.persons import EventPerson, EventPersonLink
from indico.modules.events.models.roles import EventRole
from indico.modules.events.models.series import EventSeries
from indico.modules.events.notes.models.notes import EventNote
from indico.modules.events.papers.models.files import PaperFile
from indico.modules.events.papers.models.papers import Paper
from indico.modules.events.papers.models.revisions import PaperRevision, PaperRevisionState
from indico.modules.events.payment.models.transactions import PaymentTransaction, TransactionStatus
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.registrations import PublishRegistrationsMode
from indico.modules.events.registration.models.tags import RegistrationTag
from indico.modules.events.registration.util import create_personal_data_fields, create_registration
from indico.modules.events.reminders.models.reminders import EventReminder, ReminderType
from indico.modules.events.sessions.models.blocks import SessionBlock
from indico.modules.events.sessions.models.persons import SessionBlockPersonLink
from indico.modules.events.sessions.models.sessions import Session
from indico.modules.events.static.models.static import StaticSite, StaticSiteState
from indico.modules.events.surveys.models.items import SurveyQuestion, SurveySection
from indico.modules.events.surveys.models.submissions import SurveyAnswer, SurveySubmission
from indico.modules.events.surveys.models.surveys import Survey
from indico.modules.events.timetable.models.breaks import Break
from indico.modules.events.timetable.models.entries import TimetableEntry, TimetableEntryType
from indico.modules.events.tracks.models.groups import TrackGroup
from indico.modules.events.tracks.models.tracks import Track
from indico.modules.files.models.files import File
from indico.modules.groups.models.groups import LocalGroup
from indico.modules.logs.models.entries import EventLogRealm, LogKind
from indico.modules.rb.models.blocked_rooms import BlockedRoom
from indico.modules.rb.models.blockings import Blocking
from indico.modules.rb.models.equipment import EquipmentType
from indico.modules.rb.models.locations import Location
from indico.modules.rb.models.reservations import RepeatFrequency, Reservation
from indico.modules.rb.models.rooms import Room
from indico.modules.receipts.models.files import ReceiptFile
from indico.modules.receipts.models.templates import ReceiptTemplate
from indico.modules.receipts.settings import receipt_defaults
from indico.modules.receipts.util import compile_jinja_code, create_pdf, get_safe_template_context
from indico.modules.users import User
from indico.modules.users.models.users import NameFormat
from indico.modules.vc.models.vc_rooms import VCRoom, VCRoomEventAssociation, VCRoomStatus
from indico.util.date_time import now_utc
from indico.util.string import crc32


CATEGORY_TITLE = 'OpenAPI demo data'
MANAGER_USERNAME = 'openapi.manager'
TOKEN_NAME = 'openapi-demo'  # noqa: S105
TOKEN_SCOPES = ['read:everything', 'read:legacy_api', 'registrants']
GROUP_NAMES = ('OpenAPI demo organisers', 'OpenAPI demo reviewers', 'OpenAPI demo speakers')

TOPICS = ('Accelerator physics', 'Computing', 'Detectors', 'Theory')
CONFERENCES_PER_TOPIC = 5
MEETING_COUNT = 4
USER_COUNT = 60

FIRST_NAMES = ('Ada', 'Bruno', 'Chiara', 'Diego', 'Elena', 'Farid', 'Greta', 'Hugo', 'Ilse', 'Jonas',
               'Katia', 'Lars', 'Mireia', 'Nadia', 'Olek', 'Pilar', 'Quim', 'Rosa', 'Sven', 'Tomas')
LAST_NAMES = ('Alvarez', 'Bianchi', 'Costa', 'Dubois', 'Eriksen', 'Fischer', 'Garcia', 'Horvath', 'Iversen',
              'Jankowski', 'Kowal', 'Lindgren', 'Moreau', 'Nowak', 'Oliveira', 'Petrov', 'Quintero', 'Rossi',
              'Silva', 'Tanaka')
AFFILIATIONS = ('CERN', 'DESY', 'Fermilab', 'INFN', 'KEK', 'PSI', 'RAL', 'SLAC')
COUNTRIES = ('CH', 'DE', 'ES', 'FR', 'IT', 'JP', 'GB', 'US')
CITIES = ('Geneva', 'Hamburg', 'Madrid', 'Paris', 'Rome', 'Tsukuba', 'Oxford', 'Menlo Park')
POSITIONS = ('Research fellow', 'Staff scientist', 'PhD student', 'Engineer', 'Professor')
BUILDINGS = ('30', '40', '80', '500', '513')
EQUIPMENT = ('Video conference', 'Webcast', 'Blackboard', 'Projector')
AGREEMENT_TYPES = ('speaker-release', 'data-protection')
SUBJECTS = ('beam dynamics', 'calorimetry', 'cryogenics', 'data acquisition', 'event reconstruction',
            'lattice QCD', 'machine learning', 'magnet design', 'radiation hardness', 'silicon trackers',
            'superconductivity', 'trigger systems', 'vacuum systems', 'wakefields', 'neutrino oscillations')
COLORS = ('1f77b4', 'ff7f0e', '2ca02c', 'd62728', '9467bd', '8c564b')
ROLES = (('Programme Committee', 'PC'), ('Local Organisers', 'LOC'), ('Reviewers', 'REV'))
CONFERENCE_THEMES = ('orange.css', 'brown.css', 'right_menu.css')
REGISTRATION_FEE = Decimal('40.00')

CERTIFICATE_YAML = """\
custom_fields:
  - name: signatory
    type: input
    attributes:
      label: Signatory
      value: Head of department
"""
CERTIFICATE_HTML = """\
<h1>Certificate of attendance</h1>
<p>{{ registration.personal_data.first_name }} {{ registration.personal_data.last_name }}
attended {{ event.title }}.</p>
<p>{{ custom_fields.signatory }}</p>
"""
INVOICE_YAML = """\
custom_fields:
  - name: reason
    type: input
    attributes:
      label: Reason
  - name: tier
    type: dropdown
    attributes:
      label: Tier
      options: [early bird, regular, student]
"""
INVOICE_HTML = """\
<h1>{{ event.title }}</h1>
<p>{{ registration.personal_data.first_name }} {{ registration.personal_data.last_name }},
{{ registration.personal_data.affiliation }}</p>
<p>Registration #{{ registration.friendly_id }}: {{ registration.formatted_price }}</p>
<p>{{ custom_fields.reason }} ({{ custom_fields.tier }})</p>
"""
INVOICE_DEFAULTS = {'reason': 'Conference fee', 'tier': 'regular'}


class Sequence:
    """Deterministic round robin over a list, so two runs build the same dataset."""

    def __init__(self, values):
        self.values = tuple(values)
        self.index = 0

    def next(self):
        value = self.values[self.index % len(self.values)]
        self.index += 1
        return value


def pick(values, index):
    return values[index % len(values)]


def midnight(day):
    return pytz.utc.localize(datetime.combine(day, time(7, 0)))


def png_image(color, size=(160, 60)):
    buffer = BytesIO()
    Image.new('RGB', size, f'#{color}').save(buffer, 'PNG')
    return buffer.getvalue()


def zip_archive(files):
    buffer = BytesIO()
    with ZipFile(buffer, 'w') as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def create_users():
    users = []
    for i in range(USER_COUNT):
        first_name = pick(FIRST_NAMES, i)
        last_name = pick(LAST_NAMES, i * 7)
        username = f'openapi.user{i:02d}'
        user = User(first_name=first_name, last_name=last_name, email=f'{username}@example.test',
                    affiliation=pick(AFFILIATIONS, i))
        user.identities.add(Identity(provider='indico', identifier=username, password=os.environ['SEED_PASSWORD']))
        db.session.add(user)
        users.append(user)
    db.session.flush()
    return users


def create_manager():
    manager = User(first_name='Olivia', last_name='Manager', email=f'{MANAGER_USERNAME}@example.test',
                   affiliation='CERN')
    manager.identities.add(Identity(provider='indico', identifier=MANAGER_USERNAME,
                                    password=os.environ['SEED_PASSWORD']))
    manager.is_admin = True
    db.session.add(manager)
    db.session.flush()
    return manager


def create_categories(root):
    demo = Category(title=CATEGORY_TITLE, parent=root, timezone=config.DEFAULT_TIMEZONE, acl_entries=set(),
                    description='Every entity the read-only REST API serves, with enough rows to page through.')
    db.session.add(demo)
    topics = [Category(title=title, parent=demo, timezone=config.DEFAULT_TIMEZONE, acl_entries=set(),
                       description=f'Demo events about {title.lower()}.')
              for title in TOPICS]
    db.session.add_all(topics)
    db.session.flush()
    return demo, topics


def create_event(category, manager, title, start, event_type, days):
    event = Event(creator=manager, category=category, title=title, type_=event_type, acl_entries=set(),
                  start_dt=start, end_dt=start + timedelta(days=days, hours=9), timezone=config.DEFAULT_TIMEZONE,
                  description=f'Demo event: {title}.')
    event.update_principal(manager, full_access=True)
    # friendly ids are drawn from the event row through a separate connection,
    # so nothing inside the event can be created before the event is committed
    db.session.commit()
    return event


def create_persons(event, users, count, offset):
    persons = []
    for i in range(count):
        user = pick(users, offset + i)
        person = EventPerson(event=event, user=user, first_name=user.first_name, last_name=user.last_name,
                             email=user.email, affiliation=user.affiliation)
        db.session.add(person)
        persons.append(person)
    db.session.flush()
    return persons


def create_tracks(event, index):
    group = TrackGroup(event=event, title=f'Programme {index + 1}', description='Grouped tracks.')
    db.session.add(group)
    tracks = []
    for i in range(3):
        subject = pick(SUBJECTS, index * 3 + i)
        track = Track(event=event, title=subject.capitalize(), code=f'T{i + 1}',
                      description=f'Contributions about {subject}.',
                      track_group=(group if i < 2 else None))
        db.session.add(track)
        tracks.append(track)
    db.session.flush()
    return group, tracks


def create_sessions(event, persons, count, blocks_per_session, start):
    sessions, blocks = [], []
    for i in range(count):
        sess = Session(event=event, title=f'Session {chr(ord("A") + i)}', code=f'S{i + 1}',
                       description='Demo session.')
        db.session.add(sess)
        db.session.flush()
        sessions.append(sess)
        for j in range(blocks_per_session):
            block_start = start + timedelta(days=i, hours=j * 4)
            block = SessionBlock(session=sess, title=f'Block {j + 1}', duration=timedelta(hours=3))
            block.person_links.append(SessionBlockPersonLink(person=pick(persons, i + j)))
            db.session.add(block)
            db.session.flush()
            entry = TimetableEntry(event=event, start_dt=block_start, type=TimetableEntryType.SESSION_BLOCK)
            entry.object = block
            db.session.add(entry)
            blocks.append(block)
    db.session.flush()
    return sessions, blocks


def create_contributions(event, persons, tracks, blocks, count, index):
    contributions = []
    for i in range(count):
        subject = pick(SUBJECTS, index + i)
        contrib = Contribution(event=event, title=f'Progress on {subject}', duration=timedelta(minutes=20),
                               description=f'A demo contribution about {subject}.', code=f'C{i + 1:03d}',
                               keywords=[subject.split()[0], 'demo'],
                               track=(pick(tracks, i) if tracks else None))
        contrib.person_links.append(ContributionPersonLink(person=pick(persons, i), is_speaker=True,
                                                           author_type=AuthorType.primary, display_order=0))
        contrib.person_links.append(ContributionPersonLink(person=pick(persons, i + 3), is_speaker=False,
                                                           author_type=AuthorType.secondary, display_order=1))
        db.session.add(contrib)
        db.session.flush()
        block = pick(blocks, i)
        contrib.session = block.session
        contrib.session_block = block
        start = block.timetable_entry.start_dt + timedelta(minutes=25 * (i // len(blocks)))
        entry = TimetableEntry(event=event, start_dt=start, type=TimetableEntryType.CONTRIBUTION,
                               parent=block.timetable_entry)
        entry.object = contrib
        db.session.add(entry)
        db.session.flush()
        entry.extend_parent()
        contributions.append(contrib)
    # subcontributions draw their friendly id from the contribution row
    db.session.commit()
    return contributions


def create_subcontributions(contributions, persons):
    subcontributions = []
    for i, contrib in enumerate(contributions):
        for j in range(1 + i % 2):
            subcontrib = SubContribution(contribution=contrib, title=f'{contrib.title}: part {j + 1}',
                                         duration=timedelta(minutes=8), description='A demo subcontribution.',
                                         code=f'{contrib.code}.{j + 1}')
            subcontrib.person_links.append(SubContributionPersonLink(person=pick(persons, i + j)))
            db.session.add(subcontrib)
            subcontributions.append(subcontrib)
    db.session.flush()
    return subcontributions


def create_breaks(event, blocks, count, start):
    breaks = []
    for i in range(count):
        break_ = Break(title=pick(('Coffee break', 'Lunch', 'Poster session'), i), duration=timedelta(minutes=30),
                       description='A demo break.')
        db.session.add(break_)
        db.session.flush()
        parent = blocks[i].timetable_entry if i < len(blocks) else None
        entry_start = (parent.start_dt + timedelta(hours=2)) if parent else (start + timedelta(days=i, hours=12))
        entry = TimetableEntry(event=event, start_dt=entry_start, type=TimetableEntryType.BREAK, parent=parent)
        entry.object = break_
        db.session.add(entry)
        db.session.flush()
        entry.extend_parent()
        breaks.append(break_)
    db.session.flush()
    return breaks


def create_note(obj, author, html):
    note = EventNote.get_or_create(obj)
    note.create_revision(RenderMode.html, html, author)
    db.session.flush()
    return note


def create_file_attachment(obj, author, title, description):
    folder = AttachmentFolder(object=obj, title='Slides', description='Material shown during the talk.')
    file = AttachmentFile(user=author, filename='slides.txt', content_type='text/plain')
    attachment = Attachment(folder=folder, user=author, type=AttachmentType.file, file=file, title=title,
                            description=description)
    file.save(f'{title}\n'.encode())
    db.session.flush()
    return attachment


def create_link_attachment(obj, author, title, url):
    folder = AttachmentFolder(object=obj, title='Links', description='External material.')
    attachment = Attachment(folder=folder, user=author, type=AttachmentType.link, title=title, link_url=url,
                            description='A demo link.')
    db.session.flush()
    return attachment


def create_abstracts(event, persons, tracks, users, count, index):
    abstracts = []
    for i in range(count):
        subject = pick(SUBJECTS, index + i)
        abstract = Abstract(event=event, title=f'Abstract on {subject}', submitter=pick(users, index + i),
                            description=f'We report on {subject} and its demo implications.',
                            submitted_dt=event.start_dt - timedelta(days=30 - i))
        for j in range(2):
            abstract.person_links.append(AbstractPersonLink(person=pick(persons, i + j), is_speaker=(j == 0),
                                                            author_type=AuthorType.primary, display_order=j))
        if i % 3 == 0:
            abstract.state = AbstractState.accepted
            abstract.judge = pick(users, index)
            abstract.judgment_dt = event.start_dt - timedelta(days=10)
            abstract.judgment_comment = 'Accepted for a talk.'
            abstract.accepted_track = pick(tracks, i)
        elif i % 3 == 1:
            abstract.state = AbstractState.rejected
            abstract.judge = pick(users, index)
            abstract.judgment_dt = event.start_dt - timedelta(days=10)
            abstract.judgment_comment = 'Out of scope.'
        db.session.add(abstract)
        db.session.flush()
        file = AbstractFile(filename='abstract.txt', content_type='text/plain', abstract=abstract)
        file.save(f'{abstract.title}\n'.encode())
        abstracts.append(abstract)
    db.session.flush()
    return abstracts


def create_papers(contributions, users, index):
    papers = []
    for i, contrib in enumerate(contributions):
        paper = Paper(contrib)
        submitter = pick(users, index + i)
        for j in range(1 + i % 2):
            revision = PaperRevision(paper=paper, submitter=submitter,
                                     submitted_dt=contrib.event.start_dt - timedelta(days=20 - j))
            db.session.add(revision)
            db.session.flush()
            paper_file = PaperFile(filename='paper.txt', content_type='text/plain', paper_revision=revision,
                                   _contribution=contrib)
            paper_file.save(f'{contrib.title}\n'.encode())
        if i % 2 == 0:
            revision.state = PaperRevisionState.accepted
            revision.judge = pick(users, index)
            revision.judgment_dt = contrib.event.start_dt - timedelta(days=5)
            revision.judgment_comment = 'Ready to publish.'
        db.session.flush()
        papers.append(paper)
    return papers


def create_regform(event, users, count, index):
    regform = RegistrationForm(event=event, title='Participant registration', currency='EUR',
                               base_price=REGISTRATION_FEE, introduction='Register for the demo event.',
                               start_dt=event.start_dt - timedelta(days=60),
                               end_dt=event.start_dt - timedelta(days=1),
                               publish_registrations_public=PublishRegistrationsMode.show_all,
                               publish_registrations_participants=PublishRegistrationsMode.show_all,
                               publish_checkin_enabled=True, publish_registration_count=True)
    create_personal_data_fields(regform)
    for field in regform.sections[0].fields:
        field.is_enabled = True
    db.session.add(regform)
    db.session.flush()

    registrations = []
    for i in range(count):
        user = pick(users, index + i)
        values = {'first_name': user.first_name, 'last_name': user.last_name, 'email': user.email,
                  'affiliation': user.affiliation, 'position': pick(POSITIONS, i), 'country': pick(COUNTRIES, i),
                  'address': f'{i + 1} Demo street', 'city': pick(CITIES, i), 'phone': f'+41 22 767 {i:04d}'}
        data = {'email': user.email}
        for field in regform.active_fields:
            pd_type = field.personal_data_type
            if pd_type is not None and pd_type.name in values:
                data[field.html_field_name] = values[pd_type.name]
        registration = create_registration(regform, data, management=True, notify_user=False)
        registration.checked_in = (i % 4 == 0)
        registrations.append(registration)
    db.session.flush()
    return regform, registrations


def create_survey(event, users, count, index):
    survey = Survey(event=event, title='How did it go?', introduction='Tell us what you think.',
                    start_dt=event.start_dt, end_dt=event.end_dt + timedelta(days=30))
    section = SurveySection(survey=survey, title='General', description='Overall impression.',
                            display_as_section=True, position=1)
    options = [{'id': str(uuid4()), 'option': label, 'is_enabled': True}
               for label in ('Excellent', 'Good', 'Poor')]
    questions = [
        SurveyQuestion(survey=survey, parent=section, title='Your name', description='As you want it published.',
                       field_type='text', is_required=True, position=1, field_data={}),
        SurveyQuestion(survey=survey, parent=section, title='Comments', description='Anything else.',
                       field_type='text', is_required=False, position=2, field_data={'multiline': True}),
        SurveyQuestion(survey=survey, parent=section, title='Talks attended', description='How many.',
                       field_type='number', is_required=False, position=3, field_data={'min_value': 0}),
        SurveyQuestion(survey=survey, parent=section, title='Overall rating', description='Pick one.',
                       field_type='single_choice', is_required=False, position=4,
                       field_data={'options': options, 'display': 'radio', 'with_extra_fields': False}),
    ]
    db.session.add(survey)
    # submissions draw their friendly id from the survey row
    db.session.commit()

    submissions = []
    for i in range(count):
        user = pick(users, index + i)
        submission = SurveySubmission(survey=survey, user=user, is_submitted=True,
                                      submitted_dt=event.end_dt + timedelta(days=1, hours=i))
        answers = (user.full_name, f'Demo answer {i}', i % 7, pick(options, i)['id'])
        for question, answer in zip(questions, answers, strict=True):
            submission.answers.append(SurveyAnswer(question=question, data=answer))
        db.session.add(submission)
        submissions.append(submission)
    db.session.flush()
    return survey, questions, submissions


def create_agreements(event, persons, count):
    agreements = []
    for i in range(count):
        person = pick(persons, i)
        state = pick((AgreementState.pending, AgreementState.accepted, AgreementState.rejected,
                      AgreementState.accepted_on_behalf), i)
        agreement = Agreement(uuid=str(uuid4()), event=event, type=pick(AGREEMENT_TYPES, i),
                              identifier=f'Email:{person.email}', person_name=person.full_name,
                              person_email=person.email, state=state, user=person.user,
                              timestamp=event.start_dt - timedelta(days=20 - i))
        if state != AgreementState.pending:
            agreement.signed_dt = event.start_dt - timedelta(days=15 - i)
            agreement.reason = 'Signed for the demo dataset.'
        db.session.add(agreement)
        agreements.append(agreement)
    db.session.flush()
    return agreements


def get_equipment():
    equipment = []
    for name in EQUIPMENT:
        eq = EquipmentType.query.filter_by(name=name).first()
        if eq is None:
            eq = EquipmentType(name=name)
            db.session.add(eq)
        equipment.append(eq)
    db.session.flush()
    return equipment


def create_rooms(manager, users, equipment):
    locations, rooms = [], []
    for i, name in enumerate(('Meyrin', 'Prevessin', 'Remote')):
        location = Location(name=name)
        db.session.add(location)
        db.session.flush()
        locations.append(location)
        for j in range(10):
            room = Room(location=location, owner=pick(users, i * 10 + j), building=pick(BUILDINGS, j),
                        floor=str(j % 4), number=f'{i}{j:02d}', verbose_name=f'{name} room {j + 1}',
                        capacity=10 + 5 * j, surface_area=20 + 3 * j, division='DG',
                        telephone=f'+41 22 767 {i}{j:03d}', key_location='Reception',
                        comments='Demo room.', max_advance_days=30, site=name)
            room.available_equipment = [pick(equipment, j), pick(equipment, j + 1)]
            db.session.add(room)
            rooms.append(room)
    db.session.flush()
    return locations, rooms


def create_reservations(rooms, users, count):
    reservations = []
    first_day = date.today() + timedelta(days=1)
    for i in range(count):
        room = pick(rooms, i)
        day = first_day + timedelta(days=i // len(rooms))
        start = midnight(day) + timedelta(hours=1 + (i % 6))
        frequency = pick((RepeatFrequency.NEVER, RepeatFrequency.NEVER, RepeatFrequency.WEEK), i)
        reservation = Reservation(room=room, start_dt=start, end_dt=start + timedelta(hours=1),
                                  repeat_frequency=frequency,
                                  repeat_interval=int(frequency != RepeatFrequency.NEVER),
                                  booking_reason=f'Demo booking {i + 1}', booked_for_user=pick(users, i),
                                  created_by_user=pick(users, i + 1))
        reservation.create_occurrences(skip_conflicts=True)
        db.session.add(reservation)
        reservations.append(reservation)
    db.session.flush()
    return reservations


def create_blockings(rooms, users, count):
    blockings = []
    first_day = date.today() + timedelta(days=60)
    for i in range(count):
        day = first_day + timedelta(days=i)
        blocking = Blocking(start_date=day, end_date=day + timedelta(days=1), reason=f'Demo blocking {i + 1}',
                            created_by_user=pick(users, i))
        state = pick((BlockedRoom.State.pending, BlockedRoom.State.accepted, BlockedRoom.State.rejected), i)
        blocked = BlockedRoom(room=pick(rooms, i), state=state, blocking=blocking)
        if state == BlockedRoom.State.rejected:
            blocked.rejected_by = 'Demo manager'
            blocked.rejection_reason = 'The room is needed for an event.'
        db.session.add(blocking)
        blockings.append(blocking)
    db.session.flush()
    return blockings


def create_roles(event, users, index):
    roles = []
    for i, (name, code) in enumerate(ROLES):
        role = EventRole(event=event, name=name, code=code, color=pick(COLORS, index + i),
                         members={pick(users, index * 5 + i * 3 + j) for j in range(2 + i)})
        db.session.add(role)
        roles.append(role)
    db.session.flush()
    return roles


def create_groups(users):
    groups = []
    for i, name in enumerate(GROUP_NAMES):
        group = LocalGroup(name=name, members={pick(users, i * 7 + j) for j in range(4 + i)})
        db.session.add(group)
        groups.append(group)
    db.session.flush()
    return groups


def create_reminders(event, manager, regform=None):
    tags = set()
    if regform is not None:
        tag = RegistrationTag(event=event, title='VIP', color='blue')
        db.session.add(tag)
        tags.add(tag)
    reminders = [
        EventReminder(event=event, creator=manager, scheduled_dt=event.start_dt - timedelta(days=1),
                      event_start_delta=timedelta(days=1), reminder_type=ReminderType.standard,
                      subject='See you tomorrow', message='<p>Doors open at 8:30.</p>',
                      recipients=[manager.email], reply_to_address=manager.email,
                      send_to_participants=regform is not None, send_to_speakers=True, include_summary=True,
                      forms={regform} if regform else set(), tags=tags),
        EventReminder(event=event, creator=manager, scheduled_dt=event.start_dt - timedelta(days=30),
                      reminder_type=ReminderType.custom, subject='Registration is open',
                      message='<p>Register before the deadline.</p>', recipients=[manager.email],
                      reply_to_address=manager.email, is_sent=True, attach_ical=False),
    ]
    db.session.add_all(reminders)
    db.session.flush()
    return reminders


def create_log_entries(event, manager, registrations=()):
    entries = [
        event.log(EventLogRealm.event, LogKind.change, 'Event', 'Description updated', manager,
                  data={'Description': ['A demo event.', event.description, 'text']}),
        event.log(EventLogRealm.management, LogKind.positive, 'Protection', 'Access restricted to participants',
                  manager, data={'Mode': 'protected'}),
        event.log(EventLogRealm.reviewing, LogKind.negative, 'Abstracts', 'Abstract rejected',
                  data={'Reason': 'Out of scope'}),
    ]
    entries += [event.log(EventLogRealm.participants, LogKind.other, 'Registration',
                          f'Registration of {registration.full_name} modified', manager,
                          data={'Affiliation': [registration.user.affiliation, 'CERN', 'string']},
                          meta={'registration_id': registration.id})
                for registration in registrations[:3]]
    for i, entry in enumerate(entries):
        entry.logged_dt = now_utc() - timedelta(hours=len(entries) - i)
    db.session.flush()
    return entries


def create_payments(registrations, manager):
    transactions = []
    manual = {'changed_by_name': manager.full_name, 'changed_by_id': manager.id}
    for i, registration in enumerate(registrations):
        if i % 3 == 2:
            continue
        paid = i % 3 == 0
        if i == 0:
            cancelled = PaymentTransaction(amount=registration.price, currency=registration.currency,
                                           provider='_manual', data=manual, status=TransactionStatus.cancelled,
                                           timestamp=now_utc() - timedelta(days=1))
            registration.transactions.append(cancelled)
            transactions.append(cancelled)
        transaction = PaymentTransaction(amount=registration.price, currency=registration.currency,
                                         provider='_manual' if paid else 'paypal',
                                         data=manual if paid else {'order_id': f'DEMO-{registration.friendly_id:04d}'},
                                         status=TransactionStatus.successful if paid else TransactionStatus.pending,
                                         timestamp=now_utc() - timedelta(hours=i))
        registration.transactions.append(transaction)
        registration.transaction = transaction
        if paid:
            registration.update_state(paid=True)
        transactions.append(transaction)
    db.session.flush()
    return transactions


def create_vc_rooms(event, manager, contributions, index):
    rooms = []
    specs = ((f'{event.title} plenary', event, True), (f'{event.title} side room', contributions[0], True),
             (f'{event.title} rehearsal', event, False))
    for i, (name, link_object, show) in enumerate(specs):
        zoom_id = str(9000000000 + index * 10 + i)
        vc_room = VCRoom(name=name, type='zoom', status=VCRoomStatus.created, created_by_user=manager, data={
            'zoom_id': zoom_id, 'url': f'https://zoom.example.test/j/{zoom_id}',
            'public_url': f'https://zoom.example.test/j/{zoom_id}',
            'start_url': f'https://zoom.example.test/s/{zoom_id}', 'host': manager.persistent_identifier,
            'meeting_type': 'regular', 'description': 'Demo Zoom meeting.', 'password': '123456',
            'alternative_hosts': '', 'mute_audio': False, 'mute_host_video': False, 'mute_participant_video': True,
            'waiting_room': True, 'auto_register': False, 'registration_required': False, 'registration_forms': [],
            'language_interpretation': False, 'interpreters': [], 'auto_checkin': False,
        })
        # linking fires listeners that fill in the event and the link type, and an
        # autoflush in between would write the row before they ran
        with db.session.no_autoflush:
            assoc = VCRoomEventAssociation(vc_room=vc_room, show=show, data={'password_visibility': 'everyone'})
            assoc.link_object = link_object
        db.session.add(assoc)
        rooms.append(assoc)
    db.session.flush()
    return rooms


def create_offline_copies(event, manager):
    sites = []
    for i, state in enumerate((StaticSiteState.success, StaticSiteState.failed, StaticSiteState.pending)):
        site = StaticSite(event=event, creator=manager, state=state,
                          requested_dt=now_utc() - timedelta(days=3 - i))
        db.session.add(site)
        if state == StaticSiteState.success:
            site.content_type = 'application/zip'
            site.filename = f'offline_site_{event.id}.zip'
            site.save(zip_archive({'index.html': f'<h1>{event.title}</h1>'}))
        sites.append(site)
    db.session.flush()
    return sites


def create_series(events, **kwargs):
    series = EventSeries(events=events, **kwargs)
    db.session.add(series)
    db.session.flush()
    return series


def create_layout(event, index):
    logo = png_image(pick(COLORS, index))
    event.logo = logo
    event.logo_metadata = {'hash': crc32(logo), 'size': len(logo), 'filename': 'logo.png',
                           'content_type': 'image/png'}
    stylesheet = f'h1 {{ color: #{pick(COLORS, index)}; }}'
    event.stylesheet = stylesheet
    event.stylesheet_metadata = {'hash': crc32(stylesheet), 'size': len(stylesheet), 'filename': 'custom.css'}
    layout_settings.set_multi(event, {
        'use_custom_css': index % 2 == 0,
        'theme': pick(CONFERENCE_THEMES, index),
        'announcement': f'Registration for {event.title} closes soon.',
        'show_announcement': index % 3 != 2,
        'show_banner': True,
        'header_text_color': '#ffffff',
        'header_background_color': f'#{pick(COLORS, index)}',
        'name_format': NameFormat.first_last,
        'timetable_theme': 'indico_weeks_view',
        'show_vc_rooms': True,
        'use_custom_menu': True,
    })
    # Indico stores the default entries the first time the menu is read, and only then can they be customised
    menu_entries_for_event(event)
    pages = []
    for title, html in (('Venue', '<p>How to reach the venue.</p>'), ('Accommodation', '<p>Hotels nearby.</p>')):
        page = EventPage(event=event, html=html)
        db.session.add(MenuEntry(event=event, type=MenuEntryType.page, page=page, title=title))
        pages.append(page)
    links = MenuEntry(event=event, type=MenuEntryType.user_link, title='Useful links', link_url='https://getindico.io')
    db.session.add(links)
    db.session.flush()
    db.session.add(MenuEntry(event=event, type=MenuEntryType.user_link, title='Documentation', new_tab=True,
                             link_url='https://docs.getindico.io', parent_id=links.id))
    db.session.add(MenuEntry(event=event, type=MenuEntryType.separator))
    set_feature_enabled(event, 'images', True)
    images = []
    for i, name in enumerate(('sponsor', 'venue-map')):
        image = ImageFile(event=event, filename=f'{name}.png', content_type='image/png')
        image.save(BytesIO(png_image(pick(COLORS, index + i + 1))))
        db.session.add(image)
        images.append(image)
    db.session.flush()
    return pages, images


def create_receipt_template(title, html, yaml, default_filename, **owner):
    template = ReceiptTemplate(title=title, html=html, css='h1 { color: #1f77b4; }', yaml=yaml,
                               default_filename=default_filename, **owner)
    db.session.add(template)
    db.session.flush()
    return template


def create_documents(event, template, registrations, custom_fields):
    documents = []
    for i, registration in enumerate(registrations):
        context = get_safe_template_context(event, registration, custom_fields)
        pdf = create_pdf(event, [compile_jinja_code(template.html, context)], template.css)
        file = File(filename=f'{template.default_filename}-{registration.friendly_id}.pdf',
                    content_type='application/pdf', meta={'event_id': event.id})
        file.save(('event', event.id, 'registration', registration.id, 'receipts'), pdf)
        file.claim()
        document = ReceiptFile(file=file, registration=registration, template=template,
                               template_params=custom_fields, is_published=(i % 2 == 0))
        db.session.add(document)
        documents.append(document)
    db.session.flush()
    return documents


def create_designer_template(title, type_, data, index, **owner):
    template = DesignerTemplate(title=title, type=type_, data=data, is_clonable=True, **owner)
    db.session.add(template)
    db.session.flush()
    for i, name in enumerate(('background', 'logo')):
        image = DesignerImageFile(filename=f'{name}.png', content_type='image/png', template=template)
        image.save(BytesIO(png_image(pick(COLORS, index + i), size=(400, 300))))
        if name == 'background':
            template.background_image = image
    db.session.flush()
    return template


def create_uploads(event, count):
    files = []
    for i in range(count):
        file = File(filename=f'upload-{i + 1}.txt', content_type='text/plain', meta={'event_id': event.id})
        file.save(('event', event.id, 'uploads'), f'Upload {i + 1} for {event.title}\n'.encode())
        db.session.add(file)
        files.append(file)
    db.session.flush()
    return files


def seed_conference(category, manager, users, index, start):
    title = f'{category.title} Conference {index % CONFERENCES_PER_TOPIC + 1}'
    event = create_event(category, manager, title, start, EventType.conference, days=2)
    for feature in ('abstracts', 'papers', 'registration', 'payment', 'surveys'):
        set_feature_enabled(event, feature, True)

    persons = create_persons(event, users, 12, index * 5)
    for i in range(3):
        event.person_links.append(EventPersonLink(person=persons[i]))
    group, tracks = create_tracks(event, index)
    sessions, blocks = create_sessions(event, persons, 3, 2, start)
    contributions = create_contributions(event, persons, tracks, blocks, 15, index)
    subcontributions = create_subcontributions(contributions, persons)
    breaks = create_breaks(event, blocks, 3, start)

    notes = [create_note(event, manager, f'<p>Minutes of {title}.</p>')]
    notes += [create_note(contributions[i], manager, f'<p>Notes for {contributions[i].title}.</p>')
              for i in range(4)]
    notes.append(create_note(sessions[0], manager, '<p>Session minutes.</p>'))

    attachments = [create_file_attachment(event, manager, 'Programme', 'The full programme.'),
                   create_link_attachment(event, manager, 'Indico', 'https://getindico.io'),
                   create_file_attachment(contributions[0], manager, 'Talk slides', 'Slides of the opening talk.'),
                   create_link_attachment(contributions[1], manager, 'Preprint', 'https://arxiv.org'),
                   create_file_attachment(sessions[0], manager, 'Session notes', 'Shared during the session.')]

    abstracts = create_abstracts(event, persons, tracks, users, 10, index)
    papers = create_papers(contributions[:8], users, index)
    regform, registrations = create_regform(event, users, 15, index * 3)
    payments = create_payments(registrations, manager)
    survey, questions, submissions = create_survey(event, users, 8, index * 2)
    agreements = create_agreements(event, persons, 6)

    roles = create_roles(event, users, index)
    reminders = create_reminders(event, manager, regform)
    log_entries = create_log_entries(event, manager, registrations)
    vc_rooms = create_vc_rooms(event, manager, contributions, index)
    offline_copies = create_offline_copies(event, manager)
    pages, images = create_layout(event, index)
    receipt_template = create_receipt_template('Invoice', INVOICE_HTML, INVOICE_YAML, 'invoice', event=event)
    receipt_defaults.set_multi(event, {f'custom_fields:{receipt_template.id}': INVOICE_DEFAULTS,
                                       f'filename:{receipt_template.id}': 'invoice'})
    documents = create_documents(event, receipt_template, registrations[:3], INVOICE_DEFAULTS)
    designer_template = create_designer_template(f'{title} badge', TemplateType.badge, DEFAULT_TICKET_DATA, index,
                                                 event=event)
    uploads = create_uploads(event, 2)

    return {
        'event': event, 'persons': persons, 'track_group': group, 'tracks': tracks, 'sessions': sessions,
        'blocks': blocks, 'contributions': contributions, 'subcontributions': subcontributions, 'breaks': breaks,
        'notes': notes, 'attachments': attachments, 'abstracts': abstracts, 'papers': papers, 'regform': regform,
        'registrations': registrations, 'payments': payments, 'survey': survey, 'questions': questions,
        'submissions': submissions, 'agreements': agreements, 'roles': roles, 'reminders': reminders,
        'log_entries': log_entries, 'vc_rooms': vc_rooms, 'offline_copies': offline_copies, 'pages': pages,
        'images': images, 'receipt_templates': [receipt_template], 'documents': documents,
        'designer_templates': [designer_template], 'uploads': uploads,
    }


def seed_meeting(category, manager, users, index, start):
    title = f'Demo meeting {index + 1}'
    event = create_event(category, manager, title, start, EventType.meeting, days=0)
    persons = create_persons(event, users, 6, index * 4)
    sessions, blocks = create_sessions(event, persons, 1, 1, start)
    contributions = create_contributions(event, persons, [], blocks, 8, index)
    subcontributions = create_subcontributions(contributions, persons)
    breaks = create_breaks(event, blocks, 2, start)
    notes = [create_note(event, manager, f'<p>Minutes of {title}.</p>')]
    attachments = [create_file_attachment(event, manager, 'Agenda', 'The agenda of the meeting.'),
                   create_link_attachment(event, manager, 'Indico', 'https://getindico.io')]
    reminders = create_reminders(event, manager)
    log_entries = create_log_entries(event, manager)
    vc_rooms = create_vc_rooms(event, manager, contributions, CONFERENCES_PER_TOPIC * len(TOPICS) + index)
    return {
        'event': event, 'persons': persons, 'sessions': sessions, 'blocks': blocks,
        'contributions': contributions, 'subcontributions': subcontributions, 'breaks': breaks, 'notes': notes,
        'attachments': attachments, 'reminders': reminders, 'log_entries': log_entries, 'vc_rooms': vc_rooms,
    }


def describe(dataset):
    notes = dataset['notes']
    folders = [attachment.folder for attachment in dataset['attachments']]
    documents = {}
    for document in dataset.get('documents', ()):
        documents[document.registration_id] = documents.get(document.registration_id, 0) + 1
    return {
        'id': dataset['event'].id,
        'type': dataset['event'].type,
        'note_contributions': [note.contribution_id for note in notes if note.contribution_id],
        'note_sessions': [note.session_id for note in notes if note.session_id],
        'attachment_contributions': sorted({f.contribution_id for f in folders if f.contribution_id}),
        'attachment_sessions': sorted({f.session_id for f in folders if f.session_id}),
        'roles': len(dataset.get('roles', ())),
        'reminders': len(dataset['reminders']),
        'payments': len(dataset.get('payments', ())),
        'vc_rooms': len(dataset['vc_rooms']),
        'offline_copies': len(dataset.get('offline_copies', ())),
        'pages': len(dataset.get('pages', ())),
        'images': len(dataset.get('images', ())),
        'documents': documents,
        'features': sorted(get_enabled_features(dataset['event'])),
        'announcement': (layout_settings.get(dataset['event'], 'announcement')
                         if layout_settings.get(dataset['event'], 'show_announcement') else None),
    }


def count_all(datasets, key):
    return sum(len(dataset.get(key, ())) for dataset in datasets)


def main(manifest_path):
    if Category.query.filter_by(title=CATEGORY_TITLE, is_deleted=False).first():
        raise SystemExit(f'"{CATEGORY_TITLE}" already exists, delete it before seeding again')

    manager = create_manager()
    users = create_users()
    groups = create_groups(users)
    demo, topics = create_categories(Category.get_root())
    category_templates = [
        create_receipt_template('Attendance certificate', CERTIFICATE_HTML, CERTIFICATE_YAML, 'certificate',
                                category=demo),
    ]
    poster_data = {**DEFAULT_TICKET_DATA, 'width': 2480, 'height': 3508,
                   'items': [item for item in DEFAULT_TICKET_DATA['items'] if item['type'] != 'ticket_qr_code']}
    category_designer_templates = [
        create_designer_template('Demo poster', TemplateType.poster, poster_data, 0, category=demo),
    ]

    start = midnight(date.today() + timedelta(days=7))
    conferences = []
    for topic_index, topic in enumerate(topics):
        for i in range(CONFERENCES_PER_TOPIC):
            index = topic_index * CONFERENCES_PER_TOPIC + i
            conferences.append(seed_conference(topic, manager, users, index,
                                               start + timedelta(days=7 * index)))
    meetings = [seed_meeting(topics[i % len(topics)], manager, users, i, start + timedelta(days=200 + i))
                for i in range(MEETING_COUNT)]
    datasets = conferences + meetings
    series = [create_series([dataset['event'] for dataset in conferences[i:i + CONFERENCES_PER_TOPIC]],
                            event_title_pattern=f'{topic.title} Conference {{n}}')
              for i, topic in zip(range(0, len(conferences), CONFERENCES_PER_TOPIC), topics, strict=True)]
    series.append(create_series([dataset['event'] for dataset in meetings], show_links=False))

    equipment = get_equipment()
    locations, rooms = create_rooms(manager, users, equipment)
    reservations = create_reservations(rooms, users, 150)
    blockings = create_blockings(rooms, users, 40)

    token = PersonalToken(name=TOKEN_NAME, user=manager, scopes=TOKEN_SCOPES)
    plaintext = token.generate_token()
    db.session.add(token)
    db.session.commit()

    sample = conferences[0]
    manifest = {
        'base_url': config.BASE_URL,
        'default_timezone': config.DEFAULT_TIMEZONE,
        'token': plaintext,
        'manager_id': manager.id,
        'manager_username': MANAGER_USERNAME,
        'category_id': demo.id,
        'topic_category_id': topics[0].id,
        'event_id': sample['event'].id,
        'event_ids': [dataset['event'].id for dataset in datasets],
        'events': [describe(dataset) for dataset in datasets],
        'meeting_id': meetings[0]['event'].id,
        'track_id': sample['tracks'][0].id,
        'person_id': sample['persons'][0].id,
        'session_id': sample['sessions'][0].id,
        'contribution_id': sample['contributions'][0].id,
        'subcontribution_id': sample['subcontributions'][0].id,
        'timetable_entry_id': sample['breaks'][0].timetable_entry.id,
        'note_id': sample['notes'][0].id,
        'attachment_id': sample['attachments'][0].id,
        'link_attachment_id': sample['attachments'][1].id,
        'abstract_id': sample['abstracts'][0].id,
        'paper_contribution_id': sample['papers'][0].contribution.id,
        'regform_id': sample['regform'].id,
        'registration_id': sample['registrations'][0].id,
        'survey_id': sample['survey'].id,
        'agreement_id': sample['agreements'][0].id,
        'location_id': locations[0].id,
        'location_name': locations[0].name,
        'room_id': rooms[0].id,
        'reservation_id': reservations[0].id,
        'blocking_id': blockings[0].id,
        'role_id': sample['roles'][0].id,
        'group_id': groups[0].id,
        'reminder_id': sample['reminders'][0].id,
        'log_entry_id': sample['log_entries'][0].id,
        'payment_id': sample['payments'][0].id,
        'vc_room_id': sample['vc_rooms'][0].id,
        'offline_copy_id': sample['offline_copies'][0].id,
        'series_id': series[0].id,
        'page_id': sample['pages'][0].id,
        'image_id': sample['images'][0].id,
        'document_template_id': sample['receipt_templates'][0].id,
        'document_registration_id': sample['documents'][0].registration_id,
        'document_id': sample['documents'][0].file_id,
        'designer_template_id': sample['designer_templates'][0].id,
        'file_uuid': str(sample['uploads'][0].uuid),
        'counts': {
            'users': len(users) + 1,
            'categories': len(topics) + 1,
            'events': len(datasets),
            'persons': count_all(datasets, 'persons'),
            'tracks': count_all(datasets, 'tracks'),
            'sessions': count_all(datasets, 'sessions'),
            'session_blocks': count_all(datasets, 'blocks'),
            'contributions': count_all(datasets, 'contributions'),
            'subcontributions': count_all(datasets, 'subcontributions'),
            'breaks': count_all(datasets, 'breaks'),
            'timetable_entries': TimetableEntry.query.filter(
                TimetableEntry.event_id.in_([dataset['event'].id for dataset in datasets])).count(),
            'notes': count_all(datasets, 'notes'),
            'attachments': count_all(datasets, 'attachments'),
            'abstracts': count_all(datasets, 'abstracts'),
            'papers': count_all(datasets, 'papers'),
            'registration_forms': len(conferences),
            'registrations': count_all(datasets, 'registrations'),
            'surveys': len(conferences),
            'survey_questions': count_all(datasets, 'questions'),
            'survey_submissions': count_all(datasets, 'submissions'),
            'agreements': count_all(datasets, 'agreements'),
            'locations': len(locations),
            'rooms': len(rooms),
            'reservations': len(reservations),
            'blockings': len(blockings),
            'roles': count_all(datasets, 'roles'),
            'groups': len(groups),
            'reminders': count_all(datasets, 'reminders'),
            'log_entries': count_all(datasets, 'log_entries'),
            'payments': count_all(datasets, 'payments'),
            'vc_rooms': count_all(datasets, 'vc_rooms'),
            'offline_copies': count_all(datasets, 'offline_copies'),
            'series': len(series),
            'pages': count_all(datasets, 'pages'),
            'images': count_all(datasets, 'images'),
            'document_templates': len(category_templates) + count_all(datasets, 'receipt_templates'),
            'documents': count_all(datasets, 'documents'),
            'designer_templates': len(category_designer_templates) + count_all(datasets, 'designer_templates'),
            'files': count_all(datasets, 'uploads') + count_all(datasets, 'documents'),
        },
    }
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
    print('SEED_OK', json.dumps(manifest['counts'], sort_keys=True))


if __name__ == '__main__':
    main(sys.argv[1])
