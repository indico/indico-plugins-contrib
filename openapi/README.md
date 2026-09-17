# OpenAPI

Read-only REST API for Indico resources, described with an OpenAPI v3 document.

The API reuses Indico's own request handlers, marshmallow schemas and access
checks, so a request returns exactly the data the authenticated user can see in
the web interface. Objects a user cannot access are omitted from lists instead
of being reported as an error.

## Endpoints

| Path | Description |
| --- | --- |
| `/api/v1/events` | List events |
| `/api/v1/events/<event_id>` | Event details |
| `/api/v1/events/<event_id>/contributions` | List the contributions of an event |
| `/api/v1/events/<event_id>/contributions/<contrib_id>` | Contribution details |
| `/api/v1/events/<event_id>/contributions/<contrib_id>/subcontributions` | List the subcontributions of a contribution |
| `/api/v1/events/<event_id>/contributions/<contrib_id>/subcontributions/<subcontrib_id>` | Subcontribution details |
| `/api/v1/events/<event_id>/sessions` | List the sessions of an event |
| `/api/v1/events/<event_id>/sessions/<session_id>` | Session details |
| `/api/v1/events/<event_id>/timetable` | List the timetable entries of an event |
| `/api/v1/events/<event_id>/timetable/<entry_id>` | Timetable entry details |
| `/api/v1/events/<event_id>/tracks` | List the tracks of an event |
| `/api/v1/events/<event_id>/tracks/<track_id>` | Track details |
| `/api/v1/events/<event_id>/persons` | List the people taking part in an event |
| `/api/v1/events/<event_id>/persons/<person_id>` | Event person details |
| `/api/v1/events/<event_id>/registration-forms` | List the registration forms of an event |
| `/api/v1/events/<event_id>/registration-forms/<regform_id>` | Registration form details |
| `/api/v1/events/<event_id>/registrations` | List the registrations of an event |
| `/api/v1/events/<event_id>/registrations/<registration_id>` | Registration details |
| `/api/v1/events/<event_id>/document-templates` | List the document templates available to an event |
| `/api/v1/events/<event_id>/document-templates/<template_id>` | Document template details |
| `/api/v1/events/<event_id>/registrations/<registration_id>/documents` | List the documents generated for a registration |
| `/api/v1/events/<event_id>/registrations/<registration_id>/documents/<file_id>` | Document details |
| `/api/v1/events/<event_id>/designer-templates` | List the badge and poster templates available to an event |
| `/api/v1/events/<event_id>/designer-templates/<template_id>` | Badge or poster template details |
| `/api/v1/events/<event_id>/abstracts` | List the abstracts of an event |
| `/api/v1/events/<event_id>/abstracts/<abstract_id>` | Abstract details |
| `/api/v1/events/<event_id>/papers` | List the papers of an event |
| `/api/v1/events/<event_id>/contributions/<contrib_id>/paper` | Paper of a contribution |
| `/api/v1/events/<event_id>/surveys` | List the surveys of an event |
| `/api/v1/events/<event_id>/surveys/<survey_id>` | Survey details |
| `/api/v1/events/<event_id>/surveys/<survey_id>/submissions` | List the submitted answers of a survey |
| `/api/v1/events/<event_id>/agreements` | List the agreements an event asked for |
| `/api/v1/events/<event_id>/agreements/<agreement_id>` | Agreement details |
| `/api/v1/events/<event_id>/roles` | List the roles of an event |
| `/api/v1/events/<event_id>/roles/<role_id>` | Event role details |
| `/api/v1/events/<event_id>/reminders` | List the reminders of an event |
| `/api/v1/events/<event_id>/reminders/<reminder_id>` | Reminder details |
| `/api/v1/events/<event_id>/logs` | List the log entries of an event |
| `/api/v1/events/<event_id>/logs/<entry_id>` | Log entry details |
| `/api/v1/events/<event_id>/payments` | List the payments of an event |
| `/api/v1/events/<event_id>/payments/<payment_id>` | Payment details |
| `/api/v1/events/<event_id>/requests` | List the services an event asked for |
| `/api/v1/events/<event_id>/requests/<request_id>` | Service request details |
| `/api/v1/events/<event_id>/videoconference-rooms` | List the videoconferences of an event |
| `/api/v1/events/<event_id>/videoconference-rooms/<vc_room_id>` | Videoconference details |
| `/api/v1/events/<event_id>/offline-copies` | List the offline copies of an event |
| `/api/v1/events/<event_id>/offline-copies/<site_id>` | Offline copy details |
| `/api/v1/events/<event_id>/layout` | Layout settings of an event |
| `/api/v1/events/<event_id>/menu` | Menu of an event |
| `/api/v1/events/<event_id>/pages` | List the custom pages of an event |
| `/api/v1/events/<event_id>/pages/<page_id>` | Custom page details |
| `/api/v1/events/<event_id>/images` | List the images of an event |
| `/api/v1/events/<event_id>/images/<image_id>` | Image details |
| `/api/v1/events/<event_id>/features` | List the features available to an event |
| `/api/v1/events/<event_id>/notes` | List the notes of an event and of everything inside it |
| `/api/v1/events/<event_id>/notes/<note_id>` | Note details |
| `/api/v1/events/<event_id>/attachments` | List the attachments of an event |
| `/api/v1/events/<event_id>/attachments/<attachment_id>` | Attachment details |
| `/api/v1/events/<event_id>/sessions/<session_id>/attachments` | List the attachments of a session |
| `/api/v1/events/<event_id>/sessions/<session_id>/attachments/<attachment_id>` | Attachment details |
| `/api/v1/events/<event_id>/contributions/<contrib_id>/attachments` | List the attachments of a contribution |
| `/api/v1/events/<event_id>/contributions/<contrib_id>/attachments/<attachment_id>` | Attachment details |
| `/api/v1/events/<event_id>/contributions/<contrib_id>/subcontributions/<subcontrib_id>/attachments` | List the attachments of a subcontribution |
| `/api/v1/events/<event_id>/contributions/<contrib_id>/subcontributions/<subcontrib_id>/attachments/<attachment_id>` | Attachment details |
| `/api/v1/categories` | List categories |
| `/api/v1/categories/<category_id>` | Category details |
| `/api/v1/categories/<category_id>/attachments` | List the attachments of a category |
| `/api/v1/categories/<category_id>/attachments/<attachment_id>` | Attachment details |
| `/api/v1/locations` | List the locations rooms belong to |
| `/api/v1/locations/<location_id>` | Location details |
| `/api/v1/rooms` | List the rooms that can be booked |
| `/api/v1/rooms/<room_id>` | Room details |
| `/api/v1/reservations` | List room bookings |
| `/api/v1/reservations/<reservation_id>` | Room booking details |
| `/api/v1/blockings` | List the blockings that keep rooms from being booked |
| `/api/v1/blockings/<blocking_id>` | Blocking details |
| `/api/v1/users` | List users |
| `/api/v1/users/me` | Details of the authenticated user |
| `/api/v1/users/<user_id>` | User details |
| `/api/v1/files` | List the uploaded files |
| `/api/v1/files/<uuid>` | Uploaded file details |
| `/api/v1/groups` | List the local groups |
| `/api/v1/groups/<group_id>` | Local group details |
| `/api/v1/event-series` | List the event series the caller manages |
| `/api/v1/event-series/<series_id>` | Event series details |
| `/api/v1/openapi.json` | OpenAPI v3 document |
| `/api/v1/docs` | Swagger UI |

