// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import React from 'react';

import {Translate} from 'indico/react/i18n';

import {GroupsDisplay, TagsDisplay} from '../components/GroupsTagsDisplay';

const dashboardColumns = [
  {
    key: 'affiliation-groups',
    label: Translate.string('Groups'),
    flex: 0.3,
    cellRenderer: ({rowData}) => <GroupsDisplay groups={rowData.groups} />,
  },
  {
    key: 'affiliation-tags',
    label: Translate.string('Tags'),
    flex: 0.3,
    cellRenderer: ({rowData}) => <TagsDisplay tags={rowData.tags} groupTags={rowData.group_tags} />,
  },
];

export default dashboardColumns;
