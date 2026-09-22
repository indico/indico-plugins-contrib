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
from indico.modules.categories.models.event_move_request import EventMoveRequest, MoveRequestState
from indico.modules.categories.models.roles import CategoryRole
from indico.modules.designer import TemplateType
from indico.modules.designer.models.images import DesignerImageFile
from indico.modules.designer.models.templates import DesignerTemplate
from indico.modules.events import Event
from indico.modules.events.abstracts.models.abstracts import Abstract, AbstractState
from indico.modules.events.abstracts.models.email_logs import AbstractEmailLogEntry
from indico.modules.events.abstracts.models.email_templates import AbstractEmailTemplate
from indico.modules.events.abstracts.models.files import AbstractFile
from indico.modules.events.abstracts.models.persons import AbstractPersonLink
from indico.modules.events.agreements.models.agreements import Agreement, AgreementState
from indico.modules.events.contributions.models.contributions import Contribution
from indico.modules.events.contributions.models.fields import (
    ContributionField,
    ContributionFieldValue,
    ContributionFieldVisibility,
)
from indico.modules.events.contributions.models.persons import (
    AuthorType,
    ContributionPersonLink,
    SubContributionPersonLink,
)
from indico.modules.events.contributions.models.references import ContributionReference, SubContributionReference
from indico.modules.events.contributions.models.subcontributions import SubContribution
from indico.modules.events.contributions.models.types import ContributionType
from indico.modules.events.features.util import get_enabled_features, set_feature_enabled
from indico.modules.events.layout import layout_settings
from indico.modules.events.layout.models.images import ImageFile
from indico.modules.events.layout.models.menu import EventPage, MenuEntry, MenuEntryType
from indico.modules.events.layout.util import menu_entries_for_event
from indico.modules.events.models.events import EventType
from indico.modules.events.models.labels import EventLabel
from indico.modules.events.models.persons import EventPerson, EventPersonLink
from indico.modules.events.models.references import EventReference, ReferenceType
from indico.modules.events.models.roles import EventRole
from indico.modules.events.models.series import EventSeries
from indico.modules.events.notes.models.notes import EventNote
from indico.modules.events.papers.file_types import PaperFileType
from indico.modules.events.papers.models.files import PaperFile
from indico.modules.events.papers.models.papers import Paper
from indico.modules.events.papers.models.revisions import PaperRevision, PaperRevisionState
from indico.modules.events.papers.models.templates import PaperTemplate
from indico.modules.events.payment.models.transactions import PaymentTransaction, TransactionStatus
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.invitations import InvitationState, RegistrationInvitation
from indico.modules.events.registration.models.registrations import PublishRegistrationsMode
from indico.modules.events.registration.models.tags import RegistrationTag
from indico.modules.events.registration.util import create_personal_data_fields, create_registration
from indico.modules.events.reminders.models.reminders import EventReminder, ReminderType
from indico.modules.events.sessions.models.blocks import SessionBlock
from indico.modules.events.sessions.models.persons import SessionBlockPersonLink
from indico.modules.events.sessions.models.sessions import Session
from indico.modules.events.sessions.models.types import SessionType
from indico.modules.events.settings import event_contact_settings
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
from indico.modules.rb.models.map_areas import MapArea
from indico.modules.rb.models.photos import Photo
from indico.modules.rb.models.reservation_edit_logs import ReservationEditLog
from indico.modules.rb.models.reservations import RepeatFrequency, Reservation
from indico.modules.rb.models.room_attributes import RoomAttribute
from indico.modules.rb.models.room_bookable_hours import BookableHours
from indico.modules.rb.models.room_nonbookable_periods import NonBookablePeriod
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


def jpeg_image(color, size=(320, 240)):
    buffer = BytesIO()
    Image.new('RGB', size, f'#{color}').save(buffer, 'JPEG')
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


def get_reference_types():
    types = {}
    for name, scheme, template in (('DOI', 'doi', 'https://doi.org/{value}'), ('Report number', None, None)):
        # the name is unique regardless of case
        reference_type = ReferenceType.query.filter(db.func.lower(ReferenceType.name) == name.lower()).first()
        if reference_type is None:
            reference_type = ReferenceType(name=name, scheme=scheme, url_template=template)
            db.session.add(reference_type)
        types[name] = reference_type
    db.session.flush()
    return types


def get_event_labels():
    labels = []
    for title, color, not_happening in (('Cancelled', 'red', True), ('Hybrid', 'blue', False)):
        # the title is unique regardless of case
        label = EventLabel.query.filter(db.func.lower(EventLabel.title) == title.lower()).first()
        if label is None:
            label = EventLabel(title=title, color=color, is_event_not_happening=not_happening)
            db.session.add(label)
        labels.append(label)
    db.session.flush()
    return labels


