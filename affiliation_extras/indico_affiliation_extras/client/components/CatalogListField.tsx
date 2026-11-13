// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import affiliationGroupsURL from 'indico-url:plugin_affiliation_extras.api_affiliation_catalog_groups';
import searchAffiliationsURL from 'indico-url:plugin_affiliation_extras.api_affiliation_catalog_search';
import affiliationTagsURL from 'indico-url:plugin_affiliation_extras.api_affiliation_catalog_tags';
import resolveAffiliationsURL from 'indico-url:plugin_affiliation_extras.api_resolve_affiliations';

import _ from 'lodash';
import React, {useMemo, useState} from 'react';
import {Field} from 'react-final-form';
import {Button, Confirm, Icon, Input, Modal, Popup} from 'semantic-ui-react';

import {Affiliation} from 'indico/modules/users/affiliations/types';
import {FinalCheckbox, FinalField} from 'indico/react/forms';
import {FinalModalForm} from 'indico/react/forms/final-form';
import {Translate} from 'indico/react/i18n';
import {SortableWrapper, useSortableItem} from 'indico/react/sortable';

import {GroupInfo, TagInfo} from '../types';

import {AffiliationList} from './AffiliationList';
import FinalAffiliationList from './AffiliationListField';
import {MembersDisplay} from './GroupsTagsDisplay';

import './CatalogListField.module.scss';

const DRAG_TYPE = 'affiliations-catalog-list';

export interface CatalogItem {
  id: number | null;
  // client-only stable id for unsaved rows (used as React key / drag id; dropped server-side)
  _frontendId?: string;
  name: string;
  position: number | null;
  is_enabled: boolean;
  affiliation_mode: 'predefined' | 'custom';
  groups: GroupInfo[];
  tags: TagInfo[];
  affiliations: Affiliation[];
}

const makeDefaultList = (): CatalogItem => ({
  id: null,
  _frontendId: _.uniqueId('list-'),
  name: '',
  position: null,
  is_enabled: true,
  affiliation_mode: 'predefined',
  groups: [],
  tags: [],
  affiliations: [],
});

interface CatalogListRowProps {
  value: CatalogItem;
  index: number;
  targetLocator: Record<string, number>;
  groupsURL: string;
  tagsURL: string;
  searchURL: string;
  onChange: (value: CatalogItem) => void;
  onDelete: () => void;
  onMove: (sourceIndex: number, targetIndex: number) => void;
  canDelete: boolean;
}

