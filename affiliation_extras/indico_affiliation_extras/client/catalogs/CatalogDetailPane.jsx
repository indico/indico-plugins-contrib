// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import _ from 'lodash';
import PropTypes from 'prop-types';
import React from 'react';
import {DndProvider} from 'react-dnd';
import {Form as FinalForm} from 'react-final-form';
import {HTML5Backend} from 'react-dnd-html5-backend';
import {Form, Segment} from 'semantic-ui-react';

import {ManagementPageSubTitle} from 'indico/react/components';
import {FinalInput, FinalSubmitButton} from 'indico/react/forms';
import {Translate} from 'indico/react/i18n';

import FinalCatalogList from '../components/CatalogListField';

import './CatalogDetailPane.module.scss';

export default function CatalogDetailPane({catalog, targetLocator, isNew, onSubmit}) {
  const isCreate = isNew === true;
  const initialValues = {
    name: catalog?.name || '',
    lists: _.sortBy(catalog?.lists || [], 'position').map(list => ({
      id: list.id,
      name: list.name,
      position: list.position,
      is_enabled: list.is_enabled,
      groups: list.groups,
      tags: list.tags,
      affiliations: list.affiliations,
    })),
  };

  if (!catalog && !isCreate) {
    return (
      <Segment placeholder>
        <Translate>Catalog not found</Translate>
      </Segment>
    );
  }

  const handleSubmit = async formData =>
    onSubmit({
      name: formData.name.trim(),
      lists: formData.lists.map(list => ({
        id: list.id,
        name: list.name.trim(),
        position: list.position,
        is_enabled: list.is_enabled,
        groups: list.groups.map(group => group.id),
        tags: list.tags.map(tag => tag.id),
        affiliations: list.affiliations.map(affiliation => affiliation.id),
      })),
    });

  return (
    <div styleName="catalog-detail">
      <ManagementPageSubTitle title={isCreate ? Translate.string('New catalog') : catalog.name} />
      <DndProvider backend={HTML5Backend}>
        <FinalForm
          onSubmit={handleSubmit}
          initialValues={initialValues}
          initialValuesEqual={_.isEqual}
          subscription={{}}
        >
          {fprops => (
            <Form onSubmit={fprops.handleSubmit}>
              <section>
                <h3>
                  <Translate>Name</Translate>
                </h3>
                <FinalInput
                  name="name"
                  required
                  placeholder={Translate.string('Enter a name for the catalog')}
                  validate={value =>
                    value && value.trim()
                      ? undefined
                      : Translate.string('Catalog name is required.')
                  }
                />
              </section>
              <section>
                <h3>
                  <Translate>Lists</Translate>
                </h3>
                <FinalCatalogList name="lists" targetLocator={targetLocator} required />
              </section>
              <div styleName="form-actions">
                <FinalSubmitButton label={Translate.string('Save changes')} disabledUntilChange />
              </div>
            </Form>
          )}
        </FinalForm>
      </DndProvider>
    </div>
  );
}

CatalogDetailPane.propTypes = {
  catalog: PropTypes.object,
  targetLocator: PropTypes.object.isRequired,
  isNew: PropTypes.bool,
  onSubmit: PropTypes.func.isRequired,
};

CatalogDetailPane.defaultProps = {
  catalog: null,
  isNew: false,
};