def create_references(event, contributions, subcontributions, types, index):
    doi, report = types['DOI'], types['Report number']
    # a reference type holds the references made with it, so a new reference is
    # already pending when it is built and has to carry its owner from the start
    references = [EventReference(event=event, reference_type=doi, value=f'10.5170/OPENAPI-2026-{index:03d}'),
                  EventReference(event=event, reference_type=report, value=f'OPENAPI-EVENT-{index:03d}')]
    references += [ContributionReference(contribution=contribution, reference_type=doi,
                                         value=f'10.5170/OPENAPI-2026-{index:03d}.{i + 1}')
                   for i, contribution in enumerate(contributions[:4])]
    references += [SubContributionReference(subcontribution=subcontribution, reference_type=report,
                                            value=f'OPENAPI-TALK-{index:03d}-{i + 1}')
                   for i, subcontribution in enumerate(subcontributions[:2])]
    db.session.flush()
    return references


def set_contact(event, index):
    event_contact_settings.set_multi(event, {
        'title': 'Conference secretariat',
        'emails': [f'openapi.contact{index}@example.test'],
        'phones': [f'+41 22 767 {index:04d}'],
    })


def create_contribution_types(event, contributions):
    types = []
    for name, description, private in (('Oral', 'A talk given in a session.', False),
                                       ('Poster', 'Shown in the poster session.', False),
                                       ('Keynote', 'An invited talk.', True)):
        contribution_type = ContributionType(event=event, name=name, description=description, is_private=private)
        db.session.add(contribution_type)
        types.append(contribution_type)
    db.session.flush()
    for i, contribution in enumerate(contributions):
        contribution.type = pick(types, i)
    # the type is written to the contribution row, which subcontributions draw
    # their friendly id from through a separate connection
    db.session.commit()
    return types


def create_contribution_fields(event, contributions):
    summary = ContributionField(event=event, title='Extended summary', description='A longer abstract.',
                                field_type='text', field_data={'multiline': True}, position=1, is_required=False)
    options = [{'id': str(uuid4()), 'option': label, 'is_enabled': True}
               for label in ('Beginner', 'Advanced')]
    level = ContributionField(event=event, title='Audience level', description='Who the talk is aimed at.',
                              field_type='single_choice', position=2, is_required=False,
                              visibility=ContributionFieldVisibility.managers_only,
                              field_data={'options': options, 'display': 'select'})
    db.session.add_all([summary, level])
    db.session.flush()
    for i, contribution in enumerate(contributions[:6]):
        db.session.add(ContributionFieldValue(contribution=contribution, contribution_field=summary,
                                              data=f'Extended summary of {contribution.title.lower()}.'))
        db.session.add(ContributionFieldValue(contribution=contribution, contribution_field=level,
                                              data=pick(options, i)['id']))
    db.session.flush()
    return [summary, level]


def create_session_types(event, sessions):
    types = [SessionType(event=event, name='Plenary', code='PL', is_poster=False),
             SessionType(event=event, name='Poster session', code='PO', is_poster=True)]
    db.session.add_all(types)
    db.session.flush()
    for i, sess in enumerate(sessions):
        sess.type = pick(types, i)
    db.session.flush()
    return types


def create_paper_setup(event):
    template = PaperTemplate(event=event, name='Paper template', description='The skeleton every paper starts from.',
                             filename='template.tex', content_type='text/x-tex')
    template.save(b'\\documentclass{article}\n')
    db.session.add(template)
    file_types = [PaperFileType(event=event, name='Paper', extensions=['pdf'], required=True, publishable=True,
                                filename_template='paper-{code}'),
                  PaperFileType(event=event, name='Sources', extensions=['tex', 'zip'], required=False,
                                publishable=False)]
    db.session.add_all(file_types)
    db.session.flush()
    return template, file_types


