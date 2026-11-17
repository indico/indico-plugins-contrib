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
import {HTML5Backend} from 'react-dnd-html5-backend';
import {Field, Form as FinalForm} from 'react-final-form';
import {Form, Message, Segment} from 'semantic-ui-react';

import {ManagementPageSubTitle} from 'indico/react/components';
import {FinalCheckbox, FinalInput, FinalSubmitButton} from 'indico/react/forms';
import {Translate} from 'indico/react/i18n';

import FinalCatalogList from '../components/CatalogListField';

import './CatalogDetailPane.module.scss';

export default function CatalogDetailPane({
  catalog,
  targetLocator,
  isNew,
  warnOnSetDefault,
  onSubmit,
}) {
  const isCreate = isNew === true;
  const isEvent = 'event_id' in targetLocator;
  const initialValues = {
    ...(isCreate && {set_as_default: true}),
    name: catalog?.name || '',
    lists: _.sortBy(catalog?.lists || [], 'position').map(list =>
      _.pick(list, [
        'id',
        'name',
        'position',
        'is_enabled',
        'affiliation_mode',
        'groups',
        'tags',
        'affiliations',
      ])
    ),
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
        affiliation_mode: list.affiliation_mode,
        groups: list.groups.map(group => group.id),
        tags: list.tags.map(tag => tag.id),
        affiliations: list.affiliations.map(affiliation => affiliation.id),
      })),
      ...(isCreate && {set_as_default: formData.set_as_default}),
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
            <Form onSubmit={fprops.handleSubmit} noValidate>
              <section>
                <FinalInput
                  name="name"
                  label={Translate.string('Name')}
                  required="no-validator"
                  placeholder={Translate.string('Enter a name for the catalog')}
                  validate={value =>
                    value && value.trim()
                      ? undefined
                      : Translate.string('Catalog name is required.')
                  }
                />
              </section>
              <section>
                <FinalCatalogList
                  name="lists"
                  label={Translate.string('Lists')}
                  targetLocator={targetLocator}
                  autoId={false}
                  required
                />
              </section>
              {isCreate && (
                <section>
                  <FinalCheckbox
                    name="set_as_default"
                    label={
                      isEvent
                        ? Translate.string('Set catalog as default for this event')
                        : Translate.string('Set catalog as default for this category')
                    }
                    showAsToggle
                  />
                  {warnOnSetDefault && (
                    <Field name="set_as_default" subscription={{value: true}}>
                      {({input: {value}}) =>
                        value && (
                          <Message warning visible>
                            <Translate>
                              This may change which registrations the focal points can manage.
                            </Translate>
                          </Message>
                        )
                      }
                    </Field>
                  )}
                </section>
              )}
              <div styleName="form-actions">
                <FinalSubmitButton
                  label={Translate.string('Save changes')}
                  disabledUntilChange
                  disabledIfInvalid={false}
                />
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
  warnOnSetDefault: PropTypes.bool,
  onSubmit: PropTypes.func.isRequired,
};

CatalogDetailPane.defaultProps = {
  catalog: null,
  isNew: false,
  warnOnSetDefault: false,
};
