// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import groupsURL from 'indico-url:plugin_affiliations.api_affiliation_groups';
import tagsURL from 'indico-url:plugin_affiliations.api_affiliation_tags';

import React from 'react';

import {Translate} from 'indico/react/i18n';
import {useIndicoAxios} from 'indico/react/hooks';

import FinalTagGroupInput from '../components/AffiliationTagGroupInput';
import FinalContactList from '../components/ContactListField';

function GroupsTagsSection() {
  const {data: groups} = useIndicoAxios(groupsURL({}));
  const {data: tags} = useIndicoAxios(tagsURL({}));

  return (
    <>
      <FinalTagGroupInput name="groups" label={Translate.string('Groups')} options={groups || []} />
      <FinalTagGroupInput name="tags" label={Translate.string('Tags')} options={tags || []} />
    </>
  );
}

const formSection = [
  {
    key: 'affiliations-groups-tags',
    title: Translate.string('Groups and Tags'),
    content: {
      content: <GroupsTagsSection />,
    },
  },
  {
    key: 'affiliations-contacts',
    title: Translate.string('Contacts'),
    content: {
      content: <FinalContactList name="contacts" />,
    },
  },
];

export default formSection;
