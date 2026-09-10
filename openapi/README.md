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
| `/api/v1/events/<event_id>/abstracts` | List the abstracts of an event |
| `/api/v1/events/<event_id>/abstracts/<abstract_id>` | Abstract details |
| `/api/v1/events/<event_id>/papers` | List the papers of an event |
| `/api/v1/events/<event_id>/contributions/<contrib_id>/paper` | Paper of a contribution |
| `/api/v1/events/<event_id>/surveys` | List the surveys of an event |
| `/api/v1/events/<event_id>/surveys/<survey_id>` | Survey details |
| `/api/v1/events/<event_id>/surveys/<survey_id>/submissions` | List the submitted answers of a survey |
| `/api/v1/events/<event_id>/agreements` | List the agreements an event asked for |
| `/api/v1/events/<event_id>/agreements/<agreement_id>` | Agreement details |
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
| `/api/v1/openapi.json` | OpenAPI v3 document |
| `/api/v1/docs` | Swagger UI |

## Entities served

Every entity Indico stores as event or room booking content is served. The cost
columns are the lines of plugin code and of plugin tests each one took, counted
with `wc -l` on the files it owns. Core schemas, request handlers and access
checks are reused, so they cost nothing here.

| Entity | Why it is served | Code | Tests |
| --- | --- | --- | --- |
| Events | Everything else hangs off an event, and its dates, description, location and category are what a caller asks for first. | 96 | 112 |
| Categories | The tree events are organised in, needed to walk from the instance root down to a single event. | 75 | 63 |
| Contributions | The talks of an event, with their speakers, times and room. The entity most often read from outside. | 155 | 121 |
| Subcontributions | The parts a contribution is split into, each with its own speakers and material. | 82 | 95 |
| Sessions | The blocks contributions are grouped in, with their own conveners, location and colours. | 112 | 100 |
| Timetable | The schedule itself, the only view that says when each contribution, session block and break happens. | 148 | 144 |
| Tracks | The programme an event is divided into. Abstracts and contributions point at it. | 75 | 93 |
| Event persons | Speakers, chairs, conveners and authors, with the affiliation each one was entered with. | 157 | 134 |
| Registration forms and registrations | What an event asks registrants for, whether it is open, who registered, in what state and for what price. | 273 | 221 |
| Abstracts | The submissions to a call for abstracts, with their state, tracks, authors and files. | 154 | 176 |
| Papers | The files submitted for a contribution, with every revision and the judgment of each one. | 157 | 185 |
| Surveys and submissions | The questionnaires an event runs, question by question, and the answers it collected. | 210 | 221 |
| Agreements | Who an event asked to sign something and who answered. | 112 | 111 |
| Notes | The minutes attached to an event, a session, a contribution or a subcontribution. | 93 | 98 |
| Attachments | The material and links attached to any of those, and the folders holding them. | 215 | 137 |
| Locations | The places rooms belong to. | 81 | 83 |
| Rooms | The rooms that can be booked, with their capacity, equipment and managers. | 109 | 90 |
| Reservations | The bookings of those rooms, with their occurrences. | 156 | 159 |
| Blockings | The periods a room cannot be booked, and who may still book it. | 99 | 103 |
| Users | The people the instance knows, plus the identity of the caller. | 90 | 101 |
| Shared code (spec, Swagger UI, pagination, schema helpers) | Paid once: the OpenAPI document, the docs page, the list envelope and the field description machinery every resource above builds on. | 421 | 49 |
| **Total** | | **3070** | **2596** |

## Entities not covered

The cost column is what adding each one would take, estimated from the measured
bands above: 150 to 200 lines for an entity with one core schema and plain
access rules, 300 to 350 when the payload nests other objects or hides fields
per role, 450 to 500 when it also needs several endpoints of its own.

| Entity | Why | Estimated cost |
| --- | --- | --- |
| Paper and abstract reviews, ratings and comments | Reviewing is written under the assumption that only the people in the process read it, and each role sees a different part of the same review. Exposing it through an API means reimplementing those rules rather than reusing them. | 600 to 700 |
| Editing (`events/editing`) | The editing workflow is reviewing material under another name: revisions, review comments and file type settings. It also already has its own REST API, used by its React frontend. | 500 to 600 |
| Payment transactions | A transaction stores the raw answer of a payment provider, which is neither documented by Indico nor safe to publish field by field. The registration already says whether it is paid. | 150, plus one payload per provider |
| Event logs | The log is an audit trail of every management action, including the values that changed. It is written for forensics and read in the interface with filters this API has no equivalent for. | 250 to 300 |
| Reminders | Scheduled emails are a management setting, not content: what they produce is an email, and what they hold is a recipient list and a message. | 150 |
| Event roles | Roles only exist to name groups of users inside the ACL of an event. Who may see what is already applied to every response, so listing the ACL adds nothing a caller can act on. | 150 |
| Service requests (`events/requests`) | Request types are provided by plugins, so an instance without plugins has none, and the payload of each one is defined by its own plugin. | 150, plus one payload per plugin |
| Videoconference rooms | Same reason: the room type and everything in it comes from a plugin such as Zoom, and the core model only keeps the link. | 150, plus one payload per plugin |
| Receipts and designer templates | Both are document templates plus the files they render. They are management tooling, and the rendered documents are reached through the registration they belong to. | 300 to 350 |
| Static sites and event series | A static site is a build job with a ZIP file as its result. A series is a grouping with no data of its own beyond the events it holds, which are served already. | 200 |
| Event layout and features | Menu entries, stylesheets, images and feature toggles describe how an event page looks, not what the event is. | 200 |
| Files | Uploaded files are never standalone: each one is reached through the attachment, paper or registration field that owns it, and those carry the access checks. | 100 |
| Groups | Group membership is user data under another name, and local groups can be mapped to an external provider whose members Indico does not store. | 150 |
| Instance administration | Settings, announcements, news, legal texts, authentication, OAuth applications, IP networks and the search service are either instance configuration or a view over the entities above. | 600 or more |

