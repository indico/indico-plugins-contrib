// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import React from 'react';
import {useForm, useFormState} from 'react-final-form';
import {Form, Loader, Message} from 'semantic-ui-react';

import Checkbox from 'indico/react/components/Checkbox';
import {FinalDropdown} from 'indico/react/forms';
import {useIndicoAxios} from 'indico/react/hooks';
import {Translate} from 'indico/react/i18n';

interface Props {
  catalogsURL: string;
  name: string;
}
interface CatalogData {
  catalogs: {id: number; name: string; parent?: string}[];
  defaultCatalogId: number | null;
}

export default function FinalAffiliationCatalogField({catalogsURL, name}: Props) {
  const form = useForm();
  const {values} = useFormState<Record<string, number | null | ''>>({subscription: {values: true}});
  const catalogId = values[name] ?? null;
  const useDefaultCatalog = catalogId === null;
  const {data, loading, error} = useIndicoAxios(catalogsURL, {camelize: true}) as {
    data: CatalogData | null;
    loading: boolean;
    error: unknown;
  };
  const disabled = loading || !!error || !data;
  const options: {value: number; text: string; disabled?: boolean}[] = (data?.catalogs ?? []).map(
    catalog => ({
      value: catalog.id,
      text: catalog.parent ? `${catalog.name} (${catalog.parent})` : catalog.name,
    })
  );
  const unavailable =
    typeof catalogId === 'number' &&
    data &&
    !data.catalogs.some(catalog => catalog.id === catalogId);
  if (typeof catalogId === 'number' && (!data || unavailable)) {
    options.push({
      value: catalogId,
      text: data ? Translate.string('Unavailable catalog') : Translate.string('Selected catalog'),
      disabled: true,
    });
  }
  return (
    <>
      <Form.Field disabled={disabled}>
        <Checkbox
          label={Translate.string('Use default catalog')}
          checked={useDefaultCatalog}
          disabled={disabled}
          onChange={(_, {checked}: {checked: boolean}) => {
            form.change(name, checked ? null : (data?.defaultCatalogId ?? ''));
          }}
        />
      </Form.Field>
      <FinalDropdown
        name={name}
        label={Translate.string('Affiliation catalog')}
        options={options}
        format={value => (useDefaultCatalog ? data?.defaultCatalogId : value) ?? null}
        parse={value => value || null}
        disabled={disabled || useDefaultCatalog}
        required={useDefaultCatalog ? false : 'no-validator'}
        data={data}
        clearable={false}
        placeholder={
          useDefaultCatalog && data && data.defaultCatalogId === null
            ? Translate.string('No default catalog configured')
            : Translate.string('Select an affiliation catalog')
        }
        validate={value =>
          value !== null &&
          value !== undefined &&
          data &&
          !data.catalogs.some(catalog => catalog.id === value)
            ? Translate.string('Select an affiliation catalog available for this event.')
            : undefined
        }
        selection
        search
        fluid
      />
      {loading && <Loader active inline="centered" />}
      {!!error && (
        <Message error content={Translate.string('Affiliation catalogs could not be loaded.')} />
      )}
      {unavailable && (
        <Message
          error
          content={Translate.string('Select an affiliation catalog available for this event.')}
        />
      )}
    </>
  );
}