def create_abstract_emails(event, abstracts, manager):
    templates = [
        AbstractEmailTemplate(event=event, title='Acceptance', position=1, stop_on_match=True,
                              subject='Your abstract was accepted',
                              body='Dear {abstract_submitter},\n\n{abstract_title} was accepted.',
                              reply_to_address='', extra_cc_emails=[], include_submitter=True,
                              include_authors=True, include_coauthors=False,
                              rules=[{'state': [AbstractState.accepted.value]}]),
        AbstractEmailTemplate(event=event, title='Rejection', position=2, stop_on_match=True,
                              subject='Your abstract was rejected',
                              body='Dear {abstract_submitter},\n\n{abstract_title} was rejected.',
                              reply_to_address='', extra_cc_emails=[], include_submitter=True,
                              include_authors=False, include_coauthors=False,
                              rules=[{'state': [AbstractState.rejected.value]}]),
    ]
    db.session.add_all(templates)
    db.session.flush()
    by_state = {AbstractState.accepted: templates[0], AbstractState.rejected: templates[1]}
    entries = []
    for abstract in abstracts:
        template = by_state.get(abstract.state)
        if template is None:
            continue
        entry = AbstractEmailLogEntry(abstract=abstract, email_template=template, user=manager,
                                      sent_dt=abstract.judgment_dt, recipients=[abstract.submitter.email],
                                      subject=template.subject, body=template.body,
                                      data={'template_name': template.title})
        db.session.add(entry)
        entries.append(entry)
    db.session.flush()
    return templates, entries


def create_invitations(regform, registrations, index, count=4):
    invitations = []
    for i in range(count):
        state = pick((InvitationState.pending, InvitationState.accepted, InvitationState.declined), i)
        invitation = RegistrationInvitation(registration_form=regform,
                                            first_name=pick(FIRST_NAMES, index + i),
                                            last_name=pick(LAST_NAMES, index + i),
                                            email=f'openapi.invitee{index}.{i}@example.test',
                                            affiliation=pick(AFFILIATIONS, i), state=state,
                                            skip_moderation=(i % 2 == 0), lock_email=(i % 3 == 0))
        if state == InvitationState.accepted:
            invitation.registration = pick(registrations, i)
        invitations.append(invitation)
    db.session.flush()
    return invitations


def create_category_roles(category, users):
    roles = []
    for i, (name, code) in enumerate((('Category managers', 'CATMAN'), ('Event creators', 'CREATORS'))):
        role = CategoryRole(category=category, name=name, code=code, color=pick(COLORS, i),
                            members={pick(users, i), pick(users, i + 1), pick(users, i + 2)})
        db.session.add(role)
        roles.append(role)
    db.session.flush()
    return roles


def create_move_requests(category, events, users, manager):
    requests = []
    for i, event in enumerate(events):
        state = pick((MoveRequestState.pending, MoveRequestState.accepted, MoveRequestState.rejected), i)
        request = EventMoveRequest(event=event, category=category, requestor=pick(users, i), state=state,
                                   requestor_comment='This event belongs in the demo category.',
                                   requested_dt=now_utc() - timedelta(days=30 - i))
        if state != MoveRequestState.pending:
            request.moderator = manager
            request.moderator_comment = 'Answered for the demo dataset.'
        db.session.add(request)
        requests.append(request)
    db.session.flush()
    return requests


def get_map_areas():
    corners = ((46.2400, 6.0400, 46.2250, 6.0650), (46.2600, 6.0250, 46.2450, 6.0500))
    # the instance allows a single default area, and it may already have one
    is_default = MapArea.query.filter_by(is_default=True).first() is None
    areas = []
    for name, corner in zip(('Meyrin site', 'Prevessin site'), corners, strict=True):
        area = MapArea.query.filter_by(name=name).first()
        if area is None:
            top_left_latitude, top_left_longitude, bottom_right_latitude, bottom_right_longitude = corner
            area = MapArea(name=name, is_default=is_default, top_left_latitude=top_left_latitude,
                           top_left_longitude=top_left_longitude, bottom_right_latitude=bottom_right_latitude,
                           bottom_right_longitude=bottom_right_longitude)
            db.session.add(area)
        is_default = False
        areas.append(area)
    db.session.flush()
    return areas


def get_room_attributes(rooms):
    attributes = []
    for name, title, hidden in (('demo-manager-group', 'Manager group', False),
                                ('demo-door-code', 'Door code', True)):
        attribute = RoomAttribute.query.filter_by(name=name).first()
        if attribute is None:
            attribute = RoomAttribute(name=name, title=title, is_hidden=hidden)
            db.session.add(attribute)
        attributes.append(attribute)
    db.session.flush()
    for i, room in enumerate(rooms):
        room.set_attribute_value('demo-manager-group', pick(GROUP_NAMES, i))
        if i % 3 == 0:
            room.set_attribute_value('demo-door-code', f'{1000 + i}')
    db.session.flush()
    return attributes


