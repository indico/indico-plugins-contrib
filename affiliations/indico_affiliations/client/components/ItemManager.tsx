// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import React, {useReducer} from 'react';
import ReactDOM from 'react-dom';
import {Button, Icon, Loader, Message, Segment, Popup} from 'semantic-ui-react';

import {RequestConfirmDelete} from 'indico/react/components';
import {getChangedValues, handleSubmitError} from 'indico/react/forms';
import ItemModal from './ItemModal';

import './ItemManager.module.scss';

const initialState = {
  item: null,
  operation: null,
};

function itemsReducer(state, action) {
  switch (action.type) {
    case 'ADD_ITEM':
      return {operation: 'add', item: null};
    case 'EDIT_ITEM':
      return {operation: 'edit', item: action.item};
    case 'DELETE_ITEM':
      return {operation: 'delete', item: action.item};
    case 'CLEAR':
      return {...initialState};
    default:
      return state;
  }
}

export interface ItemBase {
  id: number;
}

interface ItemManagerProps<T extends ItemBase> {
  items: T[];
  loading?: boolean;
  onCreateItem: (formData: Partial<T>) => Promise<void>;
  onEditItem: (itemId: number, itemData: Partial<T>) => Promise<void>;
  onDeleteItem: (itemId: number) => Promise<void>;
  editItemLabel: string;
  deleteItemLabel: string;
  addItemLabel: string;
  createItemLabel: string;
  noItemsMessage: string;
  canEditItem?: (item: T) => boolean;
  editDisabledReason?: string;
  confirmDeleteText: (item: T) => React.ReactNode;
  renderItem: (item: T) => React.ReactNode;
  formFields: React.ReactNode;
  initialValues: Partial<T>;
  addButtonContainer?: Element;
}

export default function ItemManager<T extends ItemBase>({
  items,
  loading = false,
  onCreateItem,
  onEditItem,
  onDeleteItem,
  editItemLabel,
  deleteItemLabel,
  addItemLabel,
  createItemLabel,
  noItemsMessage,
  canEditItem = () => true,
  editDisabledReason = '',
  confirmDeleteText,
  renderItem,
  formFields,
  initialValues,
  addButtonContainer = null,
}: ItemManagerProps<T>) {
  const [state, dispatch] = useReducer(itemsReducer, initialState);

  const createItem = async formData => {
    try {
      await onCreateItem(formData);
    } catch (e) {
      return handleSubmitError(e);
    }
  };

  const editItem = async (itemId, itemData) => {
    try {
      await onEditItem(itemId, itemData);
    } catch (e) {
      return handleSubmitError(e);
    }
  };

  if (loading) {
    return <Loader inline="centered" active />;
  } else if (!items) {
    return null;
  }

  const {operation, item: currentItem} = state;
  const addButton = (
    <Button
      onClick={() => dispatch({type: 'ADD_ITEM'})}
      disabled={!!operation}
      floated={addButtonContainer ? undefined : 'right'}
      icon="plus"
      content={addItemLabel}
      primary
    />
  );
  const addButtonNode = addButtonContainer
    ? ReactDOM.createPortal(addButton, addButtonContainer)
    : addButton;
  return (
    <div styleName="items-container">
      {items.map(item => (
        <Segment key={item.id} styleName="item-segment">
          {renderItem(item)}
          <div styleName="item-actions">
            <Popup
              on="hover"
              position="right center"
              disabled={canEditItem(item) || !editDisabledReason}
              trigger={
                <span>
                  <Icon
                    name="pencil"
                    color="grey"
                    size="small"
                    title={editItemLabel}
                    onClick={() => dispatch({type: 'EDIT_ITEM', item})}
                    disabled={!canEditItem(item)}
                    circular
                    inverted
                  />{' '}
                  <Icon
                    name="remove"
                    color="red"
                    size="small"
                    title={deleteItemLabel}
                    onClick={() => dispatch({type: 'DELETE_ITEM', item})}
                    disabled={!canEditItem(item)}
                    circular
                    inverted
                  />
                </span>
              }
              content={editDisabledReason}
            />
          </div>
        </Segment>
      ))}
      {items.length === 0 && <Message info content={noItemsMessage} />}
      {addButtonNode}
      {['add', 'edit'].includes(operation) && (
        <ItemModal
          header={operation === 'edit' ? editItemLabel : createItemLabel}
          onSubmit={async (formData, form) => {
            if (operation === 'edit') {
              return await editItem(currentItem.id, getChangedValues(formData, form));
            } else {
              return await createItem(formData);
            }
          }}
          initialValues={currentItem || initialValues}
          onClose={() => dispatch({type: 'CLEAR'})}
        >
          {formFields}
        </ItemModal>
      )}
      <RequestConfirmDelete
        onClose={() => dispatch({type: 'CLEAR'})}
        requestFunc={() => onDeleteItem(currentItem.id)}
        open={operation === 'delete'}
      >
        {currentItem && confirmDeleteText(currentItem)}
      </RequestConfirmDelete>
    </div>
  );
}