## Entities served

Every entity Indico stores as event or room booking content is served, plus the
settings saying how an event page is rendered. The cost
columns are the lines of plugin code and of plugin tests each one took, counted
with `wc -l` on the files it owns. Core schemas, request handlers and access
checks are reused, so they cost nothing here.

| Entity | Why it is served | Code | Tests |
| --- | --- | --- | --- |
| Events | Everything else hangs off an event, and its dates, description, location and category are what a caller asks for first. | 96 | 116 |
| Categories | The tree events are organised in, needed to walk from the instance root down to a single event. | 69 | 76 |
| Contributions | The talks of an event, with their speakers, times and room. The entity most often read from outside. | 155 | 101 |
| Subcontributions | The parts a contribution is split into, each with its own speakers and material. | 78 | 98 |
| Sessions | The blocks contributions are grouped in, with their own conveners, location and colours. | 93 | 104 |
| Timetable | The schedule itself, the only view that says when each contribution, session block and break happens. | 134 | 186 |
| Tracks | The programme an event is divided into. Abstracts and contributions point at it. | 74 | 100 |
| Event persons | Speakers, chairs, conveners and authors, with the affiliation each one was entered with. | 142 | 156 |
| Registration forms and registrations | What an event asks registrants for, whether it is open, who registered, in what state and for what price. | 245 | 243 |
| Abstracts | The submissions to a call for abstracts, with their state, tracks, authors and files. | 158 | 200 |
| Papers | The files submitted for a contribution, with every revision and the judgment of each one. | 157 | 193 |
| Surveys and submissions | The questionnaires an event runs, question by question, and the answers it collected. | 210 | 193 |
| Agreements | Who an event asked to sign something and who answered. | 112 | 105 |
| Event roles | The groups of users an event grants permissions to, and the people holding each one. | 99 | 104 |
| Reminders | The emails an event has scheduled for its participants, with their recipient filters and their message. | 140 | 101 |
| Event logs | Every management action an event recorded, with the values that changed, which is the only account of who did what. | 158 | 182 |
| Payments | What each registrant was charged, through which provider, and whether the payment went through. | 112 | 129 |
| Service requests | The services an event asked the instance to provide, in what state each request is, and who accepted or rejected it. | 131 | 157 |
| Videoconferences | The videoconference rooms attached to an event, a contribution or a session block, and whether the service still has each one. | 115 | 155 |
| Offline copies | The copies of an event built as static HTML, in what state each build is and where the ZIP file of a finished one is. | 95 | 87 |
| Event series | The groupings several events are presented as one through, with the title pattern and the links they share. | 78 | 109 |
| Event layout | The menu of an event page, the custom pages hanging off it, the images uploaded for it and the settings saying how the page is rendered. | 305 | 316 |
| Event features | Which optional parts of Indico an event has turned on, out of the ones its type allows. | 61 | 60 |
| Document templates and documents | The templates an event renders invoices and certificates from, the fields each one asks for, and the documents already generated for a registration. | 219 | 298 |
| Designer templates | The badge and poster templates an event draws tickets from, with the drawing itself and the images it places on it. | 128 | 143 |
| Notes | The minutes attached to an event, a session, a contribution or a subcontribution. | 76 | 89 |
| Attachments | The material and links attached to any of those, and the folders holding them. | 225 | 126 |
| Locations | The places rooms belong to. | 86 | 93 |
| Rooms | The rooms that can be booked, with their capacity, equipment and managers. | 109 | 99 |
| Reservations | The bookings of those rooms, with their occurrences. | 153 | 150 |
| Blockings | The periods a room cannot be booked, and who may still book it. | 99 | 95 |
| Users | The people the instance knows, plus the identity of the caller. | 89 | 101 |
| Files | The files uploaded to the instance, with the name, type and size of each one. | 77 | 65 |
| Groups | The groups of users the instance itself defines, and the members of each one. | 99 | 85 |
| Shared code (spec, Swagger UI, pagination, schema helpers) | Paid once: the OpenAPI document, the docs page, the list envelope and the field description machinery every resource above builds on. | 457 | 49 |
| **Total** | | **4834** | **4664** |

