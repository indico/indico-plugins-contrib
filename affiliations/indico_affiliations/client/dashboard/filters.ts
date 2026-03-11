// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import {Translate} from 'indico/react/i18n';

import {ExtendedAffiliation, GroupInfo, TagInfo} from './types';

const NO_ITEMS_VALUE = '__NO_ITEMS__';
const UNNAMED_LIST_VALUE = '__UNNAMED_LIST__';
const LIST_FILTER_PREFIX = 'contact_list:';
const LIST_FILTER_ABSENT_PREFIX = 'contact_list_absent:';

const getSafeId = (item: GroupInfo | TagInfo) => `I${item.id}`;
const getContactListFilterValue = (name: string) =>
  `${LIST_FILTER_PREFIX}${name || UNNAMED_LIST_VALUE}`;
const getContactListAbsentFilterValue = (name: string) =>
  `${LIST_FILTER_ABSENT_PREFIX}${name || UNNAMED_LIST_VALUE}`;

const BASE_REPRESENTATION_OPTIONS = [
  {
    value: 'has_contact_emails',
    text: Translate.string('Has contact emails'),
    exclusive: true,
  },
  {
    value: 'no_contact_emails',
    text: Translate.string('No contact emails'),
    exclusive: true,
  },
];

const buildContactsOptions = (affiliations: ExtendedAffiliation[]) => {
  const listNamesByKey = new Map<string, string>();
  let hasNamedList = false;
  let hasUnnamedList = false;
  affiliations.forEach(affiliation => {
    affiliation.contacts.forEach(contact => {
      const normalizedName = contact.name.trim();
      if (!normalizedName) {
        hasUnnamedList = true;
        return;
      }
      hasNamedList = true;
      const key = normalizedName.toLocaleLowerCase();
      if (!listNamesByKey.has(key)) {
        listNamesByKey.set(key, normalizedName);
      }
    });
  });

  if (!hasNamedList) {
    return BASE_REPRESENTATION_OPTIONS;
  }

  const listOptions = Array.from(listNamesByKey.values())
    .sort((a, b) => a.localeCompare(b))
    .flatMap(name => [
      {
        value: getContactListFilterValue(name),
        text: Translate.string('Has contacts in "{name}"', {name}),
      },
      {
        value: getContactListAbsentFilterValue(name),
        text: Translate.string('No contacts in "{name}"', {name}),
      },
    ]);
  if (hasUnnamedList) {
    listOptions.push({
      value: getContactListFilterValue(''),
      text: Translate.string('Has contacts in unnamed list'),
    });
    listOptions.push({
      value: getContactListAbsentFilterValue(''),
      text: Translate.string('No contacts in unnamed list'),
    });
  }

  return [...BASE_REPRESENTATION_OPTIONS, ...listOptions];
};

const buildGroupOptions = (affiliations: ExtendedAffiliation[]) => {
  const groupsById = new Map<number, GroupInfo>();
  affiliations.forEach(affiliation => {
    affiliation.groups.forEach(group => {
      if (!groupsById.has(group.id)) {
        groupsById.set(group.id, group);
      }
    });
    if (affiliation.groups.length === 0 && !groupsById.has(-1)) {
      groupsById.set(-1, {
        id: -1,
        code: Translate.string('No groups'),
        name: '',
      });
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
    const tags = [...affiliation.tags, ...affiliation.group_tags];
    tags.forEach(tag => {
      if (!tagsById.has(tag.id)) {
        tagsById.set(tag.id, tag);
      }
    });
    if (tags.length === 0 && !tagsById.has(-1)) {
      tagsById.set(-1, {
        id: -1,
        code: '',
        name: Translate.string('No tags'),
        color: undefined,
      });
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
  const contactsOptions = buildContactsOptions(affiliations);
  const groupOptions = buildGroupOptions(affiliations);
  const tagOptions = buildTagOptions(affiliations);

  return [
    {
      key: 'contacts',
      text: Translate.string('Contacts'),
      options: contactsOptions,
      isMatch: (entry: {affiliation: ExtendedAffiliation}, selectedValues: string[]) => {
        if (!selectedValues.length) {
          return true;
        }
        const hasContactEmails = entry.affiliation.contacts.length > 0;
        const selectedListValues = selectedValues.filter(value =>
          value.startsWith(LIST_FILTER_PREFIX)
        );
        const selectedAbsentListValues = selectedValues.filter(value =>
          value.startsWith(LIST_FILTER_ABSENT_PREFIX)
        );
        const listNameValues = new Set(
          entry.affiliation.contacts.map(contact => getContactListFilterValue(contact.name.trim()))
        );
        return (
          (selectedValues.includes('has_contact_emails') && hasContactEmails) ||
          (selectedValues.includes('no_contact_emails') && !hasContactEmails) ||
          selectedListValues.some(value => listNameValues.has(value)) ||
          selectedAbsentListValues.some(
            value =>
              !listNameValues.has(value.replace(LIST_FILTER_ABSENT_PREFIX, LIST_FILTER_PREFIX))
          )
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
        const tags = [...entry.affiliation.tags, ...entry.affiliation.group_tags];
        if (
          !selectedValues.length ||
          (selectedValues.includes(NO_ITEMS_VALUE) && tags.length === 0)
        ) {
          return true;
        }
        const tagIds = new Set(tags.map(t => getSafeId(t)));
        return selectedValues.some(value => tagIds.has(value));
      },
    },
  ];
};

export default affiliationFilters;
