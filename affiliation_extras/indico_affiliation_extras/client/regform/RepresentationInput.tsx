// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import affiliationCatalogsURL from 'indico-url:plugin_affiliation_extras.api_reg_form_affiliation_catalogs';
import manageAffiliationsURL from 'indico-url:plugin_affiliation_extras.manage_affiliations';
import searchAffiliationsURL from 'indico-url:plugin_affiliation_extras.search_registration_affiliation';
import searchAffiliationsManagementURL from 'indico-url:plugin_affiliation_extras.search_registration_affiliation_management';

import {noop} from 'lodash';
import React from 'react';
import {useSelector} from 'react-redux';
import {Dropdown, Form, Input, Message} from 'semantic-ui-react';

import ChoiceLabel from 'indico/modules/events/registration/form/fields/ChoiceLabel';
import {getItemById, getStaticData} from 'indico/modules/events/registration/form/selectors';
import {AffiliationField} from 'indico/react/components';
import {FinalField} from 'indico/react/forms';
import {Param, Translate} from 'indico/react/i18n';

import FinalAffiliationCatalogField from '../components/AffiliationCatalogField';

import './RepresentationInput.module.scss';

interface RepresentationType {
  id: number;
  name: string;
  affiliationMode: 'predefined' | 'custom';
  affiliations?: {id: number; name: string}[];
}
interface AffiliationValue {
  id: number | null;
  text: string;
}
interface StaticData {
  eventId: number;
  regformId: number;
  management?: boolean;
}
type RepresentationValue =
  | {
      representationId: number | null;
      representationName: string;
      affiliation: AffiliationValue;
    }
  | Record<string, never>;

const EMPTY_AFFILIATION: AffiliationValue = {id: null, text: ''};
const EMPTY_VALUE: RepresentationValue = {
  representationId: null,
  representationName: '',
  affiliation: EMPTY_AFFILIATION,
};

interface RepresentationInputComponentProps {
  id: string;
  value?: RepresentationValue | null;
  onChange: (value: RepresentationValue) => void;
  disabled: boolean;
  isRequired: boolean;
  showAsRequired: boolean;
  representationTypes: RepresentationType[];
  getSearchAffiliationURL: (params: {q: string; affiliationListId: number}) => string;
}