def create_room_availability(rooms):
    hours, periods = [], []
    shutdown = datetime.combine(date.today() + timedelta(days=90), time(0, 0))
    for i, room in enumerate(rooms):
        if i % 2 == 0:
            hours.append(BookableHours(room=room, start_time=time(8, 0), end_time=time(18, 0)))
        if i % 3 == 0:
            hours.append(BookableHours(room=room, start_time=time(9, 0), end_time=time(12, 0), weekday='sat'))
        if i % 4 == 0:
            periods.append(NonBookablePeriod(room=room, start_dt=shutdown, end_dt=shutdown + timedelta(days=7)))
    db.session.add_all(hours + periods)
    db.session.flush()
    return hours, periods


def create_room_photos(rooms, count):
    photos = []
    for i, room in enumerate(rooms[:count]):
        room.photo = Photo(data=jpeg_image(pick(COLORS, i)))
        photos.append(room.photo)
    db.session.flush()
    return photos


def create_reservation_logs(reservations, manager):
    entries = []
    for i, reservation in enumerate(reservations):
        entries.append(ReservationEditLog(reservation=reservation, user_name=reservation.created_by_user.full_name,
                                          info=['Booking created'], timestamp=reservation.created_dt))
        if i % 5 == 0:
            entries.append(ReservationEditLog(reservation=reservation, user_name=manager.full_name,
                                              info=['Booking accepted', 'Notification sent'],
                                              timestamp=reservation.created_dt + timedelta(hours=1)))
    db.session.add_all(entries)
    db.session.flush()
    return entries


def link_reservations(reservations, events):
    """Book a room for an event, which is how a booking gets attached to one.

    Indico allows a single booking occurrence per object, so one event takes one
    reservation.
    """
    links = []
    for reservation, event in zip(reservations, events, strict=False):
        occurrence = reservation.occurrences[0]
        occurrence.linked_object = event
        links.append(occurrence.link)
    db.session.flush()
    return links


def seed_conference(category, manager, users, index, start, reference_types, labels):
    title = f'{category.title} Conference {index % CONFERENCES_PER_TOPIC + 1}'
    event = create_event(category, manager, title, start, EventType.conference, days=2)
    for feature in ('abstracts', 'papers', 'registration', 'payment', 'surveys'):
        set_feature_enabled(event, feature, True)

    persons = create_persons(event, users, 12, index * 5)
    for i in range(3):
        event.person_links.append(EventPersonLink(person=persons[i]))
    set_contact(event, index)
    if index % 5 == 0:
        event.label = pick(labels, index)
        event.label_message = 'Kept in the demo dataset to show a labelled event.'
        # the label is written to the event row, which has to be committed again
        # before anything inside the event draws a friendly id from it
        db.session.commit()
    group, tracks = create_tracks(event, index)
    sessions, blocks = create_sessions(event, persons, 3, 2, start)
    session_types = create_session_types(event, sessions)
    contributions = create_contributions(event, persons, tracks, blocks, 15, index)
    contribution_types = create_contribution_types(event, contributions)
    contribution_fields = create_contribution_fields(event, contributions)
    subcontributions = create_subcontributions(contributions, persons)
    breaks = create_breaks(event, blocks, 3, start)
    references = create_references(event, contributions, subcontributions, reference_types, index)

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
    abstract_email_templates, abstract_emails = create_abstract_emails(event, abstracts, manager)
    papers = create_papers(contributions[:8], users, index)
    paper_template, paper_file_types = create_paper_setup(event)
    regform, registrations = create_regform(event, users, 15, index * 3)
    invitations = create_invitations(regform, registrations, index)
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
        'designer_templates': [designer_template], 'uploads': uploads, 'references': references,
        'contribution_types': contribution_types, 'contribution_fields': contribution_fields,
        'session_types': session_types, 'paper_templates': [paper_template], 'paper_file_types': paper_file_types,
        'abstract_email_templates': abstract_email_templates, 'abstract_emails': abstract_emails,
        'invitations': invitations,
    }


def seed_meeting(category, manager, users, index, start, reference_types):
    title = f'Demo meeting {index + 1}'
    event = create_event(category, manager, title, start, EventType.meeting, days=0)
    persons = create_persons(event, users, 6, index * 4)
    set_contact(event, index)
    sessions, blocks = create_sessions(event, persons, 1, 1, start)
    contributions = create_contributions(event, persons, [], blocks, 8, index)
    subcontributions = create_subcontributions(contributions, persons)
    breaks = create_breaks(event, blocks, 2, start)
    references = create_references(event, contributions, subcontributions, reference_types, 100 + index)
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
        'references': references,
    }