function CatalogListRow({
  value,
  index,
  targetLocator,
  groupsURL,
  tagsURL,
  searchURL,
  onChange,
  onDelete,
  onMove,
  canDelete,
}: CatalogListRowProps) {
  const [modalOpen, setModalOpen] = useState<string | null>(null);
  const openModal = (modal: string) => () => setModalOpen(modal);
  const closeModal = () => setModalOpen(null);
  const [handleRef, itemRef, style] = useSortableItem({
    type: DRAG_TYPE,
    id: value.id ?? value._frontendId,
    index,
    active: true,
    separateHandle: true,
    moveItem: onMove,
    itemData: {},
    onDrop: () => null,
  });
  const triggerDelete = () =>
    value.name.trim() || value.id !== null ? setModalOpen('delete') : onDelete();
  const isCustom = value.affiliation_mode === 'custom';
  const hasMembers =
    isCustom || value.groups.length > 0 || value.tags.length > 0 || value.affiliations.length > 0;
  const isEnabled = value.is_enabled;

  return (
    <tr ref={itemRef} style={{...style}} styleName={isEnabled ? null : 'row-disabled'}>
      <td ref={handleRef} styleName="drag-handle">
        <Icon name="bars" color="grey" title={Translate.string('Drag to reorder')} />
      </td>
      <td>
        <Input
          size="small"
          placeholder={Translate.string('List name')}
          value={value.name}
          onChange={(__, {value: name}) => onChange({...value, name})}
        />
      </td>
      <td>
        {isCustom ? (
          <Translate as="span" className="text-not-important">
            Custom affiliations
          </Translate>
        ) : (
          <MembersDisplay
            groups={value.groups}
            tags={value.tags}
            affiliations={value.affiliations}
          />
        )}
      </td>
      <td style={{whiteSpace: 'nowrap', width: '1px'}}>
        <Popup
          content={Translate.string('Edit members')}
          on="hover"
          trigger={
            <Icon.Group onClick={openModal('edit')} style={{cursor: 'pointer'}}>
              <Icon name="edit" color="grey" />
              {!hasMembers && <Icon name="circle" color="red" corner="top right" />}
            </Icon.Group>
          }
        />
        <Popup
          content={Translate.string('See affiliations')}
          on="hover"
          trigger={
            <Icon
              name="list"
              color="grey"
              onClick={openModal('affiliations')}
              disabled={isCustom}
              link
            />
          }
        />
        <Popup
          content={Translate.string('Remove list')}
          on="hover"
          trigger={
            <Icon
              name="trash"
              color="grey"
              onClick={canDelete ? triggerDelete : undefined}
              disabled={!canDelete}
              link={canDelete}
            />
          }
        />
        <Confirm
          header={
            value.name
              ? Translate.string('Removing list "{name}"', {name: value.name})
              : Translate.string('Removing list')
          }
          content={Translate.string('Are you sure you want to remove this list?')}
          confirmButton={<Button content={Translate.string('Remove')} negative />}
          cancelButton={Translate.string('Cancel')}
          open={modalOpen === 'delete'}
          onCancel={closeModal}
          onConfirm={() => {
            onDelete();
            closeModal();
          }}
        />
        <Popup
          content={isEnabled ? Translate.string('Disable list') : Translate.string('Enable list')}
          on="hover"
          trigger={
            <Icon
              name={isEnabled ? 'ban' : 'check'}
              color="grey"
              onClick={() => onChange({...value, is_enabled: !isEnabled})}
              link
            />
          }
        />
        {modalOpen === 'edit' && (
          <FinalModalForm
            id={`catalog-list-${value.id ?? value._frontendId}`}
            onClose={closeModal}
            onSubmit={({members, affiliation_mode: affiliationMode}) => {
              onChange({...value, ...members, affiliation_mode: affiliationMode});
              closeModal();
            }}
            validate={({members, affiliation_mode: affiliationMode}) =>
              affiliationMode !== 'custom' && _.every(members, _.isEmpty)
                ? {members: Translate.string('This field is required.')}
                : undefined
            }
            initialValues={{
              affiliation_mode: value.affiliation_mode,
              members: {
                groups: value.groups,
                tags: value.tags,
                affiliations: value.affiliations,
              },
            }}
            header={
              value.name
                ? Translate.string('Edit members of "{name}"', {name: value.name})
                : Translate.string('Edit members')
            }
            submitLabel={Translate.string('Apply')}
          >
            <Field name="affiliation_mode" subscription={{value: true}}>
              {({input: {value: mode}}) => (
                <FinalAffiliationList
                  name="members"
                  groupsURL={groupsURL}
                  tagsURL={tagsURL}
                  searchURL={searchURL}
                  disabled={mode === 'custom'}
                  required={mode !== 'custom' ? 'no-validator' : false}
                />
              )}
            </Field>
            <FinalCheckbox
              name="affiliation_mode"
              label={Translate.string('Use custom affiliations')}
              description={Translate.string(
                'Ask participants to enter an affiliation name instead of selecting a catalog affiliation.'
              )}
              format={mode => mode === 'custom'}
              parse={checked => (checked ? 'custom' : 'predefined')}
              showAsToggle
            />
          </FinalModalForm>
        )}
        {modalOpen === 'affiliations' && (
          <Modal onClose={closeModal} size="small" open>
            <Modal.Header>
              {value.name
                ? Translate.string('Affiliations in "{name}"', {name: value.name})
                : Translate.string('Affiliations')}
            </Modal.Header>
            <Modal.Content>
              <AffiliationList
                resolveAffiliationsURL={resolveAffiliationsURL(targetLocator)}
                groupIds={value.groups.map(group => group.id)}
                tagIds={value.tags.map(tag => tag.id)}
                affiliationIds={value.affiliations.map(affiliation => affiliation.id)}
              />
            </Modal.Content>
            <Modal.Actions>
              <Button onClick={closeModal}>
                <Translate>Close</Translate>
              </Button>
            </Modal.Actions>
          </Modal>
        )}
      </td>
    </tr>
  );
}

