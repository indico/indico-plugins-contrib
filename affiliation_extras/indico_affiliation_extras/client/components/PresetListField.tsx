// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import resolveAffiliationsURL from 'indico-url:plugin_affiliation_extras.api_resolve_affiliations';

import _ from 'lodash';
import React, {useState} from 'react';
import {Button, Confirm, Icon, Input, Loader, Modal, Popup} from 'semantic-ui-react';

import {FinalField} from 'indico/react/forms';
import {FinalModalForm} from 'indico/react/forms/final-form';
import {useIndicoAxios} from 'indico/react/hooks';
import {Translate} from 'indico/react/i18n';
import {SortableWrapper, useSortableItem} from 'indico/react/sortable';
import {Affiliation} from 'indico/modules/users/affiliations/types';

import {GroupInfo, TagInfo} from '../types';

import {MembersDisplay} from './GroupsTagsDisplay';
import FinalAffiliationList from './AffiliationListField';
import {AffiliationList} from './AffiliationList';

import './PresetListField.module.scss';

const DEFAULT_LIST_VALUE = {
  id: null,
  name: '',
  position: null,
  is_enabled: true,
  groups: [],
  tags: [],
  affiliations: [],
};
const DRAG_TYPE = 'affiliations-preset-list';

export interface PresetItem {
  id?: number | null;
  name: string;
  position?: number | null;
  is_enabled?: boolean;
  groups: GroupInfo[];
  tags: TagInfo[];
  affiliations: Affiliation[];
}

interface PresetListRowProps {
  value: PresetItem;
  index: number;
  targetLocator: Record<string, number>;
  onChange: (value: PresetItem) => void;
  onDelete: () => void;
  onMove: (sourceIndex: number, targetIndex: number) => void;
  canDelete: boolean;
}

function PresetListRow({
  value,
  index,
  targetLocator,
  onChange,
  onDelete,
  onMove,
  canDelete,
}: PresetListRowProps) {
  const [modalOpen, setModalOpen] = useState<string | null>(null);
  const openModal = (modal: string) => () => setModalOpen(modal);
  const closeModal = () => setModalOpen(null);
  const [handleRef, itemRef, style] = useSortableItem({
    type: DRAG_TYPE,
    id: value.id ?? `new-${index}`,
    index,
    active: true,
    separateHandle: true,
    moveItem: onMove,
    itemData: {},
    onDrop: () => null,
  });
  const triggerDelete = () =>
    value.name.trim() || value.id != null ? setModalOpen('delete') : onDelete();
  const hasMembers =
    value.groups.length > 0 || value.tags.length > 0 || value.affiliations.length > 0;
  const isEnabled = value.is_enabled;

  return (
    <tr ref={itemRef} style={{...style}} styleName={isEnabled ? null : 'row-disabled'}>
      <td ref={handleRef} style={{width: '1.5em', cursor: 'grab'}}>
        <Icon name="bars" color="grey" title={Translate.string('Drag to reorder')} />
      </td>
      <td>
        <Input
          size="small"
          placeholder={Translate.string('List name')}
          value={value.name}
          onChange={(_, {value: name}) => onChange({...value, name})}
        />
      </td>
      <td>
        <MembersDisplay
          groups={value.groups}
          tags={value.tags}
          affiliationCount={value.affiliations.length}
        />
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
          trigger={<Icon name="list" color="grey" onClick={openModal('affiliations')} link />}
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
            id={`preset-list-${value.id ?? index}`}
            onClose={closeModal}
            onSubmit={({members}) => {
              onChange({...value, ...members});
              closeModal();
            }}
            initialValues={{
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
            <FinalAffiliationList name="members" required />
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

function PresetListField({
  value: _value,
  onChange,
  onFocus,
  onBlur,
  targetLocator,
}: {
  value?: PresetItem[];
  onChange: (value: PresetItem[]) => void;
  onFocus: () => void;
  onBlur: () => void;
  targetLocator: Record<string, number>;
}) {
  const values = _value?.length ? _value : [DEFAULT_LIST_VALUE];
  const normalizePositions = (items: PresetItem[]) =>
    items.map((item, idx) => ({
      ...item,
      position: idx + 1,
    }));
  const normalizedValues = normalizePositions(values);

  const handleChange = (newValue: PresetItem[], touch: boolean = true) => {
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
                <PresetListRow
                  key={value.id ?? `new-${idx}`}
                  index={idx}
                  value={value}
                  targetLocator={targetLocator}
                  canDelete={normalizedValues.length > 1}
                  onChange={newValue =>
                    handleChange(normalizedValues.map((v, i) => (i === idx ? newValue : v)))
                  }
                  onDelete={() => handleChange(normalizedValues.filter((_, i) => i !== idx))}
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
        onClick={() => handleChange([...normalizedValues, DEFAULT_LIST_VALUE], false)}
        disabled={normalizedValues.some(v => !v.name.trim())}
        style={{marginTop: '0.5em'}}
        compact
        basic
      />
    </>
  );
}

const validatePresetLists = (value: PresetItem[]) => {
  if (value.some(({name}) => !name.trim())) {
    return Translate.string('List names must not be empty.');
  }
  if (
    value.some(
      ({groups, tags, affiliations}) => !groups.length && !tags.length && !affiliations.length
    )
  ) {
    return Translate.string('Each list must contain at least one group, tag, or affiliation.');
  }
};

export default function FinalPresetList({name, targetLocator, ...rest}) {
  return (
    <FinalField
      name={name}
      component={PresetListField}
      targetLocator={targetLocator}
      format={(v: PresetItem[]) => v}
      parse={(v: PresetItem[]) => v}
      undefinedValue={[]}
      isEqual={_.isEqual}
      validate={validatePresetLists}
      {...rest}
    />
  );
}
