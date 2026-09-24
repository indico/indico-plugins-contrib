# OpenAPI

Read-only REST API for Indico resources, described with an OpenAPI v3 document.

The API reuses Indico's own request handlers, marshmallow schemas and access
checks, so a request returns exactly the data the authenticated user can see in
the web interface. Objects a user cannot access are omitted from lists instead
of being reported as an error.

## Endpoints

| Path | Description |
| --- | --- |
| `/api/v1/events` | List the events the caller can see |
| `/api/v1/events/<event_id>` | Details of one event, with its dates and category |
| `/api/v1/events/<event_id>/contributions` | List the contributions of an event |
| `/api/v1/events/<event_id>/contributions/<contrib_id>` | Details of one contribution of an event |
| `/api/v1/events/<event_id>/contributions/<contrib_id>/subcontributions` | List the subcontributions of a contribution |
| `/api/v1/events/<event_id>/contributions/<contrib_id>/subcontributions/<subcontrib_id>` | Details of one subcontribution of a contribution |
| `/api/v1/events/<event_id>/contribution-types` | List the contribution types of an event |
| `/api/v1/events/<event_id>/contribution-types/<type_id>` | Details of one contribution type of an event |
| `/api/v1/events/<event_id>/contribution-fields` | List the custom contribution fields of an event |
| `/api/v1/events/<event_id>/contribution-fields/<field_id>` | Details of one custom contribution field of an event |
| `/api/v1/events/<event_id>/sessions` | List the sessions of an event |
| `/api/v1/events/<event_id>/sessions/<session_id>` | Details of one session of an event |
| `/api/v1/events/<event_id>/session-types` | List the session types of an event |
| `/api/v1/events/<event_id>/session-types/<type_id>` | Details of one session type of an event |
| `/api/v1/events/<event_id>/timetable` | List the timetable entries of an event |
| `/api/v1/events/<event_id>/timetable/<entry_id>` | Details of one timetable entry of an event |
| `/api/v1/events/<event_id>/tracks` | List the tracks of an event |
| `/api/v1/events/<event_id>/tracks/<track_id>` | Details of one track of an event |
| `/api/v1/events/<event_id>/persons` | List the people taking part in an event |
| `/api/v1/events/<event_id>/persons/<person_id>` | Details of one person taking part in an event |
| `/api/v1/events/<event_id>/registration-forms` | List the registration forms of an event |
| `/api/v1/events/<event_id>/registration-forms/<regform_id>` | Details of one registration form of an event |
| `/api/v1/events/<event_id>/registration-forms/<regform_id>/sections` | List the sections of a registration form, with their fields |
| `/api/v1/events/<event_id>/registration-forms/<regform_id>/sections/<section_id>` | Details of one section of a registration form |
| `/api/v1/events/<event_id>/registration-forms/<regform_id>/invitations` | List the invitations to register through a form |
| `/api/v1/events/<event_id>/registration-forms/<regform_id>/invitations/<invitation_id>` | Details of one invitation to register through a form |
| `/api/v1/events/<event_id>/registrations` | List the registrations of an event |
| `/api/v1/events/<event_id>/registrations/<registration_id>` | Details of one registration, with the answers given |
| `/api/v1/events/<event_id>/registration-tags` | List the tags an event marks its registrations with |
| `/api/v1/events/<event_id>/registration-tags/<tag_id>` | Details of one tag registrations are marked with |
| `/api/v1/events/<event_id>/document-templates` | List the document templates available to an event |
| `/api/v1/events/<event_id>/document-templates/<template_id>` | Details of one document template of an event |
| `/api/v1/events/<event_id>/registrations/<registration_id>/documents` | List the documents generated for a registration |
| `/api/v1/events/<event_id>/registrations/<registration_id>/documents/<file_id>` | Details of one document generated for a registration |
| `/api/v1/events/<event_id>/designer-templates` | List the badge and poster templates available to an event |
| `/api/v1/events/<event_id>/designer-templates/<template_id>` | Details of one badge or poster template |
| `/api/v1/events/<event_id>/abstracts` | List the abstracts of an event |
| `/api/v1/events/<event_id>/abstracts/<abstract_id>` | Details of one abstract submitted to an event |
| `/api/v1/events/<event_id>/abstracts/<abstract_id>/reviews` | List the reviews of an abstract |
| `/api/v1/events/<event_id>/abstracts/<abstract_id>/comments` | List the comments left on an abstract |
| `/api/v1/events/<event_id>/abstract-review-questions` | List the questions abstract reviewers answer |
| `/api/v1/events/<event_id>/abstracts/<abstract_id>/emails` | List the notifications sent about an abstract |
| `/api/v1/events/<event_id>/abstracts/<abstract_id>/emails/<email_id>` | Details of one notification sent about an abstract |
| `/api/v1/events/<event_id>/abstract-email-templates` | List the notification templates of a call for abstracts |
| `/api/v1/events/<event_id>/abstract-email-templates/<template_id>` | Details of one notification template of a call for abstracts |
| `/api/v1/events/<event_id>/papers` | List the papers of an event |
| `/api/v1/events/<event_id>/contributions/<contrib_id>/paper` | The paper of a contribution, with its revisions |
| `/api/v1/events/<event_id>/contributions/<contrib_id>/paper/revisions/<revision_id>/reviews` | List the reviews of a paper revision |
| `/api/v1/events/<event_id>/contributions/<contrib_id>/paper/revisions/<revision_id>/comments` | List the comments left on a paper revision |
| `/api/v1/events/<event_id>/paper-review-questions` | List the questions paper reviewers answer |
| `/api/v1/events/<event_id>/paper-templates` | List the paper templates of an event |
| `/api/v1/events/<event_id>/paper-templates/<template_id>` | Details of one paper template of an event |
| `/api/v1/events/<event_id>/paper-file-types` | List the file types papers are submitted as |
| `/api/v1/events/<event_id>/paper-file-types/<file_type_id>` | Details of one file type papers are submitted as |
| `/api/v1/events/<event_id>/editables` | List the editables of an event |
| `/api/v1/events/<event_id>/contributions/<contrib_id>/editables/<editable_type>` | The editable of a contribution, with its revisions |
| `/api/v1/events/<event_id>/contributions/<contrib_id>/editables/<editable_type>/revisions/<revision_id>/comments` | List the comments left on a revision of an editable |
| `/api/v1/events/<event_id>/editing/tags` | List the tags of the editing workflow |
| `/api/v1/events/<event_id>/editing/<editable_type>/file-types` | List the file types a revision is made of |
| `/api/v1/events/<event_id>/editing/<editable_type>/review-conditions` | List the conditions a revision has to meet to be reviewed |
| `/api/v1/events/<event_id>/surveys` | List the surveys of an event |
| `/api/v1/events/<event_id>/surveys/<survey_id>` | Details of one survey of an event |
| `/api/v1/events/<event_id>/surveys/<survey_id>/submissions` | List the submitted answers of a survey |
| `/api/v1/events/<event_id>/agreements` | List the agreements an event asked for |
| `/api/v1/events/<event_id>/agreements/<agreement_id>` | Details of one agreement an event asked for |
| `/api/v1/events/<event_id>/roles` | List the roles of an event |
| `/api/v1/events/<event_id>/roles/<role_id>` | Details of one role of an event |
| `/api/v1/events/<event_id>/reminders` | List the reminders of an event |
| `/api/v1/events/<event_id>/reminders/<reminder_id>` | Details of one reminder of an event |
| `/api/v1/events/<event_id>/logs` | List the log entries of an event |
| `/api/v1/events/<event_id>/logs/<entry_id>` | Details of one log entry of an event |
| `/api/v1/events/<event_id>/payments` | List the payments of an event |
| `/api/v1/events/<event_id>/payments/<payment_id>` | Details of one payment of an event |
| `/api/v1/events/<event_id>/requests` | List the services an event asked for |
| `/api/v1/events/<event_id>/requests/<request_id>` | Details of one service an event asked for |
| `/api/v1/events/<event_id>/videoconference-rooms` | List the videoconferences of an event |
| `/api/v1/events/<event_id>/videoconference-rooms/<vc_room_id>` | Details of one videoconference of an event |
| `/api/v1/events/<event_id>/offline-copies` | List the offline copies of an event |
| `/api/v1/events/<event_id>/offline-copies/<site_id>` | Details of one offline copy of an event |
| `/api/v1/events/<event_id>/layout` | Layout settings of an event |
| `/api/v1/events/<event_id>/menu` | List the menu entries of an event |
| `/api/v1/events/<event_id>/pages` | List the custom pages of an event |
| `/api/v1/events/<event_id>/pages/<page_id>` | Details of one custom page of an event |
| `/api/v1/events/<event_id>/images` | List the images of an event |
| `/api/v1/events/<event_id>/images/<image_id>` | Details of one image of an event |
| `/api/v1/events/<event_id>/features` | List the features available to an event |
| `/api/v1/events/<event_id>/notes` | List the notes of an event and of everything inside it |
| `/api/v1/events/<event_id>/notes/<note_id>` | Details of one note of an event |
| `/api/v1/events/<event_id>/notes/<note_id>/revisions` | List the successive versions of a note |
| `/api/v1/events/<event_id>/notes/<note_id>/revisions/<revision_id>` | Details of one version of a note |
| `/api/v1/events/<event_id>/attachments` | List the attachments of an event |
| `/api/v1/events/<event_id>/attachments/<attachment_id>` | Details of one attachment of an event |
| `/api/v1/events/<event_id>/sessions/<session_id>/attachments` | List the attachments of a session |
| `/api/v1/events/<event_id>/sessions/<session_id>/attachments/<attachment_id>` | Details of one attachment of a session |
| `/api/v1/events/<event_id>/contributions/<contrib_id>/attachments` | List the attachments of a contribution |
| `/api/v1/events/<event_id>/contributions/<contrib_id>/attachments/<attachment_id>` | Details of one attachment of a contribution |
| `/api/v1/events/<event_id>/contributions/<contrib_id>/subcontributions/<subcontrib_id>/attachments` | List the attachments of a subcontribution |
| `/api/v1/events/<event_id>/contributions/<contrib_id>/subcontributions/<subcontrib_id>/attachments/<attachment_id>` | Details of one attachment of a subcontribution |
| `/api/v1/categories` | List the categories events are organised in |
| `/api/v1/categories/<category_id>` | Details of one category events are organised in |
| `/api/v1/categories/<category_id>/roles` | List the roles of a category |
| `/api/v1/categories/<category_id>/roles/<role_id>` | Details of one role of a category |
| `/api/v1/categories/<category_id>/move-requests` | List the event move requests of a category |
| `/api/v1/categories/<category_id>/move-requests/<request_id>` | Details of one request to move an event into a category |
| `/api/v1/categories/<category_id>/logs` | List the log entries of a category |
| `/api/v1/categories/<category_id>/logs/<entry_id>` | Details of one log entry of a category |
| `/api/v1/categories/<category_id>/attachments` | List the attachments of a category |
| `/api/v1/categories/<category_id>/attachments/<attachment_id>` | Details of one attachment of a category |
| `/api/v1/locations` | List the locations rooms belong to |
| `/api/v1/locations/<location_id>` | Details of one location rooms belong to |
| `/api/v1/map-areas` | List the areas of the room map |
| `/api/v1/map-areas/<area_id>` | Details of one area of the room map |
| `/api/v1/equipment-types` | List the equipment a room can have |
| `/api/v1/equipment-types/<equipment_type_id>` | Details of one kind of equipment a room can have |
| `/api/v1/room-features` | List the features a room can be searched by |
| `/api/v1/room-features/<feature_id>` | Details of one feature a room can be searched by |
| `/api/v1/rooms` | List the rooms that can be booked |
| `/api/v1/rooms/<room_id>` | Details of one room that can be booked |
| `/api/v1/rooms/<room_id>/attributes` | List the attribute values of a room |
| `/api/v1/rooms/<room_id>/bookable-hours` | List the hours a room can be booked for |
| `/api/v1/rooms/<room_id>/nonbookable-periods` | List the periods a room cannot be booked for |
| `/api/v1/reservations` | List the bookings made for rooms |
| `/api/v1/reservations/<reservation_id>` | Details of one booking made for a room |
| `/api/v1/reservations/<reservation_id>/edit-logs` | List the history of a room booking |
| `/api/v1/reservations/<reservation_id>/links` | List the objects a room booking was made for |
| `/api/v1/blockings` | List the blockings that keep rooms from being booked |
| `/api/v1/blockings/<blocking_id>` | Details of one blocking that keeps rooms from being booked |
| `/api/v1/users` | List the user accounts of the instance |
| `/api/v1/users/me` | Details of the authenticated user |
| `/api/v1/users/<user_id>` | Details of one user account of the instance |
| `/api/v1/users/me/settings` | Preferences of the authenticated user |
| `/api/v1/users/me/emails` | List the email addresses of the authenticated user |
| `/api/v1/users/me/favorite-users` | List the users the caller marked as favourites |
| `/api/v1/users/me/favorite-categories` | List the categories the caller marked as favourites |
| `/api/v1/users/me/favorite-events` | List the events the caller marked as favourites |
| `/api/v1/users/me/favorite-rooms` | List the rooms the caller marked as favourites |
| `/api/v1/users/me/data-export` | Data export the authenticated user requested |
| `/api/v1/affiliations` | List the organisations people can be affiliated with |
| `/api/v1/affiliations/<affiliation_id>` | Details of one organisation people can be affiliated with |
| `/api/v1/files` | List the files uploaded to the instance |
| `/api/v1/files/<uuid>` | Details of one file uploaded to the instance |
| `/api/v1/groups` | List the groups defined in Indico itself |
| `/api/v1/groups/<group_id>` | Details of one group defined in Indico itself |
| `/api/v1/event-series` | List the event series the caller manages |
| `/api/v1/event-series/<series_id>` | Details of one series of related events |
| `/api/v1/event-labels` | List the labels an event can be marked with |
| `/api/v1/event-labels/<event_label_id>` | Details of one label an event can be marked with |
| `/api/v1/reference-types` | List the systems external identifiers point at |
| `/api/v1/reference-types/<reference_type_id>` | Details of one system external identifiers point at |
| `/api/v1/permissions` | List the permissions an ACL entry can grant |
| `/api/v1/categories/<category_id>/acl` | List the ACL of a category |
| `/api/v1/categories/<category_id>/attachments/<attachment_id>/acl` | List the ACL of an attachment of a category |
| `/api/v1/categories/<category_id>/attachment-folders/<folder_id>/acl` | List the ACL of an attachment folder of a category |
| `/api/v1/events/<event_id>/acl` | List the ACL of an event |
| `/api/v1/events/<event_id>/sessions/<session_id>/acl` | List the ACL of a session |
| `/api/v1/events/<event_id>/contributions/<contrib_id>/acl` | List the ACL of a contribution |
| `/api/v1/events/<event_id>/tracks/<track_id>/acl` | List the ACL of a track |
| `/api/v1/events/<event_id>/menu/<entry_id>/acl` | List the ACL of a menu entry |
| `/api/v1/events/<event_id>/attachments/<attachment_id>/acl` | List the ACL of an attachment of an event |
| `/api/v1/events/<event_id>/attachment-folders/<folder_id>/acl` | List the ACL of an attachment folder of an event |
| `/api/v1/events/<event_id>/sessions/<session_id>/attachments/<attachment_id>/acl` | List the ACL of an attachment of a session |
| `/api/v1/events/<event_id>/sessions/<session_id>/attachment-folders/<folder_id>/acl` | List the ACL of an attachment folder of a session |
| `/api/v1/events/<event_id>/contributions/<contrib_id>/attachments/<attachment_id>/acl` | List the ACL of an attachment of a contribution |
| `/api/v1/events/<event_id>/contributions/<contrib_id>/attachment-folders/<folder_id>/acl` | List the ACL of an attachment folder of a contribution |
| `/api/v1/events/<event_id>/contributions/<contrib_id>/subcontributions/<subcontrib_id>/attachments/<attachment_id>/acl` | List the ACL of an attachment of a subcontribution |
| `/api/v1/events/<event_id>/contributions/<contrib_id>/subcontributions/<subcontrib_id>/attachment-folders/<folder_id>/acl` | List the ACL of an attachment folder of a subcontribution |
| `/api/v1/rooms/<room_id>/acl` | List the ACL of a room |
| `/api/v1/locations/<location_id>/acl` | List the ACL of a location |
| `/api/v1/openapi.json` | OpenAPI v3 document |
| `/api/v1/docs` | Swagger UI |