function CatalogListField({
  value: _value,
  onChange,
  onFocus,
  onBlur,
  targetLocator,
}: {
  value?: CatalogItem[];
  onChange: (value: CatalogItem[]) => void;
  onFocus: () => void;
  onBlur: () => void;
  targetLocator: Record<string, number>;
}) {
  const emptyDefault = useMemo(makeDefaultList, []);
  const values = _value?.length ? _value : [emptyDefault];
  const normalizePositions = (items: CatalogItem[]) =>
    items.map((item, idx) => ({
      ...item,
      position: idx + 1,
    }));
  const normalizedValues = normalizePositions(values);

  const handleChange = (newValue: CatalogItem[], touch = true) => {
    onChange(normalizePositions(newValue));
    if (touch) {
      onFocus();
      onBlur();
    }
  };

  const handleMove = (sourceIndex: number, targetIndex: number) => {
    const newValue = [...normalizedValues];
    const [sourceItem] = newValue.splice(sourceIndex, 1);
    newValue.splice(targetIndex, 0, sourceItem);
    handleChange(newValue);
  };

  return (
    <>
      {normalizedValues.length ? (
        <SortableWrapper accept={DRAG_TYPE}>
          <table className="i-table-widget">
            <colgroup>
              <col styleName="col-drag" />
              <col styleName="col-name" />
              <col styleName="col-members" />
              <col styleName="col-actions" />
            </colgroup>
            <thead>
              <tr>
                <th />
                <th>
                  <Translate>Name</Translate>
                </th>
                <th>
                  <Translate>Members</Translate>
                </th>
                <th />
              </tr>
            </thead>
            <tbody>
              {normalizedValues.map((value, idx) => (
                <CatalogListRow
                  key={value.id ?? value._frontendId}
                  index={idx}
                  value={value}
                  targetLocator={targetLocator}
                  groupsURL={affiliationGroupsURL(targetLocator)}
                  tagsURL={affiliationTagsURL(targetLocator)}
                  searchURL={searchAffiliationsURL(targetLocator)}
                  canDelete={normalizedValues.length > 1}
                  onChange={newValue =>
                    handleChange(normalizedValues.map((v, i) => (i === idx ? newValue : v)))
                  }
                  onDelete={() => handleChange(normalizedValues.filter((__, i) => i !== idx))}
                  onMove={handleMove}
                />
              ))}
            </tbody>
          </table>
        </SortableWrapper>
      ) : (
        <div className="italic text-not-important">
          <Translate>No lists</Translate>
        </div>
      )}
      <Button
        type="button"
        icon="add"
        content={Translate.string('Add list')}
        onClick={() => handleChange([...normalizedValues, makeDefaultList()], false)}
        disabled={normalizedValues.some(v => !v.name.trim())}
        style={{marginTop: '0.5em'}}
        compact
        basic
      />
    </>
  );
}

const validateCatalogLists = (value: CatalogItem[]) => {
  if (value.some(({name}) => !name.trim())) {
    return Translate.string('List names must not be empty.');
  }
  const names = value.map(({name}) => name.trim().toLowerCase());
  if (new Set(names).size !== names.length) {
    return Translate.string('List names must be unique.');
  }
  if (
    value.some(
      ({affiliation_mode: affiliationMode, groups, tags, affiliations}) =>
        affiliationMode !== 'custom' && !groups.length && !tags.length && !affiliations.length
    )
  ) {
    return Translate.string('Each list must contain at least one group, tag, or affiliation.');
  }
};

export default function FinalCatalogList({name, targetLocator, ...rest}) {
  return (
    <FinalField
      name={name}
      component={CatalogListField}
      targetLocator={targetLocator}
      format={(v: CatalogItem[]) => v}
      parse={(v: CatalogItem[]) => v}
      undefinedValue={[]}
      isEqual={_.isEqual}
      validate={validateCatalogLists}
      {...rest}
    />
  );
}
