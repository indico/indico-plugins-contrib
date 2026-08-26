// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import React from 'react';
import {Icon, Label, List, Popup} from 'semantic-ui-react';

import {Param, Translate} from 'indico/react/i18n';

import {GroupInfo, TagInfo} from '../types';

import './GroupsTagsDisplay.module.scss';

const AFFILIATION_POPUP_LIMIT = 10;

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

export function GroupsDisplay({groups}: {groups: GroupInfo[]}) {
  if (!groups.length) {
    return '-';
  }

  return (
    <div styleName="items-column-container">
      <GroupsItems groups={groups} />
    </div>
  );
}

export function TagsDisplay({tags, groupTags}: {tags: TagInfo[]; groupTags?: TagInfo[]}) {
  if (!tags.length && !groupTags?.length) {
    return '-';
  }

  return (
    <div styleName="items-column-container">
      <TagsItems tags={tags} groupTags={groupTags} />
    </div>
  );
}

export function MembersDisplay({
  groups = [],
  tags = [],
  groupTags = [],
  affiliations = [],
}: {
  groups?: GroupInfo[];
  tags?: TagInfo[];
  groupTags?: TagInfo[];
  affiliations?: {id: number; name: string}[];
}) {
  if (!groups.length && !tags.length && !groupTags.length && !affiliations.length) {
    return '-';
  }

  const shown = affiliations.slice(0, AFFILIATION_POPUP_LIMIT);
  const remaining = affiliations.length - shown.length;

  return (
    <div styleName="items-column-container">
      <GroupsItems groups={groups} />
      <TagsItems tags={tags} groupTags={groupTags} />
      {affiliations.length > 0 && (
        <Popup
          content={
            <List>
              {shown.map(affiliation => (
                <List.Item key={affiliation.id}>{affiliation.name}</List.Item>
              ))}
              {remaining > 0 && (
                <List.Item>
                  <Translate>
                    and <Param name="count" value={remaining} /> more
                  </Translate>
                </List.Item>
              )}
            </List>
          }
          trigger={
            <Label size="tiny" basic>
              <Icon name="university" />
              {affiliations.length}
            </Label>
          }
        />
      )}
    </div>
  );
}