## Entities served

The list below is what the API serves. It leaves out the instance
administration area and the log of a user account, described under
Entities not covered. The cost columns are the lines of plugin code and of plugin
tests each entity took, counted with `wc -l` on the files it owns. Core schemas,
request handlers and access checks are reused, so they cost nothing here.

| Entity | Why it is served | Code | Tests |
| --- | --- | --- | --- |
| Events | Everything else hangs off an event, and its dates, description, location, category and external identifiers are what a caller asks for first. | 150 | 182 |
| Categories | The tree events are organised in, needed to walk from the instance root down to a single event. | 69 | 76 |
| Contributions | The talks of an event, with their speakers, times and room. The entity most often read from outside. | 159 | 132 |
| Contribution types and fields | The types an event sorts its talks into and the extra questions it asks about each one, which is what the values carried by a contribution point at. | 169 | 186 |
| Subcontributions | The parts a contribution is split into, each with its own speakers and material. | 80 | 114 |
| Sessions | The blocks contributions are grouped in, with their own conveners, location and colours. | 93 | 104 |
| Session types | The types an event sorts its sessions into. | 65 | 77 |
| Timetable | The schedule itself, the only view that says when each contribution, session block and break happens. | 134 | 205 |
| Tracks | The programme an event is divided into. Abstracts and contributions point at it. | 74 | 100 |
| Event persons | Speakers, chairs, conveners and authors, with the affiliation each one was entered with. | 142 | 156 |
| Registration forms, registrations and tags | What an event asks registrants for, section by section and field by field, whether the form is open, who registered, in what state, for what price and with what answers, plus the tags the organisers group registrations with. | 568 | 662 |
| Registration invitations | Who an event invited to register, in what state each invitation is and which registration it turned into. | 113 | 126 |
| Abstracts | The submissions to a call for abstracts, with their state, tracks, authors and files. | 158 | 200 |
| Abstract notifications | The templates a call for abstracts notifies its submitters with, and the mail each abstract actually triggered. | 183 | 162 |
| Papers | The files submitted for a contribution, with every revision and the judgment of each one. | 157 | 193 |
| Paper templates and file types | The template an author starts a paper from and the file types a submission is accepted in. | 158 | 175 |
| Surveys and submissions | The questionnaires an event runs, question by question, and the answers it collected. | 210 | 193 |
| Agreements | Who an event asked to sign something and who answered. | 112 | 105 |
| Event roles | The groups of users an event grants permissions to, and the people holding each one. | 99 | 104 |
| Category roles | The same, one level up: the groups a category grants permissions to, which every event under it inherits. | 91 | 102 |
| Event move requests | The events asking to be moved into a category, in what state each request is and who answered it. | 95 | 109 |
| Reminders | The emails an event has scheduled for its participants, with their recipient filters and their message. | 140 | 101 |
| Event and category logs | Every management action an event or a category recorded, with the values that changed, which is the only account of who did what. | 227 | 306 |
| Payments | What each registrant was charged, through which provider, and whether the payment went through. | 112 | 129 |
| Service requests | The services an event asked the instance to provide, in what state each request is, and who accepted or rejected it. | 131 | 157 |
| Videoconferences | The videoconference rooms attached to an event, a contribution or a session block, and whether the service still has each one. | 115 | 155 |
| Offline copies | The copies of an event built as static HTML, in what state each build is and where the ZIP file of a finished one is. | 95 | 87 |
| Event series | The groupings several events are presented as one through, with the title pattern and the links they share. | 78 | 109 |
| Event layout | The menu of an event page, the custom pages hanging off it, the images uploaded for it and the settings saying how the page is rendered. | 308 | 322 |
| Event features | Which optional parts of Indico an event has turned on, out of the ones its type allows. | 61 | 60 |
| Document templates and documents | The templates an event renders invoices and certificates from, the fields each one asks for, and the documents already generated for a registration. | 219 | 298 |
| Designer templates | The badge and poster templates an event draws tickets from, with the drawing itself and the images it places on it. | 128 | 143 |
| Notes | The minutes attached to an event, a session, a contribution or a subcontribution, and every version each one went through. | 152 | 139 |
| Attachments | The material and links attached to any of those, and the folders holding them. | 225 | 126 |
| Locations | The places rooms belong to. | 86 | 93 |
| Map areas | The parts of the map the room booking interface opens on. | 70 | 66 |
| Rooms | The rooms that can be booked, with their capacity, equipment and managers. | 113 | 118 |
| Equipment types and room features | The equipment a room can have and the features a room search filters by, which is what the equipment of a room points at. | 123 | 109 |
| Room attributes | The values an instance stores per room on top of the columns Indico defines itself, which is where a local identifier or an owner ends up. | 66 | 77 |
| Room availability | The hours a room can be booked for and the periods it cannot, which is what a booking request is checked against. | 89 | 94 |
| Reservations | The bookings of those rooms, with their occurrences. | 153 | 150 |
| Reservation history and links | Every change made to a booking since it was created, and the event, contribution or session block it was made for. | 154 | 170 |
| Blockings | The periods a room cannot be booked, and who may still book it. | 99 | 95 |
| Users | The identity of the caller, plus the accounts the instance holds for whoever administers it. | 79 | 98 |
| Affiliations | The organisations the instance defines, which is what the affiliation of a user, a speaker or a registrant points at. | 60 | 65 |
| Favourites | The users, categories, events and rooms the caller starred, which is what their dashboard and the room booking pages open with. | 96 | 72 |
| Personal data | The preferences the caller saved, the addresses they receive Indico mail at and the data export they asked for. | 136 | 78 |
| Files | The files uploaded to the instance, with the name, type and size of each one. | 77 | 65 |
| Groups | The groups of users the instance itself defines, and the members of each one. | 99 | 85 |
| Event labels | The labels an event can be marked with, such as `Cancelled`, as the administrators defined them. | 70 | 57 |
| Reference types | The external systems an event, a contribution or a subcontribution can carry an identifier of, such as a DOI, with the scheme and the URL template each one builds its links from. | 71 | 41 |
| Protection and permissions | The ACL of every object that holds one, entry by entry, with what each principal is granted, plus the catalogue saying what every permission name allows. | 385 | 225 |
| Reviews, ratings and comments | What the reviewers of an abstract and of a paper wrote about it, with the answer given to every question of the reviewing form and the comments left along the way, plus the questions themselves. | 288 | 416 |
| Editables, revisions and editing settings | The paper, slides or poster a contribution is edited into, revision by revision, with the files of each one, the comments left on it and the tags, file types and review conditions the workflow is configured with. | 361 | 353 |
| Shared code (spec, Swagger UI, pagination, schema helpers) | Paid once: the OpenAPI document, the docs page, the list envelope and the field description machinery every resource above builds on, plus the fixtures and the comparison helper every test builds on. | 487 | 275 |
| **Total** | | **8232** | **8397** |