### Where Indico serves them today

None of the fourteen is invisible over GET. Every one of them can be read
without a POST, either as JSON or as a rendered page, so the question is never
whether the data is reachable but in what shape and to whom.

| Entity | Read over GET | Shape |
| --- | --- | --- |
| Paper and abstract reviews, ratings and comments | `/event/<event_id>/manage/abstracts/abstracts.json`, `/event/<event_id>/manage/papers/assignment-list/export-json`, and the abstract and paper pages | JSON, but only as a whole-event dump sent as a file attachment and only to managers. The per-role view of a single review is HTML. |
| Editing | `/event/<event_id>/editing/api/...` and the editable timeline of each contribution | JSON. It already is a REST API, written for its own React frontend. |
| Payment transactions | The registration summary for the registrant, the registration details for the manager | HTML only. The check-in API exposes the date of the last successful transaction and nothing else of it. |
| Event logs | `/event/<event_id>/manage/logs/api/logs`, and the same route under a category, a user and the instance | JSON, with the filters the log interface uses. |
| Reminders | `/event/<event_id>/manage/reminders/` | HTML only. |
| Event roles | `/event/<event_id>/manage/roles/api/roles` and `<role_id>/members.csv` | JSON. |
| Service requests | `/event/<event_id>/manage/requests/` and `/event/<event_id>/manage/requests/<type>/` | HTML only. |
| Videoconference rooms | `/event/<event_id>/videoconference/` and the management page | HTML only. |
| Receipts and designer templates | `/event/<event_id>/manage/receipts/templates`, the same path plus `/images`, `/receipts/default-templates/<name>`, and `<template_id>/data` for designer templates | JSON. |
| Static sites and event series | `/event/<event_id>/manage/tools/static/` for the list, `/event/series/<series_id>` for the series | A static site is HTML plus a ZIP download. A series is JSON. |
| Event layout and features | `/event/<event_id>/manage/layout/` and `/event/<event_id>/manage/features/` | HTML only, plus the rendered stylesheet, logo, images and custom pages. |
| Files | `/files/<uuid>` and `/files/<uuid>/download` | JSON. |
| Groups | `/admin/groups/<provider>/<group_id>/` and `/groups/api/search` | Search is JSON. The group page and its member list are HTML. |
| Instance administration | The pages under `/admin/` | HTML forms, except `/admin/logs/api/logs` and `/admin/version-check`. |

The ones that can only be read as HTML today are payment transactions,
reminders, service requests, videoconference rooms, static sites, event layout
and features, group membership and instance settings. The reason is the same for
all of them: they are management surfaces rendered from a template, never asked
for by a machine. The ones that already answer JSON do it for one caller each,
either a React page of the interface or a manager downloading a file, so their
payloads are shaped after that caller instead of a public contract, and none of
them is versioned or documented.

Event logs are the closest to ready of the group. They already answer JSON over
GET, they are checked as a management surface, and the interface reads them with
filters by date, by kind of entry and by free text. Any endpoint added here would
have to carry the same filtering, otherwise a caller has to download the whole
audit trail of an event to find one entry.

Two entities are served with a field left out on purpose: an agreement never
exposes its signing token, since holding it is enough to answer on behalf of the
person who was asked to sign, and a survey submission never exposes its
respondent, anonymous or not.

Responses reuse Indico's own marshmallow schemas wherever core has one that
describes the object. Several objects are only ever rendered from a template, or
sent as a payload shaped for one React page, or described by a schema that only
loads a submitted form: attachments and their folders, categories, notes,
registration forms, registrations, session types, subcontributions, timetable
entries, breaks, surveys, survey questions and agreements. Those are declared
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

One value is left out of those comparisons because the two APIs mean different
things by it: the check-in API counts every registration a form holds, while
`registration_count` here counts the active ones, which is the number the
participant list publishes. `full_name` is compared, but the two only agree while
the event keeps the default name format, since the check-in API renders a
registrant the way the event configured it and this API always answers
`Firstname Lastname`.

Survey submissions and agreements are the two entities served without a parity
test. The interface only exports submissions as CSV or Excel, behind a POST, so
the survey test compares the questionnaire instead. For agreements, the legacy
endpoint answers with the people an agreement definition asks to sign, and those
definitions come from plugins, so there is nobody to list unless a plugin
providing one is installed. This API returns the agreements the event actually
stored, which is what the management interface lists.

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
