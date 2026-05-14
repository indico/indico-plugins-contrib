// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

// XXX: To delete when https://github.com/indico/indico/pull/7429 is merged.

import countriesURL from 'indico-url:users.api_countries';

import PropTypes from 'prop-types';
import React, {useEffect, useState} from 'react';
import {Dropdown} from 'semantic-ui-react';

import {Translate} from 'indico/react/i18n';
import {handleAxiosError, indicoAxios} from 'indico/utils/axios';

const isoToFlag = code =>
  String.fromCodePoint(...code.split('').map(c => c.charCodeAt(0) + 0x1f1a5));

let countriesPromise = null;

function useCountries() {
  const [countries, setCountries] = useState(null);
  useEffect(() => {
    if (!countriesPromise) {
      countriesPromise = indicoAxios
        .get(countriesURL({}))
        .then(({data}) => data)
        .catch(error => {
          countriesPromise = null;
          handleAxiosError(error);
        });
    }
    countriesPromise.then(setCountries);
  }, []);
  return countries;
}

export default function CountryDropdown({value, onChange, fluid}) {
  const countries = useCountries();

  return (
    <Dropdown
      fluid={fluid}
      search
      selection
      clearable
      value={value}
      options={(countries ?? []).map(([code, name]) => ({
        key: code,
        value: code,
        text: `${isoToFlag(code)} ${name}`,
      }))}
      onChange={(_, {value: v}) => onChange(v)}
      placeholder={Translate.string('Select a country...')}
      loading={!countries}
      disabled={!countries}
    />
  );
}

CountryDropdown.propTypes = {
  value: PropTypes.string.isRequired,
  onChange: PropTypes.func.isRequired,
  fluid: PropTypes.bool,
};

CountryDropdown.defaultProps = {
  fluid: false,
};
