// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import contactListNamesURL from 'indico-url:plugin_affiliations.api_contact_list_names';
import React, {useState} from 'react';
import {Dropdown, Table, Icon, Button, Popup, Confirm} from 'semantic-ui-react';

import {FinalField, unsortedArraysEqual} from 'indico/react/forms';
import {useIndicoAxios} from 'indico/react/hooks';
import {Translate} from 'indico/react/i18n';

import {EmailListField} from './EmailListField';

const DEFAULT_LIST_VALUE = {id: null, name: '', emails: []};

export interface ContactList {
  id?: number;
  name: string;
  emails: string[];
}

interface ContactListRowBaseProps {
  value: ContactList;
  onChange: (value: ContactList) => void;
}

interface SimpleContactListRowProps extends ContactListRowBaseProps {
  simple: true;
  nameOptions?: never;
  loadingNameOptions?: never;
  canDelete?: never;
  onDelete?: never;
}

interface AdvancedContactListRowProps extends ContactListRowBaseProps {
  simple?: false;
  nameOptions: Set<string>;
  loadingNameOptions: boolean;
  canDelete: boolean;
  onDelete: () => void;
}

function ContactListRow({
  value: {id, name, emails},
  onChange,
  onDelete,
  nameOptions,
  loadingNameOptions,
  canDelete,
  simple = false,
}: SimpleContactListRowProps | AdvancedContactListRowProps) {
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const triggerDelete = () => {
    if (emails.length > 0) {
      setConfirmingDelete(true);
    } else {
      onDelete();
    }
  };
  const emailList = (
    <EmailListField
      value={emails}
      onChange={newEmails => onChange({id, name, emails: newEmails})}
    />
  );
  if (simple) {
    return (
      <>
        <Translate as="label">Contact emails</Translate>
        {emailList}
      </>
    );
  }
  return (
    <Table.Row>
      <Table.Cell>
        <Dropdown
          placeholder={Translate.string('Type or select a name')}
          options={[...nameOptions, name]
            .filter(x => x)
            .sort((a, b) => a.localeCompare(b))
            .map(opt => ({value: opt, text: opt}))}
          value={name}
          onChange={(__, {value: newName}) => onChange({id, name: newName as string, emails})}
          loading={loadingNameOptions}
          selection
          allowAdditions
          clearable
          search
          fluid
        />
      </Table.Cell>
      <Table.Cell>{emailList}</Table.Cell>
      <Table.Cell>
        {canDelete && (
          <>
            <Popup
              content={Translate.string('Delete list')}
              on="hover"
              trigger={<Icon name="trash" onClick={triggerDelete} color="grey" link />}
            />
            <Confirm
              header={
                name
                  ? Translate.string('Deleting contact list "{name}"', {name})
                  : Translate.string('Deleting unnamed contact list')
              }
              content={Translate.string('Are you sure you want to remove this contact list?')}
              confirmButton={<Button content={Translate.string('Delete')} negative />}
              cancelButton={Translate.string('Cancel')}
              open={confirmingDelete}
              onCancel={() => setConfirmingDelete(false)}
              onConfirm={() => {
                onDelete();
                setConfirmingDelete(false);
              }}
            />
          </>
        )}
      </Table.Cell>
    </Table.Row>
  );
}

function ContactListField({
  value: _value,
  onChange,
  onFocus,
  onBlur,
}: {
  value?: ContactList[];
  onChange: (value: ContactList[]) => void;
  onFocus: () => void;
  onBlur: () => void;
}) {
  const {data: _nameOptions, loading: loadingNameOptions} = useIndicoAxios(contactListNamesURL({}));
  const values: ContactList[] = _value?.length ? _value : [DEFAULT_LIST_VALUE];
  const nameOptions = new Set((_nameOptions as string[]) ?? []).difference(
    new Set(values.map(v => v.name))
  );
  const simple = values.length === 1 && values[0].name === '';

  const handleChange = (newValue: ContactList[], touch: boolean = true) => {
    onChange(newValue);
    if (touch) {
      onFocus();
      onBlur();
    }
  };

  const field = simple ? (
    <ContactListRow value={values[0]} onChange={newValue => handleChange([newValue])} simple />
  ) : (
    <Table basic="very" style={{marginBottom: 0}} compact>
      <Table.Header>
        <Table.Row>
          <Translate as={Table.HeaderCell} width={5}>
            List name
          </Translate>
          <Translate as={Table.HeaderCell} width={10}>
            Contact emails
          </Translate>
          <Table.HeaderCell width={1} />
        </Table.Row>
      </Table.Header>
      <Table.Body>
        {values.map((value, idx) => (
          <ContactListRow
            key={idx}
            value={value}
            onChange={newValue => handleChange(values.map((v, i) => (i === idx ? newValue : v)))}
            onDelete={() => handleChange(values.filter((__, i) => i !== idx))}
            nameOptions={nameOptions}
            loadingNameOptions={loadingNameOptions}
            canDelete={values.length > 1}
          />
        ))}
      </Table.Body>
    </Table>
  );
  return (
    <>
      {field}
      <Button
        type="button"
        icon="add"
        content={Translate.string('Add list')}
        onClick={() => handleChange([...values, DEFAULT_LIST_VALUE], false)}
        disabled={!simple && !!values.find(v => !v.name && v.emails.length === 0)}
        style={{marginTop: '0.5em'}}
        compact
        basic
      />
    </>
  );
}

const validateContactLists = (value?: ContactList[]) => {
  if (!value?.length) {
    return;
  }
  const normalized = value.map(({name}) => name.trim().toLocaleLowerCase());
  if (new Set(normalized).size < value.length) {
    return Translate.string('Contact list names must be unique.');
  }
  if (value.length > 1 && value.find(({emails}) => emails.length === 0)) {
    return Translate.string('Contact lists must not be empty.');
  }
};

export default function FinalContactList({name, ...rest}) {
  return (
    <FinalField
      name={name}
      component={ContactListField}
      format={(v: ContactList[]) => v}
      parse={(v: ContactList[]) => v}
      undefinedValue={[]}
      isEqual={unsortedArraysEqual}
      validate={validateContactLists}
      {...rest}
    />
  );
}
