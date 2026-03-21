// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import React from 'react';
import {Icon, Label, Popup} from 'semantic-ui-react';

import {Translate} from 'indico/react/i18n';

import {GroupInfo, TagInfo} from '../dashboard/types';

import './GroupsTagsDisplay.module.scss';

function GroupsItems({groups}: {groups: GroupInfo[]}) {
  return (
    <>
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
    </>
  );
}

function TagsItems({tags, groupTags}: {tags: TagInfo[]; groupTags?: TagInfo[]}) {
  return (
    <>
      {tags.map(tag => (
        <Popup
          key={`tag-${tag.id}`}
          content={tag.name}
          trigger={<Label size="tiny" color={tag.color} content={tag.code} />}
        />
      ))}
      {(groupTags || []).map(tag => (
        <Popup
          key={`group-tag-${tag.id}`}
          content={Translate.string('{tagName} (Inherited)', {tagName: tag.name})}
          trigger={<Label size="tiny" color={tag.color} content={tag.code} basic />}
        />
      ))}
    </>
  );
}

export function GroupsDisplay({
  groups,
  emptyLabel = '-',
}: {
  groups: GroupInfo[];
  emptyLabel?: string;
}) {
  if (!groups.length) {
    return emptyLabel;
  }

  return (
    <div styleName="items-column-container">
      <GroupsItems groups={groups} />
    </div>
  );
}

export function TagsDisplay({
  tags,
  groupTags,
  emptyLabel = '-',
}: {
  tags: TagInfo[];
  groupTags?: TagInfo[];
  emptyLabel?: string;
}) {
  if (!tags.length && !groupTags?.length) {
    return emptyLabel;
  }

  return (
    <div styleName="items-column-container">
      <TagsItems tags={tags} groupTags={groupTags} />
    </div>
  );
}

export function MembersDisplay({
  groups,
  tags,
  groupTags,
  affiliationCount = 0,
  emptyLabel = '-',
}: {
  groups: GroupInfo[];
  tags: TagInfo[];
  groupTags?: TagInfo[];
  affiliationCount?: number;
  emptyLabel?: string;
}) {
  if (!groups.length && !tags.length && !groupTags?.length && affiliationCount === 0) {
    return emptyLabel;
  }

  return (
    <div styleName="items-column-container">
      <GroupsItems groups={groups} />
      <TagsItems tags={tags} groupTags={groupTags} />
      {affiliationCount > 0 && (
        <Popup
          content={Translate.string('Affiliations')}
          trigger={
            <Label size="tiny" basic>
              <Icon name="university" />
              {affiliationCount}
            </Label>
          }
        />
      )}
    </div>
  );
}
