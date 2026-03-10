// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

// XXX: delete this file once EmailListField is exportable

import _ from 'lodash';
import PropTypes from 'prop-types';
import React, {useState} from 'react';
import {Dropdown} from 'semantic-ui-react';

import {Translate} from 'indico/react/i18n';

const isValid = value => /^\S+@\S+\.\S+$/.test(value);

/**
 * A field that lets the user enter email addresses
 */
export function EmailListField({value, disabled, onChange, onFocus, onBlur}) {
  const [searchQuery, setSearchQuery] = useState('');
  const options = value.filter(isValid).map(x => ({text: x, value: x}));

  const setValue = newValue => {
    newValue = _.uniq(newValue.filter(isValid));
    onChange(newValue);
    onFocus();
    onBlur();
  };

  const handleChange = (e, {value: newValue}) => {
    if (newValue.length && newValue[newValue.length - 1] === searchQuery) {
      setSearchQuery('');
    }
    setValue(newValue);
  };

  const handleSearchChange = (e, {searchQuery: newSearchQuery}) => {
    if (/[,;]/.test(newSearchQuery)) {
      const addresses = newSearchQuery.replace(/\s/g, '').split(/[,;]+/);
      setValue([...value, ...addresses.filter(isValid)]);
      setSearchQuery(addresses.filter(a => a && !isValid(a)).join(', '));
    } else {
      setSearchQuery(newSearchQuery);
    }
  };

  const handleBlur = () => {
    if (isValid(searchQuery)) {
      setValue([...value, searchQuery]);
      setSearchQuery('');
    }
  };

  return (
    <Dropdown
      options={options}
      value={value}
      searchQuery={searchQuery}
      disabled={disabled}
      searchInput={{onFocus, onBlur, type: 'email'}}
      search
      selection
      multiple
      allowAdditions
      fluid
      open={isValid(searchQuery)}
      placeholder={Translate.string('Please enter an email address')}
      additionLabel={Translate.string('Add email') + ' '} // eslint-disable-line prefer-template
      onChange={handleChange}
      onSearchChange={handleSearchChange}
      onBlur={handleBlur}
      selectedLabel={null}
      icon=""
    />
  );
}

EmailListField.propTypes = {
  value: PropTypes.arrayOf(PropTypes.string).isRequired,
  disabled: PropTypes.bool,
  onChange: PropTypes.func.isRequired,
  onFocus: PropTypes.func,
  onBlur: PropTypes.func,
};

EmailListField.defaultProps = {
  disabled: false,
  onFocus: () => {},
  onBlur: () => {},
};
