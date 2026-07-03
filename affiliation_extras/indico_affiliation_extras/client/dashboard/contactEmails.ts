// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import {ContactList} from '../components/ContactListField';
import {ExtendedAffiliation} from './types';

export const getActiveContactListEmails = ({
  emails,
  inactive_emails: inactiveEmails = [],
}: ContactList) => {
  const inactiveEmailSet = new Set(inactiveEmails);
  return emails.filter(email => !inactiveEmailSet.has(email));
};

export const hasActiveContactEmails = (contactList: ContactList) =>
  getActiveContactListEmails(contactList).length > 0;

export const getAffiliationEmails = (
  affiliation: ExtendedAffiliation,
  contactLists: string[] = [],
  includeUnnamedLists: boolean = true
) =>
  Array.from(
    new Set(
      affiliation.contact_lists
        .filter(
          ({name}) =>
            contactLists.length === 0 ||
            contactLists.includes(name) ||
            (includeUnnamedLists && name === '')
        )
        .flatMap(getActiveContactListEmails)
    )
  );

export const hasAffiliationEmails = (affiliation: ExtendedAffiliation) =>
  getAffiliationEmails(affiliation).length > 0;
