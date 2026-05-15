// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import React, {useMemo} from 'react';
import {List, Loader, Message} from 'semantic-ui-react';

import {Translate} from 'indico/react/i18n';
import {useIndicoAxios} from 'indico/react/hooks';

import {ExtendedAffiliation} from '../types';
import {getAffiliationSubheader} from '../util';

import {MembersDisplay} from './GroupsTagsDisplay';

function AffiliationItem({affiliation}: {affiliation: ExtendedAffiliation}) {
  return (
    <List.Item>
      <List.Content floated="right">
        <MembersDisplay
          groups={affiliation.groups}
          tags={affiliation.tags}
          groupTags={affiliation.group_tags}
        />
      </List.Content>
      <List.Content>
        <List.Header>{affiliation.name}</List.Header>
        {getAffiliationSubheader(affiliation) && (
          <List.Description>{getAffiliationSubheader(affiliation)}</List.Description>
        )}
      </List.Content>
    </List.Item>
  );
}

export function AffiliationList({
  resolveAffiliationsURL,
  groupIds: groups,
  tagIds: tags,
  affiliationIds: affiliations,
}: {
  resolveAffiliationsURL: string;
  groupIds: number[];
  tagIds: number[];
  affiliationIds: number[];
}) {
  const {data, loading} = useIndicoAxios({
    url: resolveAffiliationsURL,
    method: 'POST',
    data: {groups, tags, affiliations},
  });
  const resolvedAffiliations: ExtendedAffiliation[] = useMemo(
    () =>
      data?.map((a: ExtendedAffiliation) => ({
        ...a,
        groups: a.groups.filter(g => groups.includes(g.id)),
        tags: a.tags.filter(t => tags.includes(t.id)),
        group_tags: a.group_tags.filter(t => tags.includes(t.id)),
      })),
    [data]
  );

  if (loading) {
    return <Loader active inline="centered" />;
  }
  if (!resolvedAffiliations.length) {
    return <Message content={Translate.string('This list is currently empty')} info />;
  }
  return (
    <List divided relaxed>
      {resolvedAffiliations.map(affiliation => (
        <AffiliationItem key={affiliation.id} affiliation={affiliation} />
      ))}
    </List>
  );
}
