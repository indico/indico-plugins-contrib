// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import editGroupURL from 'indico-url:plugin_affiliations.api_affiliation_group';
import groupsURL from 'indico-url:plugin_affiliations.api_affiliation_groups';
import tagsURL from 'indico-url:plugin_affiliations.api_affiliation_tags';

import React from 'react';
import {FinalInput, FinalTextArea} from 'indico/react/forms';

import {Param, Translate} from 'indico/react/i18n';

import ItemManager, {ItemBase} from '../components/ItemManager';
import indicoAxios, {handleAxiosError} from 'indico/utils/axios';
import {useIndicoAxios} from 'indico/react/hooks';

import FinalTagGroupInput from '../components/AffiliationTagGroupInput';

interface GroupFormData {
  code: string;
  name: string;
  tags: number[];
  meta: unknown;
}

interface GroupItem extends ItemBase, GroupFormData {
  system: boolean;
}

const formatMetaValue = (value: unknown) =>
  typeof value === 'string' ? value : JSON.stringify(value, null, 2);

const parseMetaValue = (value: string) => {
  if (!value) {
    return {};
  }
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
};

const validateMetaValue = (value: unknown) => {
  if (!value || Array.isArray(value)) {
    return Translate.string('Enter a JSON object');
  }
  if (typeof value === 'string') {
    try {
      JSON.parse(value);
    } catch (error) {
      return error.message;
    }
  }
};

export default function GroupManager({addButtonContainer}: {addButtonContainer?: Element}) {
  const {data, loading, reFetch, lastData} = useIndicoAxios(groupsURL({}));
  const {data: tags} = useIndicoAxios(tagsURL({}));

  const handleCreateGroup = async (formData: GroupFormData) => {
    await indicoAxios.post(groupsURL({}), formData);
    reFetch();
  };

  const handleEditGroup = async (groupId: number, groupData: GroupFormData) => {
    await indicoAxios.patch(editGroupURL({group_id: groupId}), groupData);
    reFetch();
  };

  const handleDeleteGroup = async (groupId: number) => {
    try {
      await indicoAxios.delete(editGroupURL({group_id: groupId}));
      reFetch();
    } catch (e) {
      handleAxiosError(e);
    }
  };

  const groups = data || lastData || [];
  return (
    <ItemManager<GroupItem>
      items={groups}
      loading={loading}
      onCreateItem={handleCreateGroup}
      onEditItem={handleEditGroup}
      onDeleteItem={handleDeleteGroup}
      editItemLabel={Translate.string('Edit group')}
      deleteItemLabel={Translate.string('Delete group')}
      addItemLabel={Translate.string('Add new group')}
      createItemLabel={Translate.string('Create a new group')}
      noItemsMessage={Translate.string('There are no groups defined')}
      confirmDeleteText={item => (
        <Translate>
          Are you sure you want to delete the group{' '}
          <Param name="group" value={item.name} wrapper={<strong />} />?
        </Translate>
      )}
      renderItem={group => (
        <strong>
          {group.code}: {group.name}
        </strong>
      )}
      formFields={group => (
        <>
          <FinalInput
            name="code"
            label={Translate.string('Code')}
            disabled={!!group?.system}
            required
            autoFocus
          />
          <FinalInput
            name="name"
            label={Translate.string('Name')}
            disabled={!!group?.system}
            required
          />
          <FinalTagGroupInput name="tags" label={Translate.string('Tags')} options={tags || []} />
          <FinalTextArea
            name="meta"
            label={Translate.string('Metadata (JSON)')}
            placeholder={Translate.string('Enter a JSON object')}
            className="mono"
            format={formatMetaValue}
            formatOnBlur={false}
            parse={parseMetaValue}
            validate={validateMetaValue}
            rows={4}
            disabled={!!group?.system}
          />
        </>
      )}
      canEditItem={group => !group.system}
      initialValues={{code: '', name: '', meta: {}}}
      addButtonContainer={addButtonContainer}
    />
  );
}