## Entities not covered

The cost column is what adding each one would take, estimated from the measured
bands above: 150 to 200 lines for an entity with one core schema and plain
access rules, 300 to 350 when the payload nests other objects or hides fields
per role, 450 to 500 when it also needs several endpoints of its own.

| Entity | Why | Estimated cost |
| --- | --- | --- |
| Instance administration | Settings, announcements, news, legal texts, authentication, OAuth applications, IP networks and the search service are either instance configuration or a view over the entities above. | 600 or more |
| User logs | The audit trail of one account: the profile changes, the permissions granted and the mail sent to it. Indico shows it in the administration area alone and never to the account it belongs to, so serving it here would mean answering one caller with the record of another, which the personal endpoints never do. Identities, API keys and personal tokens are credentials and are not served at all either. | 150 to 200 |

### Where Indico serves them today

Neither of them is invisible over GET. Both can be read without a POST,
either as JSON or as a rendered page, so the question is never whether the data
is reachable but in what shape and to whom.

| Entity | Read over GET | Shape |
| --- | --- | --- |
| User logs | `/user/<user_id>/logs`, with JSON at `/user/<user_id>/api/logs` | JSON behind an HTML page, served to instance administrators alone. |
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

A profile follows the same rule: every caller reads their own at `/users/me`,
and reading the profile of somebody else, or listing the accounts of the
instance, is left to administrators, the audience of the user management area.
Deleted accounts are never served.

