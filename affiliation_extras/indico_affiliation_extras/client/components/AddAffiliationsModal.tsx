// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import React, {useState} from 'react';
import {Form as FinalForm} from 'react-final-form';
import {Button, Form, Grid, Icon, Label, List, Loader, Modal} from 'semantic-ui-react';

import {Affiliation} from 'indico/modules/users/affiliations/types';
import {FinalDropdown, FinalInput, validators} from 'indico/react/forms';
import {PluralTranslate, Singular, Plural, Param, Translate} from 'indico/react/i18n';
import {indicoAxios} from 'indico/utils/axios';
import {snakifyKeys} from 'indico/utils/case';

import {GroupInfo, TagInfo} from '../types';

// XXX: import from 'indico/react/components' when https://github.com/indico/indico/pull/7429 is merged.
import {FinalCountryDropdown} from './CountryDropdown';

import './AddAffiliationsModal.module.scss';

interface AffiliationWithExtraInfo extends Affiliation {
  extraInfo?: number;
}

interface SearchFilters {
  q: string;
  groupIds: number[];
  tagIds: number[];
  countryCode: string;
}

const initialSearchFilters: SearchFilters = {
  q: '',
  groupIds: [],
  tagIds: [],
  countryCode: '',
};

interface ResultSectionProps {
  items: AffiliationWithExtraInfo[];
  isSelected: (item: AffiliationWithExtraInfo) => boolean;
  onToggle: (item: AffiliationWithExtraInfo) => void;
  renderItemExtra?: ((item: AffiliationWithExtraInfo) => React.ReactNode) | null;
}

interface AddAffiliationsModalProps {
  onClose: () => void;
  onConfirm: (selection: AffiliationWithExtraInfo[]) => void;
  initialValues: AffiliationWithExtraInfo[];
  searchURL: string;
  groups: GroupInfo[] | null;
  tags: TagInfo[] | null;
  extraInfoURL?: string | null;
  renderItemExtra?: ((item: AffiliationWithExtraInfo) => React.ReactNode) | null;
}

function ResultSection({items, isSelected, onToggle, renderItemExtra = null}: ResultSectionProps) {
  return items.length > 0 ? (
    <List divided relaxed styleName="list">
      {items.map(item => (
        <List.Item key={item.id} styleName="result-item" onClick={() => onToggle(item)}>
          <div styleName="item">
            <div styleName="content">
              {item.name}
              {renderItemExtra && <span styleName="item-count">{renderItemExtra(item)}</span>}
            </div>
            <div styleName="item-actions">
              {isSelected(item) ? (
                <Icon name="checkmark" size="large" color="green" />
              ) : (
                <Icon styleName="button" name="add" size="large" />
              )}
            </div>
          </div>
        </List.Item>
      ))}
    </List>
  ) : (
    <p styleName="no-results">
      <Translate>No results.</Translate>
    </p>
  );
}

