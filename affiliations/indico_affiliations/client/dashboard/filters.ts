// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import {Translate} from 'indico/react/i18n';

import {ExtendedAffiliation, GroupInfo, TagInfo} from './types';

const NO_ITEMS_VALUE = '__NO_ITEMS__';

const getSafeId = (item: GroupInfo | TagInfo) => `I${item.id}`;

const buildGroupOptions = (affiliations: ExtendedAffiliation[]) => {
  const groupsById = new Map<number, GroupInfo>();
  affiliations.forEach(affiliation => {
    affiliation.groups.forEach(group => {
      if (!groupsById.has(group.id)) {
        groupsById.set(group.id, group);
      }
    });
    if (affiliation.groups.length === 0 && !groupsById.has(-1)) {
      groupsById.set(-1, {id: -1, code: Translate.string('No groups'), name: ''});
    }
  });

  return Array.from(groupsById.values())
    .sort((a, b) => a.code.localeCompare(b.code))
    .map(group => ({
      value: group.id === -1 ? NO_ITEMS_VALUE : getSafeId(group),
      text: group.code,
      exclusive: group.id === -1,
    }));
};

const buildTagOptions = (affiliations: ExtendedAffiliation[]) => {
  const tagsById = new Map<number, TagInfo>();
  affiliations.forEach(affiliation => {
    affiliation.tags.forEach(tag => {
      if (!tagsById.has(tag.id)) {
        tagsById.set(tag.id, tag);
      }
    });
    if (affiliation.tags.length === 0 && !tagsById.has(-1)) {
      tagsById.set(-1, {id: -1, code: '', name: Translate.string('No tags'), color: undefined});
    }
  });

  return Array.from(tagsById.values())
    .sort((a, b) => a.code.localeCompare(b.code))
    .map(tag => ({
      value: tag.id === -1 ? NO_ITEMS_VALUE : getSafeId(tag),
      text: tag.name,
      color: tag.color,
      exclusive: tag.id === -1,
    }));
};

const affiliationFilters = ({affiliations}: {affiliations: ExtendedAffiliation[]}) => {
  const groupOptions = buildGroupOptions(affiliations);
  const tagOptions = buildTagOptions(affiliations);

  return [
    {
      key: 'representation',
      text: Translate.string('Representation'),
      options: [
        {
          value: 'has_contact_emails',
          text: Translate.string('Has contact emails'),
          exclusive: true,
        },
        {value: 'no_contact_emails', text: Translate.string('No contact emails'), exclusive: true},
      ],
      isMatch: (entry: {affiliation: ExtendedAffiliation}, selectedValues: string[]) => {
        if (!selectedValues.length) {
          return true;
        }
        const hasContactEmails = entry.affiliation.contact_emails.length > 0;
        return (
          (selectedValues.includes('has_contact_emails') && hasContactEmails) ||
          (selectedValues.includes('no_contact_emails') && !hasContactEmails)
        );
      },
    },
    {
      key: 'groups',
      text: Translate.string('Groups'),
      options: groupOptions,
      isMatch: (entry: {affiliation: ExtendedAffiliation}, selectedValues: string[]) => {
        if (
          !selectedValues.length ||
          (selectedValues.includes(NO_ITEMS_VALUE) && entry.affiliation.groups.length === 0)
        ) {
          return true;
        }
        const groupIds = new Set(entry.affiliation.groups.map(g => getSafeId(g)));
        return selectedValues.some(value => groupIds.has(value));
      },
    },
    {
      key: 'tags',
      text: Translate.string('Tags'),
      options: tagOptions,
      isMatch: (entry: {affiliation: ExtendedAffiliation}, selectedValues: string[]) => {
        if (
          !selectedValues.length ||
          (selectedValues.includes(NO_ITEMS_VALUE) && entry.affiliation.tags.length === 0)
        ) {
          return true;
        }
        const tagIds = new Set(entry.affiliation.tags.map(t => getSafeId(t)));
        return selectedValues.some(value => tagIds.has(value));
      },
    },
  ];
};

export default affiliationFilters;
