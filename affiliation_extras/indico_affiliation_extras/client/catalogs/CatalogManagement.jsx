// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import createCatalogURL from 'indico-url:plugin_affiliation_extras.api_create_catalog';
import editCatalogURL from 'indico-url:plugin_affiliation_extras.api_edit_catalog';
import catalogDetailURL from 'indico-url:plugin_affiliation_extras.category_catalog_detail';
import catalogListURL from 'indico-url:plugin_affiliation_extras.manage_category_affiliations';
import catalogNewURL from 'indico-url:plugin_affiliation_extras.create_category_catalog';

import PropTypes from 'prop-types';
import React, {useEffect, useReducer} from 'react';
import {useHistory} from 'react-router';
import {BrowserRouter as Router, Route, Switch} from 'react-router-dom';
import {Message} from 'semantic-ui-react';

import {ManagementPageBackButton} from 'indico/react/components';
import {handleSubmitError} from 'indico/react/forms';
import {routerPathFromFlask, useNumericParam} from 'indico/react/util/routing';
import {Translate} from 'indico/react/i18n';
import {indicoAxios} from 'indico/utils/axios';

import CatalogDetailPane from './CatalogDetailPane';
import CatalogListPane from './CatalogListPane';

function reducer(state, action) {
  switch (action.type) {
    case 'ADD_CATALOG':
      return {
        ...state,
        ownCatalogs: [...state.ownCatalogs, action.catalog],
        message: Translate.string('Catalog "{name}" was added', {name: action.catalog.name}),
      };
    case 'UPDATE_CATALOG':
      return {
        ...state,
        ownCatalogs: state.ownCatalogs.map(catalog =>
          catalog.id === action.catalog.id ? action.catalog : catalog
        ),
        message: Translate.string('Catalog "{name}" was updated', {name: action.catalog.name}),
      };
    case 'DELETE_CATALOG':
      return {
        ...state,
        ownCatalogs: state.ownCatalogs.filter(catalog => catalog.id !== action.id),
        message: Translate.string('Catalog deleted'),
      };
    case 'SET_DEFAULT_CATALOG':
      return {
        ...state,
        defaultCatalogId: action.defaultCatalogId,
        explicitDefaultCatalogId: action.explicitDefaultCatalogId,
      };
    case 'RESET_MESSAGE':
      return {
        ...state,
        message: null,
      };
    default:
      return state;
  }
}

function CatalogEditRoute({catalogs, dispatch, targetLocator}) {
  const catalogId = useNumericParam('catalog_id');
  const catalog = catalogs.find(p => p.id === catalogId);

  const saveCatalog = async payload => {
    try {
      const {data: updatedCatalog} = await indicoAxios.patch(
        editCatalogURL({catalog_id: catalogId, ...targetLocator}),
        payload
      );
      dispatch({type: 'UPDATE_CATALOG', catalog: updatedCatalog});
    } catch (err) {
      return handleSubmitError(err);
    }
  };

  return (
    <>
      <ManagementPageBackButton url={catalogListURL(targetLocator)} />
      <CatalogDetailPane catalog={catalog} targetLocator={targetLocator} onSubmit={saveCatalog} />
    </>
  );
}

function CatalogCreateRoute({dispatch, targetLocator}) {
  const history = useHistory();

  const createCatalog = async payload => {
    try {
      const {data: createdCatalog} = await indicoAxios.post(
        createCatalogURL(targetLocator),
        payload
      );
      dispatch({type: 'ADD_CATALOG', catalog: createdCatalog});
      history.push(catalogListURL(targetLocator));
    } catch (err) {
      return handleSubmitError(err);
    }
  };

  return (
    <>
      <ManagementPageBackButton url={catalogListURL(targetLocator)} />
      <CatalogDetailPane
        catalog={null}
        targetLocator={targetLocator}
        isNew
        onSubmit={createCatalog}
      />
    </>
  );
}

export default function CatalogManagement({initialState, targetLocator}) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const targetIdParams = Object.keys(targetLocator);

  useEffect(() => {
    if (state.message) {
      setTimeout(() => dispatch({type: 'RESET_MESSAGE'}), 2500);
    }
  }, [state.message]);

  return (
    <>
      {state.message && (
        <Message success>
          <Message.Content>{state.message}</Message.Content>
        </Message>
      )}
      <Router>
        <Switch>
          <Route
            exact
            path={routerPathFromFlask(catalogNewURL, targetIdParams)}
            render={() => <CatalogCreateRoute dispatch={dispatch} targetLocator={targetLocator} />}
          />
          <Route
            exact
            path={routerPathFromFlask(catalogDetailURL, [...targetIdParams, 'catalog_id'])}
            render={() => (
              <CatalogEditRoute
                catalogs={state.ownCatalogs}
                dispatch={dispatch}
                targetLocator={targetLocator}
              />
            )}
          />
          <Route
            exact
            path={routerPathFromFlask(catalogListURL, targetIdParams)}
            render={() => (
              <CatalogListPane dispatch={dispatch} targetLocator={targetLocator} {...state} />
            )}
          />
        </Switch>
      </Router>
    </>
  );
}

CatalogEditRoute.propTypes = {
  catalogs: PropTypes.array.isRequired,
  dispatch: PropTypes.func.isRequired,
  targetLocator: PropTypes.object.isRequired,
};

CatalogCreateRoute.propTypes = {
  dispatch: PropTypes.func.isRequired,
  targetLocator: PropTypes.object.isRequired,
};

CatalogManagement.propTypes = {
  initialState: PropTypes.shape({
    ownCatalogs: PropTypes.array,
    inheritedCatalogs: PropTypes.array,
    defaultCatalogId: PropTypes.number,
    explicitDefaultCatalogId: PropTypes.number,
  }).isRequired,
  targetLocator: PropTypes.object.isRequired,
};
