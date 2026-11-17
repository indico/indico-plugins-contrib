// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import cloneCatalogURL from 'indico-url:plugin_affiliation_extras.api_clone_catalog';
import deleteCatalogURL from 'indico-url:plugin_affiliation_extras.api_delete_catalog';
import toggleDefaultCatalogURL from 'indico-url:plugin_affiliation_extras.api_toggle_default_catalog';
import catalogDetailURL from 'indico-url:plugin_affiliation_extras.catalog_detail';
import catalogNewURL from 'indico-url:plugin_affiliation_extras.create_catalog';
import catalogListURL from 'indico-url:plugin_affiliation_extras.manage_affiliations';

import _ from 'lodash';
import PropTypes from 'prop-types';
import React, {useState} from 'react';
import {Link} from 'react-router-dom';
import {Button, Icon, Popup} from 'semantic-ui-react';

import {RequestConfirm} from 'indico/react/components';
import {Param, Translate} from 'indico/react/i18n';
import {handleAxiosError, indicoAxios} from 'indico/utils/axios';

import './CatalogListPane.module.scss';

function CatalogRow({
  catalog,
  dispatch,
  setPrompt,
  targetLocator,
  inherited,
  defaultCatalogId,
  explicitDefaultCatalogId,
  shouldConfirmDefaultChange,
  inheritedDefaultCatalog,
}) {
  const isDefault = catalog.id === defaultCatalogId;
  const isInheritedDefault = isDefault && catalog.id !== explicitDefaultCatalogId;
  const deleteCatalog = async () => {
    try {
      await indicoAxios.delete(deleteCatalogURL({catalog_id: catalog.id, ...targetLocator}));
      dispatch({type: 'DELETE_CATALOG', id: catalog.id});
    } catch (err) {
      handleAxiosError(err);
      return true;
    }
  };

  const cloneCatalog = async () => {
    try {
      const {data: clonedCatalog} = await indicoAxios.post(
        cloneCatalogURL({catalog_id: catalog.id, ...targetLocator})
      );
      dispatch({type: 'ADD_CATALOG', catalog: clonedCatalog});
    } catch (err) {
      handleAxiosError(err);
    }
  };

  const toggleDefaultCatalog = async () => {
    try {
      const {data} = await indicoAxios.post(
        toggleDefaultCatalogURL({catalog_id: catalog.id, ...targetLocator})
      );
      dispatch({
        type: 'SET_DEFAULT_CATALOG',
        defaultCatalogId: data.default_catalog_id,
        explicitDefaultCatalogId: data.explicit_default_catalog_id,
      });
    } catch (err) {
      handleAxiosError(err);
      return true;
    }
  };

  const openDeletePrompt = () => {
    setPrompt({
      header: Translate.string('Confirm deletion'),
      content: (
        <Translate>
          Are you sure you want to delete the catalog{' '}
          <Param name="name" value={catalog.name} wrapper={<strong />} />?
        </Translate>
      ),
      confirmText: Translate.string('Delete'),
      negative: true,
      func: deleteCatalog,
    });
  };

  const toggleDefaultWithConfirmation = () => {
    // clearing a pin that matches the parent category's default does not change anything,
    // and pinning the first default does not replace an existing one
    if (
      !shouldConfirmDefaultChange ||
      (isDefault && catalog.id === inheritedDefaultCatalog?.id) ||
      defaultCatalogId === null
    ) {
      toggleDefaultCatalog();
      return;
    }
    setPrompt({
      header: isDefault
        ? Translate.string('Clear default catalog')
        : Translate.string('Change default catalog'),
      content: isDefault ? (
        inheritedDefaultCatalog ? (
          <Translate>
            The default catalog will go back to{' '}
            <Param name="inherited" value={inheritedDefaultCatalog.name} wrapper={<strong />} />.
            This may change which registrations the focal points can manage.
          </Translate>
        ) : (
          <Translate>
            There will be no default catalog. Focal points may lose access to some registrations.
          </Translate>
        )
      ) : (
        <Translate>
          <Param name="name" value={catalog.name} wrapper={<strong />} /> will become the default
          catalog. This may change which registrations the focal points can manage.
        </Translate>
      ),
      confirmText: isDefault
        ? Translate.string('Clear default')
        : Translate.string('Change default'),
      negative: false,
      func: toggleDefaultCatalog,
    });
  };

  const defaultTitle = isInheritedDefault
    ? Translate.string('This is the inherited default catalog')
    : isDefault
      ? Translate.string('Clear default catalog')
      : Translate.string('Set as default catalog');

  return (
    <tr>
      <td>
        {inherited ? (
          catalog.name
        ) : (
          <Link to={catalogDetailURL({catalog_id: catalog.id, ...targetLocator})}>
            {catalog.name}
          </Link>
        )}
      </td>
      <td className="text-superfluous">
        {inherited && catalog.owner && (
          <>
            {'event_id' in catalog.owner.locator ? (
              <Translate>
                from event{' '}
                <Param
                  name="title"
                  value={catalog.owner.title}
                  wrapper={<a href={catalogListURL(catalog.owner.locator)} />}
                />
              </Translate>
            ) : (
              <Translate>
                from category{' '}
                <Param
                  name="title"
                  value={catalog.owner.title}
                  wrapper={<a href={catalogListURL(catalog.owner.locator)} />}
                />
              </Translate>
            )}
          </>
        )}
      </td>
      <td styleName="catalog-actions">
        <div className="thin toolbar right">
          <Popup
            position="bottom center"
            content={defaultTitle}
            trigger={
              <Icon
                name="pin"
                color={isDefault ? 'yellow' : undefined}
                disabled={isInheritedDefault}
                onClick={toggleDefaultWithConfirmation}
              />
            }
          />
          {!inherited && (
            <Popup
              position="bottom center"
              content={Translate.string('Edit catalog')}
              trigger={
                <Link to={catalogDetailURL({catalog_id: catalog.id, ...targetLocator})}>
                  <Icon name="edit" color="blue" />
                </Link>
              }
            />
          )}
          <Popup
            position="bottom center"
            content={Translate.string('Clone catalog')}
            trigger={<Icon name="clone" color="blue" onClick={cloneCatalog} />}
          />
          {!inherited && (
            <Popup
              position="bottom right"
              content={
                catalog.is_used_by_regform
                  ? Translate.string(
                      'This catalog is used by a representation field and cannot be deleted'
                    )
                  : Translate.string('Delete catalog')
              }
              trigger={
                <Icon
                  name="trash"
                  color="red"
                  disabled={catalog.is_used_by_regform}
                  onClick={openDeletePrompt}
                />
              }
            />
          )}
        </div>
      </td>
    </tr>
  );
}

