// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import React from 'react';
import {Dropdown} from 'semantic-ui-react';

import {FinalField, unsortedArraysEqual} from 'indico/react/forms';
import {Translate} from 'indico/react/i18n';

import './AffiliationTagGroupInput.module.scss';

export interface AffiliationOption {
  id: number;
  code: string;
  name: string;
  color?: string;
}

const normalizeValue = value => {
  if (!value) {
    return [];
  }
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map(item => (typeof item === 'object' ? item.id : item));
};

function TagGroupInput({onChange, value, placeholder, options}) {
  const normalizedValue = normalizeValue(value);
  return (
    <Dropdown
      placeholder={placeholder}
      styleName="tag-group-input"
      fluid
      multiple
      search
      selection
      value={normalizedValue}
      options={options.map(({id, code, name, color}) => ({
        value: id,
        text: `${code}: ${name}`,
        key: id,
        color,
      }))}
      onChange={(_, {value: nextValue}) => onChange(nextValue)}
      closeOnChange
      renderLabel={({color, text}) => ({
        color,
        content: text,
      })}
    />
  );
}

TagGroupInput.defaultProps = {
  placeholder: Translate.string('Search by code or name...'),
};

export default function FinalTagGroupInput({name, ...rest}) {
  return (
    <FinalField
      name={name}
      component={TagGroupInput}
      format={normalizeValue}
      parse={normalizeValue}
      undefinedValue={[]}
      isEqual={unsortedArraysEqual}
      {...rest}
    />
  );
}