The ACL of an object is served to whoever manages that object, the audience of
the protection page showing it today. An entry names a principal, with the
identifier and the name Indico prints next to it, and says whether it grants
reading, full management or a list of named permissions. What a parent grants is
not repeated: an object inheriting its protection is read by walking up the
chain, exactly as the access check does. A permission an entry holds but its
object no longer defines is left out, since it grants nothing. The access key of
an object is never served: holding it is enough to read what it protects. A
track is the one object whose ACL answers to the managers of its event rather
than to its own entries, because its permissions belong to the abstract
reviewing workflow and its programme is edited from the event, which is where
Indico checks. Attachments, their folders and menu entries name principals and
grant them nothing beyond reading, so their entries carry no permissions at all,
and a blocking is the one object whose ACL was already served: the principals
that may still book the rooms are part of the blocking itself, which is how the
room booking interface shows them. Since a name stored in an entry means nothing
on its own, `/permissions` describes what each one allows, per kind of object.

A review and a comment are served to whoever Indico lets read that single entry,
which is the check the timeline of an abstract and of a paper applies when it
renders itself: the author of an entry always reads their own, a judge reads
every one, and a comment is read by whichever of the conveners, the reviewers,
the people listed on the submission or every user its visibility names. An entry
the caller may not read is left out of the list rather than reported, the same
way the timeline simply does not draw it, so two callers reading the same
abstract get different lists. Reaching them at all still needs access to the
abstract or to the paper, so somebody outside the submission is answered 403
before any entry is considered. An answer carries the question it was given to,
which is what makes a value mean anything, and the score of a review is the
average of the answers that count towards it. The questions of the reviewing
form are served on their own to whoever manages the reviewing, the audience of
the settings page defining them, since a reviewer already gets each question
next to the answer they gave it.

