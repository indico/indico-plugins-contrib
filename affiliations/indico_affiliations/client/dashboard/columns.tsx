// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import React from 'react';
import {Label, Popup} from 'semantic-ui-react';

import {Translate} from 'indico/react/i18n';

import {GroupInfo, TagInfo} from './types';

import './columns.module.scss';

function AffiliationGroupsCell({groups}: {groups: GroupInfo[]}) {
  if (!groups.length) {
    return '-';
  }

  return (
    <div styleName="items-column-container">
      {groups.map((group, idx) => (
        <Popup
          key={group.id}
          content={group.name}
          trigger={
            <span styleName="code">
              {group.code}
              {idx < groups.length - 1 && ','}
            </span>
          }
        />
      ))}
    </div>
  );
}

function AffiliationTagsCell({tags}: {tags: TagInfo[]}) {
  if (!tags.length) {
    return '-';
  }

  return (
    <div styleName="items-column-container">
      {tags.map(tag => (
        <Popup
          key={tag.id}
          content={tag.name}
          trigger={<Label size="tiny" color={tag.color} content={tag.code} />}
        />
      ))}
    </div>
  );
}

const dashboardColumns = [
  {
    key: 'affiliation-groups',
    label: Translate.string('Groups'),
    cellRenderer: ({rowData}) => <AffiliationGroupsCell groups={rowData.groups} />,
  },
  {
    key: 'affiliation-tags',
    label: Translate.string('Tags'),
    cellRenderer: ({rowData}) => <AffiliationTagsCell tags={rowData.tags} />,
  },
];

export default dashboardColumns;
