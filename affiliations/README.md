# Extended Affiliations Plugin

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

## Changelog

### 3.3.10

- Initial release for Indico 3.3.10