CatalogRow.propTypes = {
  catalog: PropTypes.object.isRequired,
  dispatch: PropTypes.func.isRequired,
  setPrompt: PropTypes.func.isRequired,
  targetLocator: PropTypes.object.isRequired,
  inherited: PropTypes.bool,
  defaultCatalogId: PropTypes.number,
  explicitDefaultCatalogId: PropTypes.number,
  shouldConfirmDefaultChange: PropTypes.bool,
  inheritedDefaultCatalog: PropTypes.object,
};

CatalogRow.defaultProps = {
  inherited: false,
  defaultCatalogId: null,
  explicitDefaultCatalogId: null,
  shouldConfirmDefaultChange: false,
  inheritedDefaultCatalog: null,
};

export default function CatalogListPane({
  ownCatalogs,
  inheritedCatalogs,
  targetLocator,
  dispatch,
  defaultCatalogId,
  explicitDefaultCatalogId,
  shouldConfirmDefaultChange,
  inheritedDefaultCatalogId,
}) {
  const [prompt, setPrompt] = useState(null);
  const inheritedDefaultCatalog = inheritedCatalogs.find(
    catalog => catalog.id === inheritedDefaultCatalogId
  );

  return (
    <div styleName="catalog-list">
      <RequestConfirm
        header={prompt?.header ?? ''}
        confirmText={prompt?.confirmText}
        negative={prompt?.negative}
        onClose={() => setPrompt(null)}
        requestFunc={prompt?.func || (() => null)}
        open={prompt !== null}
      >
        {prompt?.content}
      </RequestConfirm>

      {!!inheritedCatalogs.length && (
        <section>
          <h3>
            <Translate>Inherited catalogs</Translate>
          </h3>
          <table className="i-table-widget">
            <tbody>
              {_.sortBy(inheritedCatalogs, 'name').map(catalog => (
                <CatalogRow
                  key={catalog.id}
                  catalog={catalog}
                  dispatch={dispatch}
                  setPrompt={setPrompt}
                  targetLocator={targetLocator}
                  inherited
                  defaultCatalogId={defaultCatalogId}
                  explicitDefaultCatalogId={explicitDefaultCatalogId}
                  shouldConfirmDefaultChange={shouldConfirmDefaultChange}
                  inheritedDefaultCatalog={inheritedDefaultCatalog}
                />
              ))}
            </tbody>
          </table>
        </section>
      )}

      <section>
        <div className="flexrow f-a-center f-j-space-between">
          <h3>
            <Translate>Custom catalogs</Translate>
          </h3>
          <Button
            as={Link}
            to={catalogNewURL(targetLocator)}
            icon="plus"
            content={Translate.string('Add new catalog')}
            className="mini primary icon"
          />
        </div>
        {ownCatalogs.length ? (
          <table className="i-table-widget">
            <tbody>
              {_.sortBy(ownCatalogs, 'name').map(catalog => (
                <CatalogRow
                  key={catalog.id}
                  catalog={catalog}
                  dispatch={dispatch}
                  setPrompt={setPrompt}
                  targetLocator={targetLocator}
                  defaultCatalogId={defaultCatalogId}
                  explicitDefaultCatalogId={explicitDefaultCatalogId}
                  shouldConfirmDefaultChange={shouldConfirmDefaultChange}
                  inheritedDefaultCatalog={inheritedDefaultCatalog}
                />
              ))}
            </tbody>
          </table>
        ) : (
          <Translate as="div" className="italic text-not-important">
            No catalogs
          </Translate>
        )}
      </section>
    </div>
  );
}

CatalogListPane.propTypes = {
  ownCatalogs: PropTypes.array.isRequired,
  inheritedCatalogs: PropTypes.array.isRequired,
  targetLocator: PropTypes.object.isRequired,
  dispatch: PropTypes.func.isRequired,
  defaultCatalogId: PropTypes.number,
  explicitDefaultCatalogId: PropTypes.number,
  shouldConfirmDefaultChange: PropTypes.bool,
  inheritedDefaultCatalogId: PropTypes.number,
};