An editable is served to whoever may see its timeline, which is the people
listed on the contribution, whoever may submit it and the editing team of the
event, and the list of editables leaves out the ones the caller cannot reach
rather than reporting them. A revision the editing team took back is served to
the team alone, and a comment marked as internal likewise, which is what the
timeline draws for each of them. An event may run its editing team
anonymously, and then whoever is not part of it reads an action of the team
without the name behind it: the user is served with its fields empty and marked
as anonymous, so a hidden name is never confused with an editable nobody is
assigned to. A file of a revision carries the identifier `/files` takes, which
is how Indico hands out a file it protects by keeping that identifier secret.
The tags and the file types are served to whoever can see the event, since they
name what a revision is made of and what it is marked with, while the review
conditions are served to the editing managers, the audience of the page defining
them. What the editing service stored about an editable is left out, as the
answer of a payment provider is: it belongs to the service rather than to
Indico, and the actions it offers are not something a read-only API can hand on.

The log of an event is served with the filters the log interface uses: the area
of the event an entry belongs to, free text over the same columns the interface
searches, and the registration an entry is about. Without them a caller would
have to read the whole audit trail of an event to find one entry. A caller who
only manages the registrations of the event has to pass the registration filter,
and reaches a single entry only when that entry is about a registration, which
is the rule the log interface applies as well. The log of a category is served
the same way to whoever manages the category, with the same filters over the two
realms a category records, while the log of a user and of the instance is not
served: those belong to instance administration.

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