## Entities not covered

The cost column is what adding each one would take, estimated from the measured
bands above: 150 to 200 lines for an entity with one core schema and plain
access rules, 300 to 350 when the payload nests other objects or hides fields
per role, 450 to 500 when it also needs several endpoints of its own.

| Entity | Why | Estimated cost |
| --- | --- | --- |
| Paper and abstract reviews, ratings and comments | Reviewing is written under the assumption that only the people in the process read it, and each role sees a different part of the same review. Exposing it through an API means reimplementing those rules rather than reusing them. | 600 to 700 |
| Editing (`events/editing`) | The editing workflow is reviewing material under another name: revisions, review comments and file type settings. It also already has its own REST API, used by its React frontend. | 500 to 600 |
| Instance administration | Settings, announcements, news, legal texts, authentication, OAuth applications, IP networks and the search service are either instance configuration or a view over the entities above. | 600 or more |

### Where Indico serves them today

None of the three is invisible over GET. Every one of them can be read
without a POST, either as JSON or as a rendered page, so the question is never
whether the data is reachable but in what shape and to whom.

| Entity | Read over GET | Shape |
| --- | --- | --- |
| Paper and abstract reviews, ratings and comments | `/event/<event_id>/manage/abstracts/abstracts.json`, `/event/<event_id>/manage/papers/assignment-list/export-json`, and the abstract and paper pages | JSON, but only as a whole-event dump sent as a file attachment and only to managers. The per-role view of a single review is HTML. |
| Editing | `/event/<event_id>/editing/api/...` and the editable timeline of each contribution | JSON. It already is a REST API, written for its own React frontend. |
| Instance administration | The pages under `/admin/` | HTML forms, except `/admin/logs/api/logs` and `/admin/version-check`. |