def describe(dataset):
    notes = dataset['notes']
    folders = [attachment.folder for attachment in dataset['attachments']]
    documents = {}
    for document in dataset.get('documents', ()):
        documents[document.registration_id] = documents.get(document.registration_id, 0) + 1
    emails = {}
    for entry in dataset.get('abstract_emails', ()):
        emails[entry.abstract_id] = emails.get(entry.abstract_id, 0) + 1
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
        'abstract_emails': emails,
        'contribution_types': len(dataset.get('contribution_types', ())),
        'contribution_fields': len(dataset.get('contribution_fields', ())),
        'session_types': len(dataset.get('session_types', ())),
        'paper_templates': len(dataset.get('paper_templates', ())),
        'paper_file_types': len(dataset.get('paper_file_types', ())),
        'abstract_email_templates': len(dataset.get('abstract_email_templates', ())),
        'invitations': len(dataset.get('invitations', ())),
        'regform_id': dataset['regform'].id if 'regform' in dataset else None,
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

    reference_types = get_reference_types()
    labels = get_event_labels()
    category_roles = create_category_roles(demo, users)

    start = midnight(date.today() + timedelta(days=7))
    conferences = []
    for topic_index, topic in enumerate(topics):
        for i in range(CONFERENCES_PER_TOPIC):
            index = topic_index * CONFERENCES_PER_TOPIC + i
            conferences.append(seed_conference(topic, manager, users, index,
                                               start + timedelta(days=7 * index), reference_types, labels))
    meetings = [seed_meeting(topics[i % len(topics)], manager, users, i, start + timedelta(days=200 + i),
                             reference_types)
                for i in range(MEETING_COUNT)]
    move_requests = create_move_requests(demo, [dataset['event'] for dataset in meetings[:3]], users, manager)
    datasets = conferences + meetings
    series = [create_series([dataset['event'] for dataset in conferences[i:i + CONFERENCES_PER_TOPIC]],
                            event_title_pattern=f'{topic.title} Conference {{n}}')
              for i, topic in zip(range(0, len(conferences), CONFERENCES_PER_TOPIC), topics, strict=True)]
    series.append(create_series([dataset['event'] for dataset in meetings], show_links=False))

    equipment = get_equipment()
    locations, rooms = create_rooms(manager, users, equipment)
    map_areas = get_map_areas()
    room_attributes = get_room_attributes(rooms)
    photos = create_room_photos(rooms, 6)
    reservations = create_reservations(rooms, users, 150)
    # a booking is checked against the availability of its room, so the demo
    # bookings are made before the rooms are restricted
    bookable_hours, nonbookable_periods = create_room_availability(rooms)
    reservation_logs = create_reservation_logs(reservations, manager)
    reservation_links = link_reservations(reservations, [dataset['event'] for dataset in conferences])
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
        'invitation_id': sample['invitations'][0].id,
        'contribution_type_id': sample['contribution_types'][0].id,
        'contribution_field_id': sample['contribution_fields'][0].id,
        'session_type_id': sample['session_types'][0].id,
        'paper_template_id': sample['paper_templates'][0].id,
        'paper_file_type_id': sample['paper_file_types'][0].id,
        'abstract_email_template_id': sample['abstract_email_templates'][0].id,
        'emailed_abstract_id': sample['abstract_emails'][0].abstract_id,
        'category_role_id': category_roles[0].id,
        'move_request_id': move_requests[0].id,
        'survey_id': sample['survey'].id,
        'agreement_id': sample['agreements'][0].id,
        'location_id': locations[0].id,
        'location_name': locations[0].name,
        'room_id': rooms[0].id,
        'attributed_room_id': rooms[0].id,
        'map_area_id': map_areas[0].id,
        'reservation_id': reservations[0].id,
        'linked_reservation_id': reservation_links[0].reservation_occurrence.reservation_id,
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
            'references': count_all(datasets, 'references'),
            'contribution_types': count_all(datasets, 'contribution_types'),
            'contribution_fields': count_all(datasets, 'contribution_fields'),
            'session_types': count_all(datasets, 'session_types'),
            'paper_templates': count_all(datasets, 'paper_templates'),
            'paper_file_types': count_all(datasets, 'paper_file_types'),
            'abstract_email_templates': count_all(datasets, 'abstract_email_templates'),
            'abstract_emails': count_all(datasets, 'abstract_emails'),
            'invitations': count_all(datasets, 'invitations'),
            'category_roles': len(category_roles),
            'move_requests': len(move_requests),
            'locations': len(locations),
            'rooms': len(rooms),
            'map_areas': len(map_areas),
            'room_attributes': len(room_attributes),
            'bookable_hours': len(bookable_hours),
            'nonbookable_periods': len(nonbookable_periods),
            'room_photos': len(photos),
            'reservations': len(reservations),
            'reservation_edit_logs': len(reservation_logs),
            'reservation_links': len(reservation_links),
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