Contribution types, session types, paper templates and paper file types are
served to whoever can see the event, since a contribution, a session and a paper
already carry the value pointing at one and these are the definitions saying what
it means. Custom contribution fields follow the values they describe instead: a
manager gets every field, and everybody else gets the active ones whose values are
public, which are exactly the values a contribution shows them.

Registration invitations are served to the managers of the event alone, the
audience of the page listing them. The UUID of an invitation is left out, as the
signing token of an agreement is: it is the secret in the link the invitee
received, and whoever holds it may register on their behalf.

The notification templates of a call for abstracts are served to its managers,
the audience of the page writing them, and the notifications an abstract
triggered to whoever may judge it, which is who the abstract page shows the log
to. Both carry the text as it was handled: the templates with their placeholders
left in, the log with them already filled.

Category roles are served to the managers of the category, the audience of the
page listing them, and so are the requests to move an event into it. What the
request list serves beyond the moderation page is history: the page lists the
pending requests alone, while the list answers with every request the category
ever received, which is what makes the state worth having as a filter.

Map areas, bookable hours and non-bookable periods are served to whoever may use
the room booking system, since the map opens on an area and the booking form
already draws both kinds of availability, day by day, for any room it shows.
Core answers with the availability rows themselves only through its
administration API, which is where they are edited, so that is what the
comparison is made against. Room attributes follow the same rule with one
exception: an attribute marked as hidden is dropped by the endpoint the room page
calls, whoever asks, and is served here to the managers of the room, the audience
that edits it in the administration area.

The history of a booking is served to whoever may see the details of the booking,
which is the check the booking page makes before rendering it, and the objects a
booking was made for to whoever may use the room booking system. A link names its
event, contribution or session block by identifier whatever the caller can read,
and the title only when the caller can access the object itself.

Equipment types and room features are served to whoever may use the room booking
system, since the search form already filters rooms by both. An equipment type
carries whether any room still has it, which is the column the administration
list shows, and the features it maps to, which is how a room ends up drawn with
one.

Reference types, event labels and affiliations are served to any authenticated
caller. Each of them is a catalogue the instance defines once and then hands to
everybody: a reference of an event already names its type, an event already shows
its label, and a user already carries the affiliation it links to, so what is
served here is the definition behind a value the caller can read anyway.

Registration tags are served to whoever manages the registrations of an event,
the audience the tags exist for: a registration carries them only in the payload
a manager gets, and the tag list is edited from the same management area.

An older revision of a note is served to whoever manages the object the note
hangs off, which is a narrower audience than the note itself. The current text is
what the object shows, while a revision holds what it used to say and no longer
does.

The preferences of the caller, the addresses they receive Indico mail at, the
export of their own data they asked Indico to build and the four lists of
favourites they keep are served to the caller alone. Indico puts all of it on the
profile page, which an administrator may open for somebody else; this API answers
about the account holding the token and about no other, so none of these
endpoints takes a user id in its path. A favourite pointing at something the
caller may no longer read, or at something since deleted, is left out of the
list, which is the one place these endpoints answer with less than the profile
page does. A favourite user is served with the name and the address the user
search answers with, since that is the interface the caller picked them from.

Responses reuse Indico's own marshmallow schemas wherever core has one that
describes the object. Several objects are only ever rendered from a template, or
sent as a payload shaped for one React page, or described by a schema that only
loads a submitted form: attachments and their folders, categories, notes,
registration forms, registrations, registration invitations, session types,
subcontributions, timetable entries, breaks, surveys, survey questions,
agreements, generated documents, designer templates, paper templates, abstract
notification templates and the notifications sent from them, category roles,
event move requests, room attributes, bookable hours, non-bookable periods, the
history of a booking and the objects it was made for, registration tags, note
revisions, event labels, reference types and editing review conditions. Those are declared here as
automatic schemas over the model, so their field names and types still come from
Indico rather than from a hand-written mapping.

## How a resource is built