export default function AddAffiliationsModal({
  onClose,
  onConfirm,
  initialValues,
  searchURL,
  groups,
  tags,
  extraInfoURL = null,
  renderItemExtra = null,
}: AddAffiliationsModalProps) {
  const [hasSearched, setHasSearched] = useState(false);
  const [affiliations, setAffiliations] = useState<AffiliationWithExtraInfo[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [values, setValues] = useState<AffiliationWithExtraInfo[]>(initialValues);

  const toggle = (item: AffiliationWithExtraInfo) => {
    setValues(prev =>
      prev.some(i => i.id === item.id) ? prev.filter(i => i.id !== item.id) : [...prev, item]
    );
  };

  const isSelected = (item: AffiliationWithExtraInfo) => values.some(i => i.id === item.id);
  const initialIds = new Set(initialValues.map(i => i.id));
  const newItems = values.filter(i => !initialIds.has(i.id));
  const newAdditionsCount = newItems.length;
  const registrationsCount = newItems.reduce((acc, item) => acc + (item.extraInfo || 0), 0);
  const hasChanges =
    values.some(i => !initialIds.has(i.id)) ||
    initialValues.some(i => !values.some(s => s.id === i.id));

  const applySearch = async (filters: SearchFilters) => {
    setHasSearched(true);
    setIsLoading(true);
    setAffiliations([]);
    try {
      const {data} = await indicoAxios.get<AffiliationWithExtraInfo[]>(searchURL, {
        params: snakifyKeys(filters),
      });
      if (extraInfoURL && data.length) {
        const {data: extraInfoData} = await indicoAxios
          .post<Record<string, number>>(extraInfoURL, {affiliation_ids: data.map(a => a.id)})
          .catch(() => ({data: {} as Record<string, number>}));
        setAffiliations(data.map(a => ({...a, extraInfo: extraInfoData[String(a.id)] ?? 0})));
      } else {
        setAffiliations(data);
      }
    } catch {
      setAffiliations([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleConfirm = () => {
    onConfirm(values);
    onClose();
  };

  return (
    <Modal open onClose={onClose} size="large" closeIcon>
      <Modal.Header>
        <Translate>Add Affiliations</Translate>
      </Modal.Header>
      <Modal.Content scrolling>
        <Grid>
          <Grid.Column width={4}>
            <FinalForm
              onSubmit={applySearch}
              initialValues={initialSearchFilters}
              subscription={{
                dirtySinceLastSubmit: true,
                hasValidationErrors: true,
                pristine: true,
                submitting: true,
                submitSucceeded: true,
              }}
            >
              {fprops => (
                <Form onSubmit={fprops.handleSubmit}>
                  <FinalInput
                    name="q"
                    label={Translate.string('Affiliation name')}
                    required
                    validate={(value: string) => validators.required((value || '').trim())}
                    placeholder={Translate.string('Affiliation name')}
                    autoFocus
                  />
                  <FinalDropdown
                    name="groupIds"
                    label={Translate.string('Groups')}
                    fluid
                    multiple
                    search
                    selection
                    options={(groups ?? []).map(group => ({
                      key: group.id,
                      value: group.id,
                      text: `${group.code}: ${group.name}`,
                    }))}
                    placeholder={Translate.string('Select groups...')}
                    loading={!groups}
                    disabled={!groups}
                  />
                  <FinalDropdown
                    name="tagIds"
                    label={Translate.string('Tags')}
                    fluid
                    multiple
                    search
                    selection
                    options={(tags ?? []).map(tag => ({
                      key: tag.id,
                      value: tag.id,
                      text: tag.name,
                      color: tag.color,
                      content: (
                        <>
                          <Label color={tag.color} /> <span style={{marginLeft: 10}}></span>{' '}
                          {tag.name}
                        </>
                      ),
                    }))}
                    renderLabel={({color, text}) => ({color, content: text})}
                    placeholder={Translate.string('Select tags...')}
                    loading={!tags}
                    disabled={!tags}
                  />
                  <FinalCountryDropdown
                    name="countryCode"
                    label={Translate.string('Country')}
                    fluid
                  />
                  <Button
                    type="submit"
                    icon="search"
                    primary
                    content={Translate.string('Search')}
                    loading={fprops.submitting}
                    disabled={
                      fprops.hasValidationErrors ||
                      fprops.submitting ||
                      (fprops.submitSucceeded ? !fprops.dirtySinceLastSubmit : fprops.pristine)
                    }
                  />
                </Form>
              )}
            </FinalForm>
          </Grid.Column>

          {!hasSearched ? (
            <Grid.Column width={12}>
              <Translate>Enter a search term and click Search.</Translate>
            </Grid.Column>
          ) : isLoading ? (
            <Grid.Column width={12}>
              <Loader active inline="centered" />
            </Grid.Column>
          ) : (
            <Grid.Column width={12}>
              <ResultSection
                items={affiliations}
                isSelected={isSelected}
                onToggle={toggle}
                renderItemExtra={renderItemExtra}
              />
            </Grid.Column>
          )}
        </Grid>
      </Modal.Content>

      <Modal.Actions>
        <div styleName="actions">
          <span styleName="selected-count">
            {newAdditionsCount > 0 && (
              <>
                <PluralTranslate count={newAdditionsCount}>
                  <Singular>
                    <Param name="count" value={newAdditionsCount} /> affiliation selected
                  </Singular>
                  <Plural>
                    <Param name="count" value={newAdditionsCount} /> affiliations selected
                  </Plural>
                </PluralTranslate>
                {extraInfoURL && registrationsCount > 0 && (
                  <>
                    {', '}
                    <PluralTranslate count={registrationsCount}>
                      <Singular>
                        <Param name="count" value={registrationsCount} /> user belongs to them
                      </Singular>
                      <Plural>
                        <Param name="count" value={registrationsCount} /> users belong to them
                      </Plural>
                    </PluralTranslate>
                  </>
                )}
              </>
            )}
          </span>
          <Button type="button" primary onClick={handleConfirm} disabled={!hasChanges}>
            <Translate>Add</Translate>
          </Button>
          <Button type="button" onClick={onClose}>
            <Translate>Cancel</Translate>
          </Button>
        </div>
      </Modal.Actions>
    </Modal>
  );
}
