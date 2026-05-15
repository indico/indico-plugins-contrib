# Affiliation Extras Plugin

This plugin extends Indico's predefined affiliations management with groups, tags,
representative contact emails, and built-in emailing tools for affiliation representatives.

## Features

- Create, edit and delete affiliation tags (`code`, `name`, `color`)
- Create, edit and delete affiliation groups (`code`, `name`, `metadata`)
- Assign tags to groups
- Assign groups and tags to affiliations
- Add representative contact emails to affiliations
- Show groups and tags in the affiliations dashboard table
- Filter affiliations by groups, tags, and representation status (has/no contact emails)
- Email representatives for all affiliations or only currently filtered affiliations
- Email representatives from a single affiliation
- Use affiliation placeholders in subject/body (including metadata paths such as `foo.bar` or `items.0`)
- Upload inline images in representative emails (embedded as CID attachments)
- Log changes and sent emails in the admin log

### Tags And Groups

Tags are lightweight labels you can attach to affiliations and groups. They are ideal for
orthogonal or cross-cutting concepts such as "alumni", "strategic partner", or "vendor".
Affiliations and groups can have many tags, and tags do not imply hierarchy.

Groups are a way to organize affiliations into structured sets. They can carry metadata
and are commonly used for organizational or regional structure, such as departments,
faculties, or campuses. A group can have many affiliations.

In short, use tags for flexible labeling across affiliations and groups, and use groups
for structured organization and metadata of affiliations.

## Changelog

### 3.3

- Initial release
