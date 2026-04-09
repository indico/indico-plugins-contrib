// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import cloneCatalogURL from 'indico-url:plugin_affiliation_extras.api_clone_catalog';
import deleteCatalogURL from 'indico-url:plugin_affiliation_extras.api_delete_catalog';
import toggleDefaultCatalogURL from 'indico-url:plugin_affiliation_extras.api_toggle_default_catalog';
import catalogDetailURL from 'indico-url:plugin_affiliation_extras.category_catalog_detail';
import catalogListURL from 'indico-url:plugin_affiliation_extras.manage_category_affiliations';
import catalogNewURL from 'indico-url:plugin_affiliation_extras.create_category_catalog';

import _ from 'lodash';
import PropTypes from 'prop-types';
import React, {useState} from 'react';
import {Link} from 'react-router-dom';
import {Button, Icon} from 'semantic-ui-react';

import {RequestConfirmDelete} from 'indico/react/components';
import {Param, Translate} from 'indico/react/i18n';
import {handleAxiosError, indicoAxios} from 'indico/utils/axios';

import './CatalogListPane.module.scss';

function CatalogRow({
  catalog,
  dispatch,
  setDeletePrompt,
  targetLocator,
  inherited,
  defaultCatalogId,
  explicitDefaultCatalogId,
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

  const cloneCatalog = async evt => {
    evt.target.dispatchEvent(new Event('indico:closeAutoTooltip'));
    try {
      const {data: clonedCatalog} = await indicoAxios.post(
        cloneCatalogURL({catalog_id: catalog.id, ...targetLocator})
      );
      dispatch({type: 'ADD_CATALOG', catalog: clonedCatalog});
    } catch (err) {
      handleAxiosError(err);
    }
  };

  const toggleDefaultCatalog = async evt => {
    evt.target.dispatchEvent(new Event('indico:closeAutoTooltip'));
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
    }
  };

  const openDeletePrompt = evt => {
    evt.target.dispatchEvent(new Event('indico:closeAutoTooltip'));
    setDeletePrompt({name: catalog.name, func: deleteCatalog});
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
          <Translate>
            from category{' '}
            <Param
              name="title"
              value={catalog.owner.title}
              wrapper={<a href={catalogListURL(catalog.owner.locator)} />}
            />
          </Translate>
        )}
      </td>
      <td styleName="catalog-actions">
        <div className="thin toolbar right">
          <Icon
            name="pin"
            color={isDefault ? 'yellow' : undefined}
            title={defaultTitle}
            disabled={isInheritedDefault}
            onClick={toggleDefaultCatalog}
          />
          {!inherited && (
            <Link to={catalogDetailURL({catalog_id: catalog.id, ...targetLocator})}>
              <Icon name="edit" color="blue" title={Translate.string('Edit catalog')} />
            </Link>
          )}
          <Icon
            name="clone"
            color="blue"
            title={Translate.string('Clone catalog')}
            onClick={cloneCatalog}
          />
          {!inherited && (
            <Icon
              name="trash"
              color="red"
              title={Translate.string('Delete catalog')}
              onClick={openDeletePrompt}
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
  setDeletePrompt: PropTypes.func,
  targetLocator: PropTypes.object.isRequired,
  inherited: PropTypes.bool,
  defaultCatalogId: PropTypes.number,
  explicitDefaultCatalogId: PropTypes.number,
};

CatalogRow.defaultProps = {
  inherited: false,
  setDeletePrompt: null,
  defaultCatalogId: null,
  explicitDefaultCatalogId: null,
};

export default function CatalogListPane({
  ownCatalogs,
  inheritedCatalogs,
  targetLocator,
  dispatch,
  defaultCatalogId,
  explicitDefaultCatalogId,
}) {
  const [deletePrompt, setDeletePrompt] = useState(null);

  return (
    <div styleName="catalog-list">
      <RequestConfirmDelete
        onClose={() => setDeletePrompt(null)}
        requestFunc={deletePrompt?.func || (() => null)}
        open={deletePrompt !== null}
      >
        <Translate>
          Are you sure you want to delete the catalog{' '}
          <Param name="name" value={deletePrompt?.name} wrapper={<strong />} />?
        </Translate>
      </RequestConfirmDelete>

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
                  targetLocator={targetLocator}
                  inherited
                  defaultCatalogId={defaultCatalogId}
                  explicitDefaultCatalogId={explicitDefaultCatalogId}
                />
              ))}
            </tbody>
          </table>
        </section>
      )}

      <section>
        <div className="flexrow f-a-center f-j-space-between">
          <h3>
            <Translate>Catalogs</Translate>
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
                  setDeletePrompt={setDeletePrompt}
                  targetLocator={targetLocator}
                  defaultCatalogId={defaultCatalogId}
                  explicitDefaultCatalogId={explicitDefaultCatalogId}
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
};
