// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import editTagURL from 'indico-url:plugin_affiliations.api_affiliation_tag';
import tagsURL from 'indico-url:plugin_affiliations.api_affiliation_tags';

import React from 'react';
import {Label, SemanticCOLORS} from 'semantic-ui-react';

import {Param, Translate} from 'indico/react/i18n';
import {FinalDropdown, FinalInput} from 'indico/react/forms';
import indicoAxios, {handleAxiosError} from 'indico/utils/axios';
import {SUIPalette} from 'indico/utils/palette';

import ItemManager, {ItemBase} from '../components/ItemManager';
import {useIndicoAxios} from 'indico/react/hooks';

interface TagFormData {
  code: string;
  name: string;
  color: SemanticCOLORS;
}

type TagItem = ItemBase & TagFormData;

const renderColorLabel = (colorName: SemanticCOLORS) => (
  <div style={{display: 'flex', alignItems: 'center'}}>
    <Label color={colorName} /> <span style={{marginLeft: 10}}>{SUIPalette[colorName]}</span>
  </div>
);

const availableColors = Object.keys(SUIPalette).map((colorName: SemanticCOLORS) => ({
  text: renderColorLabel(colorName),
  value: colorName,
}));

export default function TagManager({addButtonContainer}: {addButtonContainer?: Element}) {
  const {data, loading, reFetch, lastData} = useIndicoAxios(tagsURL({}));

  const handleCreateTag = async (formData: TagFormData) => {
    await indicoAxios.post(tagsURL({}), formData);
    reFetch();
  };

  const handleEditTag = async (tagId: number, tagData: TagFormData) => {
    await indicoAxios.patch(editTagURL({tag_id: tagId}), tagData);
    reFetch();
  };

  const handleDeleteTag = async (tagId: number) => {
    try {
      await indicoAxios.delete(editTagURL({tag_id: tagId}));
      reFetch();
    } catch (e) {
      handleAxiosError(e);
    }
  };

  const tags = data || lastData || [];
  return (
    <ItemManager<TagItem>
      items={tags}
      loading={loading}
      onCreateItem={handleCreateTag}
      onEditItem={handleEditTag}
      onDeleteItem={handleDeleteTag}
      editItemLabel={Translate.string('Edit tag')}
      deleteItemLabel={Translate.string('Delete tag')}
      addItemLabel={Translate.string('Add new tag')}
      createItemLabel={Translate.string('Create a new tag')}
      noItemsMessage={Translate.string('No tags have been created yet.')}
      editDisabledReason={''}
      confirmDeleteText={item => (
        <Translate>
          Are you sure you want to delete the tag{' '}
          <Param name="tag" value={item.name} wrapper={<strong />} />?
        </Translate>
      )}
      renderItem={item => (
        <div>
          <Label color={item.color} content={item.code} />
          <strong style={{marginLeft: '4px'}}>{item.name}</strong>
        </div>
      )}
      formFields={
        <>
          <FinalInput name="code" label={Translate.string('Code')} required autoFocus />
          <FinalInput name="name" label={Translate.string('Name')} required />
          <FinalDropdown
            name="color"
            label={Translate.string('Color')}
            options={availableColors}
            search={null}
            selection
            required
          />
        </>
      }
      initialValues={{code: '', name: '', color: null}}
      addButtonContainer={addButtonContainer}
    />
  );
}