function RepresentationInputComponent({
  id,
  value,
  onChange,
  disabled,
  isRequired,
  showAsRequired,
  representationTypes,
  getSearchAffiliationURL,
}: RepresentationInputComponentProps) {
  const normalizedValue = value?.affiliation ? value : EMPTY_VALUE;
  const representationId = normalizedValue.representationId;
  const selectedRepresentation =
    representationTypes.find(item => item.id === representationId) ?? null;
  const representationOptions: {value: number; text: string; disabled?: boolean}[] =
    representationTypes.map(item => ({
      value: item.id,
      text: item.name,
    }));
  const historicalValue = representationId !== null && !selectedRepresentation;
  if (historicalValue) {
    representationOptions.push({
      value: representationId,
      text: normalizedValue.representationName,
      disabled: true,
    });
  }
  const preloadedAffiliationOptions = (selectedRepresentation?.affiliations || []).map(
    affiliation => ({
      key: affiliation.id,
      value: affiliation.id,
      text: affiliation.name,
    })
  );
  if (
    normalizedValue.affiliation.id !== null &&
    normalizedValue.affiliation.text &&
    !preloadedAffiliationOptions.some(option => option.value === normalizedValue.affiliation.id)
  ) {
    preloadedAffiliationOptions.unshift({
      key: normalizedValue.affiliation.id,
      value: normalizedValue.affiliation.id,
      text: normalizedValue.affiliation.text,
    });
  }
  const usePreloadedAffiliations = preloadedAffiliationOptions.length > 0;

  const handleRepresentationChange = (_: unknown, {value: selectedValue}: {value?: unknown}) => {
    const nextRepresentationId = typeof selectedValue === 'number' ? selectedValue : null;
    if (nextRepresentationId === null) {
      onChange({});
      return;
    }
    const nextRepresentation = representationTypes.find(item => item.id === nextRepresentationId);
    onChange({
      representationId: nextRepresentationId,
      representationName: nextRepresentation?.name ?? '',
      affiliation: EMPTY_AFFILIATION,
    });
  };

  const handleAffiliationChange = (nextAffiliation: AffiliationValue) => {
    onChange({
      ...normalizedValue,
      affiliation: nextAffiliation ?? EMPTY_AFFILIATION,
    });
  };

  return (
    <>
      <Form.Field>
        <Dropdown
          id={`${id}-representation-type`}
          styleName="representation-field"
          options={representationOptions}
          search
          selection
          fluid
          required={isRequired}
          disabled={disabled}
          clearable={!isRequired}
          placeholder={Translate.string('Select a representation type')}
          value={representationId}
          onChange={handleRepresentationChange}
        />
      </Form.Field>
      {representationId !== null && (
        <Form.Field required={showAsRequired}>
          <label htmlFor={`${id}-affiliation`}>
            <ChoiceLabel
              choice={{
                caption: selectedRepresentation?.name ?? normalizedValue.representationName,
                _deleted: historicalValue,
              }}
              management={false}
              paid={false}
            />
          </label>
          {selectedRepresentation?.affiliationMode === 'custom' ||
          (historicalValue && normalizedValue.affiliation.id === null) ? (
            <Input
              id={`${id}-affiliation`}
              styleName="representation-field"
              value={normalizedValue.affiliation.text}
              onChange={(_, {value: text}) => handleAffiliationChange({id: null, text})}
              placeholder={Translate.string('Enter an affiliation name')}
              disabled={disabled || historicalValue}
              required={isRequired}
              fluid
            />
          ) : (
            <AffiliationField
              id={`${id}-affiliation`}
              styleName="representation-field"
              value={normalizedValue.affiliation}
              onChange={handleAffiliationChange}
              allowCustomAffiliations={false}
              currentAffiliation={null}
              includeMeta={false}
              searchAffiliationURL={({q}) =>
                getSearchAffiliationURL({q, affiliationListId: representationId})
              }
              // These props intentionally pass through AffiliationField to ComboDropdown.
              {...(usePreloadedAffiliations
                ? {
                    options: preloadedAffiliationOptions,
                    search: true,
                    onSearchChange: noop,
                  }
                : {})}
              disabled={disabled || historicalValue}
            />
          )}
        </Form.Field>
      )}
    </>
  );
}

interface RepresentationInputProps {
  fieldId: number;
  htmlId: string;
  htmlName: string;
  disabled?: boolean;
  isRequired: boolean;
  representationTypes?: RepresentationType[];
  searchContext?: Record<string, unknown>;
}

export function RepresentationSettings() {
  const {eventId, regformId} = useSelector(getStaticData) as StaticData;
  const catalogsURL = manageAffiliationsURL({event_id: eventId});

  return (
    <>
      <FinalAffiliationCatalogField
        catalogsURL={affiliationCatalogsURL({event_id: eventId, reg_form_id: regformId})}
        name="catalogId"
      />
      <Translate as={Message} info>
        Representation types are configured in the{' '}
        <Param name="url" wrapper={<a href={catalogsURL} />}>
          affiliation catalogs settings
        </Param>
        .
      </Translate>
    </>
  );
}

export default function RepresentationInput({
  fieldId,
  htmlId,
  htmlName,
  disabled = false,
  isRequired,
  representationTypes = [],
  searchContext = {},
}: RepresentationInputProps) {
  const {eventId, regformId, management} = useSelector(getStaticData) as StaticData;
  const showAsRequired = useSelector(state => getItemById(state, fieldId).isRequired);
  const searchURL = management ? searchAffiliationsManagementURL : searchAffiliationsURL;

  return (
    <FinalField
      id={htmlId}
      name={htmlName}
      component={RepresentationInputComponent}
      undefinedValue={{}}
      disabled={disabled}
      isRequired={isRequired}
      showAsRequired={showAsRequired}
      representationTypes={representationTypes}
      getSearchAffiliationURL={({q, affiliationListId}: {q: string; affiliationListId: number}) =>
        searchURL({
          event_id: eventId,
          reg_form_id: regformId,
          field_id: fieldId,
          affiliation_list_id: affiliationListId,
          q,
          ...searchContext,
        })
      }
    />
  );
}
