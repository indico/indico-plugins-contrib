// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import groupsURL from 'indico-url:plugin_affiliation_extras.api_affiliation_groups';
import tagsURL from 'indico-url:plugin_affiliation_extras.api_affiliation_tags';
import searchAffiliationsURL from 'indico-url:users.api_affiliations';

import _ from 'lodash';
import React, {useMemo, useState} from 'react';
import {Button, Dropdown, Header, Icon, Label, List, Message, Segment} from 'semantic-ui-react';

import {FinalField, validators} from 'indico/react/forms';
import {useIndicoAxios} from 'indico/react/hooks';
import {Translate} from 'indico/react/i18n';
import {makeAsyncDebounce} from 'indico/utils/debounce';
import {Affiliation} from 'indico/modules/users/affiliations/types';

import {GroupInfo, TagInfo} from '../types';
import {getAffiliationSubheader} from '../util';

const debounce = makeAsyncDebounce(250);

export interface AffiliationListValue {
  groups: GroupInfo[];
  tags: TagInfo[];
  affiliations: Affiliation[];
}

function AffiliationListField({
  value,
  onChange,
  onFocus,
  onBlur,
  disabled = false,
}: {
  value: AffiliationListValue;
  onChange: (value: AffiliationListValue) => void;
  onFocus?: () => void;
  onBlur?: () => void;
  disabled?: boolean;
}) {
  const {data: groups} = useIndicoAxios(groupsURL({}));
  const {data: tags} = useIndicoAxios(tagsURL({}));
  const [searchQuery, setSearchQuery] = useState('');
  const {data: fetchedAffiliationResults, loading: loadingAffiliations} = useIndicoAxios(
    searchAffiliationsURL({q: searchQuery}),
    {
      manual: !searchQuery,
    }
  );
  const affiliationResults = useMemo(
    () => fetchedAffiliationResults || [],
    [fetchedAffiliationResults]
  );

  const markTouched = () => {
    onFocus?.();
    onBlur?.();
  };

  const usedGroupIds = useMemo(() => new Set(value.groups.map(g => g.id)), [value.groups]);
  const usedTagIds = useMemo(() => new Set(value.tags.map(t => t.id)), [value.tags]);
  const usedAffiliationIds = useMemo(
    () => new Set(value.affiliations.map(a => a.id)),
    [value.affiliations]
  );

  const groupOptions = (groups || [])
    .filter(g => !usedGroupIds.has(g.id))
    .map(g => ({value: g.id, text: `${g.code}: ${g.name}`}));
  const tagOptions = (tags || [])
    .filter(t => !usedTagIds.has(t.id))
    .map(t => ({value: t.id, text: `${t.code}: ${t.name}`, color: t.color}));
  const affiliationData = searchQuery ? affiliationResults : [];
  const affiliationOptions = affiliationData
    .filter(a => !usedAffiliationIds.has(a.id))
    .map(a => ({
      value: a.id,
      text: a.name,
      content: (
        <Header style={{fontSize: 14}} content={a.name} subheader={getAffiliationSubheader(a)} />
      ),
    }));

  const handleAddGroup = (groupId: number) => {
    const group = (groups || []).find(g => g.id === groupId);
    if (!group) {
      return;
    }
    onChange({...value, groups: [...value.groups, group]});
    markTouched();
  };
  const handleAddTag = (tagId: number) => {
    const tag = (tags || []).find(t => t.id === tagId);
    if (!tag) {
      return;
    }
    onChange({...value, tags: [...value.tags, tag]});
    markTouched();
  };
  const handleAddAffiliation = (affiliationId: number) => {
    const affiliation = affiliationData.find(a => a.id === affiliationId);
    if (!affiliation) {
      return;
    }
    onChange({...value, affiliations: [...value.affiliations, affiliation]});
    markTouched();
  };

  const handleDeleteGroup = (groupId: number) => {
    onChange({...value, groups: value.groups.filter(g => g.id !== groupId)});
    markTouched();
  };
  const handleDeleteTag = (tagId: number) => {
    onChange({...value, tags: value.tags.filter(t => t.id !== tagId)});
    markTouched();
  };
  const handleDeleteAffiliation = (affiliationId: number) => {
    onChange({...value, affiliations: value.affiliations.filter(a => a.id !== affiliationId)});
    markTouched();
  };

  const handleAffiliationSearchChange = (_, {searchQuery: query}) => {
    if (!query) {
      setSearchQuery('');
      return;
    }
    debounce(() => setSearchQuery(query));
  };

  const entries = [
    ...value.groups.map(group => ({
      key: `group-${group.id}`,
      title: group.code,
      description: group.name,
      onDelete: () => handleDeleteGroup(group.id),
    })),
    ...value.tags.map(tag => ({
      key: `tag-${tag.id}`,
      title: <Label size="tiny" color={tag.color} content={tag.code} />,
      description: tag.name,
      onDelete: () => handleDeleteTag(tag.id),
    })),
    ...value.affiliations.map(affiliation => ({
      key: `affiliation-${affiliation.id}`,
      title: affiliation.name,
      description: getAffiliationSubheader(affiliation),
      onDelete: () => handleDeleteAffiliation(affiliation.id),
    })),
  ];

  return (
    <>
      <Segment attached="top">
        {entries.length > 0 ? (
          <List divided relaxed>
            {entries.map(entry => (
              <List.Item key={entry.key}>
                <List.Content floated="right">
                  <Icon
                    name="close"
                    link
                    color="grey"
                    disabled={disabled}
                    onClick={() => !disabled && entry.onDelete()}
                  />
                </List.Content>
                <List.Content>
                  <List.Header>{entry.title}</List.Header>
                  {entry.description && <List.Description>{entry.description}</List.Description>}
                </List.Content>
              </List.Item>
            ))}
          </List>
        ) : (
          <Translate>This list is currently empty</Translate>
        )}
      </Segment>
      <Button.Group attached="bottom">
        <Button icon="add" as="div" disabled />
        <AddDropdown
          text={Translate.string('Group')}
          options={groupOptions}
          disabled={disabled || groupOptions.length === 0}
          onChange={handleAddGroup}
        />
        <AddDropdown
          text={Translate.string('Tag')}
          options={tagOptions}
          disabled={disabled || tagOptions.length === 0}
          onChange={handleAddTag}
        />
        <Dropdown
          text={Translate.string('Affiliation')}
          button
          upward
          floating
          scrolling
          search
          loading={loadingAffiliations}
          disabled={disabled}
          options={affiliationOptions}
          openOnFocus={false}
          selectOnBlur={false}
          selectOnNavigation={false}
          value={null}
          onSearchChange={handleAffiliationSearchChange}
          onChange={(e, data) => handleAddAffiliation(data.value as number)}
          noResultsMessage={Translate.string('Search an affiliation')}
        />
      </Button.Group>
    </>
  );
}

function AddDropdown({text, options, disabled, onChange}) {
  return (
    <Dropdown
      text={text}
      button
      upward
      floating
      scrolling
      disabled={disabled}
      options={options}
      openOnFocus={false}
      selectOnBlur={false}
      selectOnNavigation={false}
      value={null}
      onChange={(e, data) => onChange(data.value)}
    />
  );
}

export default function FinalAffiliationList({name, ...rest}) {
  const {required, validate, ...otherProps} = rest;
  const validateMembers = (value: AffiliationListValue) => {
    if (_.every(value, _.isEmpty)) {
      return Translate.string('This field is required.');
    }
  };
  const finalValidate =
    required && required !== 'no-validator'
      ? validate
        ? validators.chain(validateMembers, validate)
        : validateMembers
      : validate;
  return (
    <FinalField
      name={name}
      component={AffiliationListField}
      isEqual={(a, b) => _.isEqual(a, b)}
      required={required ? 'no-validator' : false}
      validate={finalValidate}
      {...otherProps}
    />
  );
}
