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

## Entities not covered

Everything Indico stores as event or room booking content is served: events,
categories, contributions, subcontributions, sessions, timetable entries,
tracks, event persons, registration forms, registrations, abstracts, papers,
surveys and their submissions, agreements, notes, attachments, locations, rooms,
bookings, blockings and users.

What is left out, and why:

| Entity | Why |
| --- | --- |
| Paper and abstract reviews, ratings and comments | Reviewing is written under the assumption that only the people in the process read it, and each role sees a different part of the same review. Exposing it through an API means reimplementing those rules rather than reusing them. |
| Editing (`events/editing`) | The editing workflow is reviewing material under another name: revisions, review comments and file type settings. It also already has its own REST API, used by its React frontend. |
| Payment transactions | A transaction stores the raw answer of a payment provider, which is neither documented by Indico nor safe to publish field by field. The registration already says whether it is paid. |
| Event logs | The log is an audit trail of every management action, including the values that changed. It is written for forensics and read in the interface with filters this API has no equivalent for. |
| Reminders | Scheduled emails are a management setting, not content: what they produce is an email, and what they hold is a recipient list and a message. |
| Event roles | Roles only exist to name groups of users inside the ACL of an event. Who may see what is already applied to every response, so listing the ACL adds nothing a caller can act on. |
| Service requests (`events/requests`) | Request types are provided by plugins, so an instance without plugins has none, and the payload of each one is defined by its own plugin. |
| Videoconference rooms | Same reason: the room type and everything in it comes from a plugin such as Zoom, and the core model only keeps the link. |
| Receipts and designer templates | Both are document templates plus the files they render. They are management tooling, and the rendered documents are reached through the registration they belong to. |
| Static sites and event series | A static site is a build job with a ZIP file as its result. A series is a grouping with no data of its own beyond the events it holds, which are served already. |
| Event layout and features | Menu entries, stylesheets, images and feature toggles describe how an event page looks, not what the event is. |
| Files | Uploaded files are never standalone: each one is reached through the attachment, paper or registration field that owns it, and those carry the access checks. |
| Groups | Group membership is user data under another name, and local groups can be mapped to an external provider whose members Indico does not store. |
| Instance administration | Settings, announcements, news, legal texts, authentication, OAuth applications, IP networks and the search service are either instance configuration or a view over the entities above. |

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

## Parity with the legacy export API

Every entity that the legacy export API (`/export/...`) also serves has a test
asserting both APIs return the same values, field by field. The payloads have a
different shape, so the tests compare the underlying values rather than the raw
JSON.

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

Tracks, registrations, abstracts, papers, surveys, locations and blockings have
no counterpart in the legacy API, so there is nothing to compare them against.

Agreements are the one entity both APIs serve without a parity test. The legacy
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