Instance settings are the one entity that can only be read as HTML today: they are a
management surface rendered from a template, never asked for by a machine. The ones
that already answer JSON do it for one caller each,
either a React page of the interface or a manager downloading a file, so their
payloads are shaped after that caller instead of a public contract, and none of
them is versioned or documented.

Two entities are served with a field left out on purpose: an agreement never
exposes its signing token, since holding it is enough to answer on behalf of the
person who was asked to sign, and a survey submission never exposes its
respondent, anonymous or not.

Files are the one entity whose list is restricted to administrators. A file
carries no access list: Indico protects it by keeping its identifier secret and
hands that identifier out through the receipt, editing revision or data export
holding the file, so listing the identifiers would give away the permission
along with them. Reading one file by its identifier is open to any
authenticated caller, which is the rule Indico itself applies.

Groups are served in both shapes but only to administrators, since the
administration area is the only interface showing a group together with the
email address of every member. Only the groups Indico defines itself are
returned: a group coming from an external identity provider is known by its
name alone, and its members are asked for on every check instead of being
stored. The endpoints also honour the setting that hides local groups, so they
answer 403 while it is off, exactly as the administration pages do.

The log of an event is served with the filters the log interface uses: the area
of the event an entry belongs to, free text over the same columns the interface
searches, and the registration an entry is about. Without them a caller would
have to read the whole audit trail of an event to find one entry. A caller who
only manages the registrations of the event has to pass the registration filter,
and reaches a single entry only when that entry is about a registration, which
is the rule the log interface applies as well. The log of a category, of a user
and of the instance is not served: those belong to instance administration.

A payment is served to the managers of the registrations of an event, the only
audience the interface shows one to: the transaction appears on the management
page of a registration and nowhere else. Registrants see whether their own
registration is paid, not the payment behind it, so that is all they get here as
well, on the registration itself. The answer of the payment provider is left out
of the payload: its shape is defined by each payment plugin rather than by
Indico, so there is no contract to document, and it carries whatever the provider
chose to send back about the payer. The list takes the registration and the state
as filters, so a caller can ask for the payments of one registrant, or for the
ones that did not go through, without reading every payment of the event.

A service request is served to the managers of the event and to the people
running the service that was asked for, which is the audience the request pages
serve as well: managing a request type is enough to reach the requests of that
type in any event, and of no other type. The list is filtered to the types whose
definition is loaded, so the rows an uninstalled plugin left behind stay
invisible, as they are in the interface. What it does serve beyond the interface
is history: the management page shows only the latest request of each type, while
the list answers with every request an event ever sent, which is what makes the
type and the state worth having as filters. The values the manager filled in are
served as they were stored, since the fields are defined by the plugin providing
the request type and Indico has no say in them.

A videoconference is served to whoever can see the event, which is the audience
of the page listing them, and its managers also get the two kinds the page hides:
the rooms marked as hidden and the ones the service no longer has, both of which
the management page keeps showing. A room whose plugin is not installed is served
to nobody, as it is dropped from both pages. What the plugin stored about the room
is left out of the payload, the same way the provider answer of a payment is: its
shape belongs to each plugin, and it holds the credentials to join, which the
interface only ever renders into a button. What is left is the part Indico owns,
which is the name of the room, the service it lives in and what it is attached to.

The layout of an event is served to whoever can see the event, since it
describes the page they are already looking at: the menu, the custom pages
hanging off it, and the settings the page is rendered with, down to the URLs of
the stylesheet, the logo and the scripts. The announcement is served only while
the event publishes it, so a draft stays hidden, and the three settings saying
where the announcement, the stylesheet and the menu come from are left out: they
say how the page was put together, not what it shows. A menu entry is listed
only when the caller can see it, children included, which is the check the page
itself makes before rendering one, and a custom page only when the entry
pointing at it grants access.

