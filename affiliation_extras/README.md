# Affiliation Extras Plugin

This plugin extends Indico's predefined affiliations management with groups, tags,
contact lists, and focal points. Affiliation catalogs define which organizations participants
can represent at an event, while registration tools support inviting representatives and
letting focal points manage registrations for their affiliations.

## Features

- Create, edit and delete affiliation tags (`code`, `name`, `color`)
- Create, edit and delete affiliation groups (`code`, `name`, `metadata`)
- Assign tags to groups
- Assign groups and tags to affiliations
- Organize affiliation contact emails into named or unnamed lists
- Disable and re-enable individual contact emails
- Assign Indico users as affiliation focal points
- Show groups and tags in the affiliations dashboard table
- Filter affiliations by groups, tags, and active contact emails, including specific contact lists
- Create affiliation catalogs in categories and events, with inherited defaults and local copies
- Define ordered catalog lists using affiliations, groups, and tags
- Add a Representation registration field with catalog-based affiliation choices
- Show representation types and affiliations as separate registration-list columns
- Let focal points manage and moderate registrations representing their affiliations
- Invite existing Indico users by affiliation, group, or tag
- Invite focal points, contacts, or both from the event's default affiliation catalog
- Email representatives for all affiliations or only currently filtered affiliations
- Email representatives from a single affiliation
- Use affiliation placeholders in subject/body (including metadata paths such as `foo.bar` or `items.0`)
- Upload inline images in representative emails (embedded as CID attachments)
- Log affiliation changes and representative emails in the admin log, and catalog changes
  and registration invitations in the corresponding category or event log

### Tags And Groups

Tags are lightweight labels you can attach to affiliations and groups. They are ideal for
orthogonal or cross-cutting concepts such as "alumni", "strategic partner", or "vendor".
Affiliations and groups can have many tags, and tags do not imply hierarchy.

Groups are a way to organize affiliations into structured sets. They can carry metadata
and are commonly used for organizational or regional structure, such as departments,
faculties, or campuses. A group can have many affiliations.

### Contact Lists

Each affiliation can have multiple contact lists, such as "Administration" or "Operations",
each containing one or more email addresses. An unnamed list can hold general contacts.
Contacts do not need an Indico account.

Administrators manage these lists when editing an affiliation. Individual addresses can be
disabled without removing them and re-enabled later. Disabled addresses are excluded from
representative emails and catalog invitations, and do not count as active contacts in
dashboard filters.

Use consistent list names across affiliations to target the same role in several
organizations. The email and catalog-invitation dialogs allow selecting named contact
lists and choosing whether to include unnamed lists.

### Affiliation Catalogs

Category and event managers can create catalogs from the **Affiliations** management page.
A catalog contains ordered affiliation lists, for example "Member organizations" and
"Observers". Each list can include affiliations directly or select them through groups and
tags. These selections are combined: a tag includes both affiliations carrying that tag
and affiliations belonging to groups carrying it.

Catalogs created in a category are available to its subcategories and events. Select a
default catalog locally or inherit the default from the nearest category that defines one.
Inherited catalogs are edited in their owning category; clone one to create a local copy
that can be customized independently.

The event's effective default catalog supplies the representation types and affiliations
used by registration forms and catalog invitations. Lists can be reordered or disabled;
disabled lists are excluded from representation choices and catalog invitation recipients.

### Representation Field

Add a **Representation** field to a registration form to ask participants which organization
they represent. Participants first choose a representation type, corresponding to an enabled
list in the event's default catalog, then select an affiliation from that list. Affiliations
must be selected from the configured choices; free-text affiliations are not accepted.

For example, a participant can select "Member organizations" and then their organization.
Configure the event's default catalog and its lists before using this field. The field can
be required, and the registration list offers separate columns for its representation type
and affiliation.

### Focal Points

Focal points are Indico users assigned to represent an affiliation. Administrators can
assign multiple focal points to an affiliation, and a user can be a focal point for multiple
affiliations. Contact lists store email recipients, while focal-point assignments link
existing Indico accounts to affiliations and can grant registration-management access.

To let focal points manage registrations, add a Representation field to the registration
form and enable **Focal point management** in the form's settings. The focal point's
affiliation must belong to an enabled list in the event's default catalog.

On enabled forms, focal points can manage and moderate registrations whose Representation
field identifies one of their affiliations, and register people for those affiliations.
This access is limited to matching registrations and enabled forms. Existing event or
registration-management permissions continue to apply independently.

When emailing registrants from the registration list, **Send copy to focal points** is available on
these forms and is off by default. When enabled, each email copies the current focal points
for that registrant's representation affiliations, using the same field visibility and
catalog scope as focal point access. Manually entered CC addresses are preserved. The
option is hidden when focal point management is turned off for the form.

### Registration Invitations

The registration invitation dialog supports selecting existing Indico users through
affiliations, groups, and tags. It also supports inviting recipients from the event's
default affiliation catalog: choose focal points, contact emails, or both, and select the
contact lists to use when including contacts.

Catalog invitations combine recipients across the enabled catalog lists, remove duplicates,
and skip people already invited or actively registered. Contact emails matching an Indico
account use the account's details; other contact addresses can also receive invitations.
Event managers and users with registration-management access can view catalog recipients'
email addresses and send these invitations.

### Emailing Representatives

Administrators can email contacts for a single affiliation, all affiliations, or the current
filtered dashboard results. Choose contact lists to target specific roles, or send to all
lists. Only active, valid addresses receive emails; affiliations without matching addresses
are skipped.

Messages support affiliation placeholders in the subject and body, including the
affiliation's name, address, country, and metadata paths such as `foo.bar` or `items.0`.
The dialog provides a preview and supports inline images embedded as CID attachments.

## Changelog

### 3.3

- Initial release

### 3.3.1

- Add Affiliation Catalogs
- Add Representation field

### 3.3.2

- Add support for Focal Points
- Allow copying each registrant's affiliation focal points when emailing from the registration list
- Allow disabling affiliation contacts
- Allow inviting focal points and contacts from the event's Affiliation Catalog
- **Access control:** Event managers and users with registration-management
  access can now invite catalog contacts and view their email addresses,
  previously restricted to admins. Event managers can include any affiliation
  in their catalogs, extending this access across affiliations.