A resource is one module under `indico_openapi/resources/`, holding its schema,
its request handlers and an `ENDPOINTS` list. The package imports every module
it finds and joins the lists, the blueprint registers one URL rule per entry and
the OpenAPI document is generated from the same entries, so a route and its
documentation cannot disagree on what is served. Dropping the module in is the
whole change; nothing else registers it.

```python
@dataclass(frozen=True)
class Endpoint:
    rule: str
    name: str
    rh: type[RH]
    summary: str
    tag: str
    schema: type | None = None
    many: bool = False
```

Tracks are the smallest complete example. The schema extends the one core
already has for the object and adds a description per field, since the fields
inherited from core carry none and the generated document is the only reference
a caller gets. A test fails as soon as any field of any schema is left
undescribed.

```python
class TrackSchema(DescribedFieldsMixin, CoreTrackSchema):
    class Meta(CoreTrackSchema.Meta):
        fields = (*CoreTrackSchema.Meta.fields, 'track_group')
        descriptions = {
            'id': 'Numeric identifier of the track, unique across the whole instance.',
            'title': 'Title of the track.',
            ...
        }

    track_group = fields.Nested(TrackGroupReferenceSchema)
```

The request handlers subclass the bases core uses for its own pages, so the
access check is the one the web interface runs: `RHProtectedEventBase` for what
anyone allowed to see the event may read, `RHManageEventBase` for what only its
managers see. A detail handler loads the row scoped to the event and dumps it. A
list handler mixes in `RHListBase`, declares its schema and its query, and gets
the pagination and the per-row access check from the base; a track has no access
list of its own, so its per-row check is a constant, while a note answers with
the check of the object it is attached to. `json_errors` turns the exceptions
core raises into the JSON errors the document describes.

```python
@json_errors
class RHTrackList(RHListBase, RHProtectedEventBase):
    schema = TrackSchema

    def _query(self):
        return Track.query.with_parent(self.event).order_by(Track.position)

    def _can_access(self, obj):
        return True


ENDPOINTS = [
    Endpoint(
        rule='/events/<int:event_id>/tracks',
        name='tracks',
        rh=RHTrackList,
        schema=TrackSchema,
        many=True,
        summary='List the tracks of an event',
        tag='Tracks',
    ),
    Endpoint(
        rule='/events/<int:event_id>/tracks/<int:track_id>',
        name='track',
        rh=RHTrack,
        schema=TrackSchema,
        summary='Track details',
        tag='Tracks',
    ),
]
```

A list that takes filters extends `ListArgs` with them and names them as
parameters of its query, as the event list does with `category_id`; the document
picks them up as query parameters from the same class. When core has no schema
for the object, the resource declares an automatic schema over the model
instead, as the notes resource does, so the field names and types still come
from Indico.

The test module of a resource covers the detail and the list, the 403 an
outsider gets, the 404 an identifier of another event gets, and the parity with
the endpoint Indico serves today, described in the next section. The tuple of
compared fields it declares is what the live check imports, so a field added to
the schema is compared everywhere at once or nowhere.

## Parity with the endpoints Indico already serves

Every entity Indico already answers with over GET has a test asserting that this
API and that endpoint return the same values, field by field. The entities with
nothing to compare against are listed at the end of this section. The payloads
have a different shape, so the tests compare the underlying values rather than
the raw JSON.

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
| Registration forms, sections, fields, registrations and answers | `/api/checkin/event/<event_id>/forms/[<reg_form_id>/registrations/[<registration_id>]]` |
| Abstracts | `/event/<event_id>/manage/abstracts/abstracts.json` |
| Papers | `/event/<event_id>/manage/papers/assignment-list/export-json` |
| Abstract reviews and comments | `/event/<event_id>/manage/abstracts/abstracts.json`, fields `reviews` and `comments` |
| Paper reviews and comments | `/event/<event_id>/manage/papers/assignment-list/export-json`, fields `reviews` and `comments` of each revision |
| Paper reviewing questions | the same export, fields `layout_review_questions` and `content_review_questions` |
| Editables, revisions and comments | `/event/<event_id>/api/contributions/<contrib_id>/editing/<editable_type>` |
| Editing tags | `/event/<event_id>/editing/api/tags` |
| Editing file types | `/event/<event_id>/editing/api/<editable_type>/file-types` |
| Editing review conditions | `/event/<event_id>/editing/api/<editable_type>/review-conditions` |
| Surveys | `/event/<event_id>/manage/surveys/<survey_id>/questionnaire/survey.json` |
| Locations | `/rooms/api/locations` |
| Blockings | `/rooms/api/blockings/` |
| Files | `/files/<uuid>` |
| Groups | `/groups/api/search` |
| Event roles | `/event/<event_id>/manage/roles/api/roles/` and `/event/<event_id>/manage/api/event-roles` |
| Event logs | `/event/<event_id>/manage/logs/api/logs` |
| Category logs | `/category/<category_id>/manage/logs/api/logs` |
| Event series | `/event-series/<series_id>` |
| Document templates | `/event/<event_id>/manage/receipts/templates` |
| Designer templates | `/event/<event_id>/manage/designer/<template_id>/data` |
| Contribution types | `/event/<event_id>/contributions/<contrib_id>.json`, field `type` |
| Custom contribution fields | `/event/<event_id>/manage/contributions/api/fields/` |
| Paper file types | `/event/<event_id>/papers/api/file-types/` |
| Category roles | `/category/<category_id>/manage/roles/api/roles/` |
| Registration tags | `/api/checkin/event/<event_id>/`, field `registration_tags` |
| Affiliations | `/api/admin/affiliations` |
| Favourite users | `/user/api/favorites/users` |
| Favourite categories | `/user/api/favorites/categories` |
| Favourite events | `/user/api/favorites/events` |
| Favourite rooms | `/rooms/api/user/favorite-rooms/` |
| Event move requests | `/category/<category_id>/api/event-move-requests` |
| Map areas | `/rooms/api/map-areas` |
| Equipment types | `/rooms/api/equipment` |
| Room features | `/rooms/api/admin/features` |
| Room attributes | `/rooms/api/rooms/<room_id>/attributes` |
| Room availability | `/rooms/api/admin/rooms/<room_id>/availability` |
| Reservation history | `/rooms/api/bookings/<reservation_id>`, field `edit_logs` |
| Reservation links | `/rooms/api/bookings/<reservation_id>/links` |