Images and features are served to the managers of the event alone, as the image
manager and the features page are the only interfaces listing them. The feature
list leaves out what the type of the event does not allow, the same rows that
page hides, so it answers with the features the event can actually turn on, and
the images need their own feature to be on, as the image manager does.

Document templates are served to whoever manages the registrations of an event,
the audience of the interface listing them, and the scope is the one that
interface offers: the templates of the event plus the ones it inherits from its
categories, with the defaults the event set already applied. The HTML body, the
stylesheet and the raw metadata of a template are left out, since core only
serves them to the editor writing them and they say how a document is drawn
rather than what it asks for. The documents themselves hang off the registration
they were generated for, so a registrant reaches their own without managing
anything, and gets only the published ones, which is the rule the registration
page applies; a manager also gets the unpublished ones, and each payload carries
the download URL of the caller's own interface. The values a document was
rendered with are left out: they are a snapshot of the registration taken when it
was generated, and the registration has endpoints of its own. The document
endpoints need the registration feature to be on, as the page serving them does,
while the template endpoints need no feature at all, since core gates the
receipts interface on nothing but the permission.

Designer templates are served to the managers of the event alone, as the designer
is the only interface listing them, over the same scope of the event plus its
categories, filtered through the signal the designer page gives plugins to hide a
template. What the editor reads is what is served: the title, the drawing, the
background and the images its items reference, with the URLs left relative as
core writes them. Whether a template is a ticket, whether it can be cloned and
which registration form it is linked to are left out, as they are settings only
the management page acts on.

Responses reuse Indico's own marshmallow schemas wherever core has one that
describes the object. Several objects are only ever rendered from a template, or
sent as a payload shaped for one React page, or described by a schema that only
loads a submitted form: attachments and their folders, categories, notes,
registration forms, registrations, session types, subcontributions, timetable
entries, breaks, surveys, survey questions, agreements, generated documents and
designer templates. Those are declared
here as automatic schemas over the model, so their field names and types still
come from Indico rather than from a hand-written mapping.

## Parity with the endpoints Indico already serves

Every entity has a test asserting that this API and the endpoint Indico already
serves return the same values, field by field. The payloads have a different
shape, so the tests compare the underlying values rather than the raw JSON.

The tests call the other endpoint live in the same test run, so they fail as soon
as Indico changes what it answers. That is deliberate: following Indico's own
output is the point of this API, and a test that keeps passing through such a
change would be hiding it.

Twelve entities are compared against the legacy export API:

| Entity | Legacy endpoint |
| --- | --- |
| Events | `/export/event/<event_id>.json` |
| Categories | `/export/categ/<category_id>.json` |
| Contributions | `/export/event/<event_id>.json?detail=contributions` |
| Subcontributions | `/export/event/<event_id>.json?detail=subcontributions` |
| Sessions | `/export/event/<event_id>/session/<session_id>.json` |
| Timetable | `/export/timetable/<event_id>.json` |
| Persons | `/export/event/<event_id>.json`, field `chairs` |
| Notes | `/export/note/<event_id>[/session/<id>\|/contribution/<id>[/<subid>]].json` |
| Attachments | `/export/attachments/<event_id>[/session/<id>\|/contribution/<id>[/<subid>]].json` |
| Users | `/export/user/<user_id>.json` |
| Rooms | `/export/room/<location>/<room_ids>.json` |
| Reservations | `/export/reservation/<location>.json` |

The rest have no legacy endpoint, so they are compared against the JSON the
current interface itself calls:

| Entity | Current endpoint |
| --- | --- |
| Tracks and track groups | `/event/<event_id>/program.json` |
| Registration forms and registrations | `/api/checkin/event/<event_id>/forms/[<reg_form_id>/registrations/[<registration_id>]]` |
| Abstracts | `/event/<event_id>/manage/abstracts/abstracts.json` |
| Papers | `/event/<event_id>/manage/papers/assignment-list/export-json` |
| Surveys | `/event/<event_id>/manage/surveys/<survey_id>/questionnaire/survey.json` |
| Locations | `/rooms/api/locations` |
| Blockings | `/rooms/api/blockings/` |
| Files | `/files/<uuid>` |
| Groups | `/groups/api/search` |
| Event roles | `/event/<event_id>/manage/roles/api/roles/` and `/event/<event_id>/manage/api/event-roles` |
| Event logs | `/event/<event_id>/manage/logs/api/logs` |
| Event series | `/event-series/<series_id>` |
| Document templates | `/event/<event_id>/manage/receipts/templates` |
| Designer templates | `/event/<event_id>/manage/designer/<template_id>/data` |

Event roles are the one entity whose comparison needs two endpoints at once:
the management API serves the members of a role but not its id, and the
protection API the id but not the members, so the test compares
against both payloads joined on the code each of them orders by.

The member list of a group is left out of its comparison, for lack of anything
to compare it against: the group search answers with the name and the identifier
of a group and never with its members, and the member list of the administration
area is rendered as HTML.

One value is left out of those comparisons because the two APIs mean different
things by it: the check-in API counts every registration a form holds, while
`registration_count` here counts the active ones, which is the number the
participant list publishes. `full_name` is compared, but the two only agree while
the event keeps the default name format, since the check-in API renders a
registrant the way the event configured it and this API always answers
`Firstname Lastname`.

Survey submissions, agreements, reminders, payments, service requests,
videoconferences, offline copies, event layout, event features and the documents
generated for a registration are the entities served without a parity test. The interface only exports submissions as CSV or Excel, behind a
POST, so the survey test compares the questionnaire instead. For agreements, the
legacy endpoint answers with the people an agreement definition asks to sign, and
those definitions come from plugins, so there is nobody to list unless a plugin
providing one is installed. This API returns the agreements the event actually
stored, which is what the management interface lists. Reminders are only ever
rendered as a management page, so there is no payload to compare against, and a
payment is rendered into the registration page by the very plugin that handled
it, so there is none either. Service requests are only ever rendered as a
management page too, one form per request type, each of them provided by a plugin,
and a videoconference is rendered by the plugin holding it, into the event page
and into the management table. An offline copy is listed on a management page as
well, with nothing behind its link but the ZIP file itself. The layout and the
features of an event are only ever rendered as management pages as well, and the
only machine-readable part of either is a toggle answering to PUT and DELETE. A
generated document is rendered into the registration page and into the management
list as a download link, with nothing behind it but the PDF itself. The list of
designer templates has no payload to compare against either, since the designer
renders its own page; the comparison is made on a single template instead, against
the endpoint its editor reads.

### Checking a running instance

The tests above run on rows built by fixtures. `scripts/seed_demo_data.py` fills
a running instance with rows for every entity served, and
`scripts/live_parity.py` repeats the comparisons over HTTP against it, importing
the mappings from the test modules so the two cannot drift apart. The entities
with no payload to compare against are checked by count, and the layout and the
features by value, against what the seed wrote to its manifest.
`scripts/purge_demo_data.py` removes the dataset again. Service requests are the
one entity the seed leaves out: a request needs a plugin that defines its type,
and none of the plugins shipped with Indico does.

```sh
SEED_PASSWORD=... indico shell -r <<< "import runpy, sys; sys.argv = ['seed', '/tmp/demo.json']; runpy.run_path('scripts/seed_demo_data.py', run_name='__main__')"
python scripts/live_parity.py /tmp/demo.json
indico shell -r <<< "import runpy; runpy.run_path('scripts/purge_demo_data.py', run_name='__main__')"
```

## Pagination

List endpoints take `limit` and `offset` and answer with an envelope:

```json
{
    "results": [],
    "count": 0,
    "next_offset": null
}
```

`next_offset` is the value to send as `offset` to get the next page, or `null`
on the last one. It counts rows scanned rather than results returned, because
rows the user cannot access are skipped without being listed.

## Authentication

Swagger UI authenticates with your Indico session cookie, so nothing needs to
be filled in there. From outside, create a personal token under your Indico
profile with the `read:everything` scope and send it as a bearer token:

```sh
curl -H 'Authorization: Bearer indp_...' https://indico.example.com/api/v1/events/1
```

Indico rejects a request that carries a token and a session cookie at the same
time, so never send both.