Event roles are the one entity whose comparison needs two endpoints at once:
the management API serves the members of a role but not its id, and the
protection API the id but not the members, so the test compares
against both payloads joined on the code each of them orders by.

The four lists of favourites are compared on identifiers alone. The interface
keeps the objects it already holds and asks Indico only which ones are starred,
so three of those endpoints answer with a bare list of ids and the fourth with
one entry per id. This API answers with the objects themselves, in the shape it
serves them everywhere else, and what the two have to agree on is which objects
are in the list.

Reviewing is compared out of the two exports the reviewing pages download, which
is where Indico dumps a whole event at once. Three values are computed rather
than compared: the abstracts export names the question of a rating by identifier
and leaves the score of a review to be averaged from its ratings, and the papers
export leaves out the flag saying whether an answer counts towards that score,
which holds for every question but a rating taken out of it by hand. The
questions abstract reviewers answer are the one part compared on four fields
alone, since that export describes a question with its identifier, title,
position and that same flag, and the rest of it is only ever rendered into the
reviewing settings page.

An editable is compared against the timeline its own page is drawn from, which
serves the whole workflow of one contribution in a single payload: the editable,
its revisions, and the files, tags and comments of each revision. Two values are
computed rather than compared: the timeline nests the state of an editable and
the type of a revision as an object with a name and a translated title, and it
serves the revisions themselves instead of counting the ones carrying files.
A review condition is compared as the pair the editing page reads it as, since
that endpoint answers with the identifier of a condition followed by the file
types it asks for and nothing else.

The member list of a group is left out of its comparison, for lack of anything
to compare it against: the group search answers with the name and the identifier
of a group and never with its members, and the member list of the administration
area is rendered as HTML.

The identifier of the session block a booking was made for is left out for the
same reason. The booking interface links to the session holding the block, so
the payload carries the id of the event, and the id of the contribution when the
booking was made for one, but nothing that names the block itself.

One value is left out of those comparisons because the two APIs mean different
things by it: the check-in API counts every registration a form holds, while
`registration_count` here counts the active ones, which is the number the
participant list publishes. `full_name` is compared, but the two only agree while
the event keeps the default name format, since the check-in API renders a
registrant the way the event configured it and this API always answers
`Firstname Lastname`.

The timetable needs the same kind of care. A poster is shown for as long as the
session it is presented in, and the legacy export answers with that displayed
span for the contributions of a poster session. This API answers with the
schedule as stored, which is what a timetable entry holds, so the comparison
stretches those contributions over their session block before matching them.

Survey submissions, agreements, reminders, payments, service requests,
videoconferences, offline copies, event layout, event features, the documents
generated for a registration, session types, registration invitations, paper
templates, abstract notifications, reference types, event labels, note
revisions, user preferences, email addresses, data exports and access lists are
the entities served without a parity test. The interface only exports submissions as CSV or Excel, behind a
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
the endpoint its editor reads. Session types, registration invitations, paper
templates and both the notification templates of a call for abstracts and the
notifications it sent are only ever rendered as management pages, with a download
link behind a paper template and nothing behind the rest. The preferences and the
email addresses of a caller are rendered as forms, which answer to POST, and the
one JSON endpoint of the data export is the call that starts an export rather
than one that describes it, so the three of them are checked against the values
the demo data seeds instead. An ACL has nothing to compare against either: the
protection page renders its own entries into a form, and the one endpoint behind
it, `/event/<event_id>/manage/protection/acl`, answers with an HTML fragment
listing what the parents grant. The seeded entries are what the ACLs are checked
against, and every permission they hand out is looked up in the catalogue the
API serves.

Reference types and event labels are managed from an administration page that
answers HTML, and neither catalogue is served as JSON anywhere, so there is
nothing to compare them against either. Note revisions are not rendered at all:
Indico keeps every version of a note and only ever shows the current one.

Two comparisons are made against an endpoint the administration area calls,
since the catalogue behind it is only listed as a whole there: the features a
room can be searched by, which every user of the room booking system already
gets next to the equipment they belong to, and the affiliations, which anybody
filling in a name searches through the endpoint of the interface.

### Checking a running instance

The tests above run on rows built by fixtures. `scripts/seed_demo_data.py` fills
a running instance with rows for every entity served, and
`scripts/live_parity.py` repeats the comparisons over HTTP against it, importing
the mappings from the test modules so the two cannot drift apart. The entities
with no payload to compare against are checked by count, and the layout, the
features and the ACLs by value, against what the seed wrote to its manifest.
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

## Changelog

### 3.3

- Initial release
