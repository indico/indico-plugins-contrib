// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import createPresetURL from 'indico-url:plugin_affiliation_extras.api_create_preset';
import editPresetURL from 'indico-url:plugin_affiliation_extras.api_edit_preset';
import presetDetailURL from 'indico-url:plugin_affiliation_extras.category_preset_detail';
import presetListURL from 'indico-url:plugin_affiliation_extras.manage_category_affiliations';
import presetNewURL from 'indico-url:plugin_affiliation_extras.create_category_preset';

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

import PresetDetailPane from './PresetDetailPane';
import PresetListPane from './PresetListPane';

function reducer(state, action) {
  switch (action.type) {
    case 'ADD_PRESET':
      return {
        ...state,
        ownPresets: [...state.ownPresets, action.preset],
        message: Translate.string('Preset "{name}" was added', {name: action.preset.name}),
      };
    case 'UPDATE_PRESET':
      return {
        ...state,
        ownPresets: state.ownPresets.map(preset =>
          preset.id === action.preset.id ? action.preset : preset
        ),
        message: Translate.string('Preset "{name}" was updated', {name: action.preset.name}),
      };
    case 'DELETE_PRESET':
      return {
        ...state,
        ownPresets: state.ownPresets.filter(preset => preset.id !== action.id),
        message: Translate.string('Preset deleted'),
      };
    case 'SET_DEFAULT_PRESET':
      return {
        ...state,
        defaultPresetId: action.defaultPresetId,
        explicitDefaultPresetId: action.explicitDefaultPresetId,
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

function PresetEditRoute({presets, dispatch, targetLocator}) {
  const presetId = useNumericParam('preset_id');
  const preset = presets.find(p => p.id === presetId);

  const savePreset = async payload => {
    try {
      const {data: updatedPreset} = await indicoAxios.patch(
        editPresetURL({preset_id: presetId, ...targetLocator}),
        payload
      );
      dispatch({type: 'UPDATE_PRESET', preset: updatedPreset});
    } catch (err) {
      return handleSubmitError(err);
    }
  };

  return (
    <>
      <ManagementPageBackButton url={presetListURL(targetLocator)} />
      <PresetDetailPane preset={preset} targetLocator={targetLocator} onSubmit={savePreset} />
    </>
  );
}

function PresetCreateRoute({dispatch, targetLocator}) {
  const history = useHistory();

  const createPreset = async payload => {
    try {
      const {data: createdPreset} = await indicoAxios.post(createPresetURL(targetLocator), payload);
      dispatch({type: 'ADD_PRESET', preset: createdPreset});
      history.push(presetListURL(targetLocator));
    } catch (err) {
      return handleSubmitError(err);
    }
  };

  return (
    <>
      <ManagementPageBackButton url={presetListURL(targetLocator)} />
      <PresetDetailPane preset={null} targetLocator={targetLocator} isNew onSubmit={createPreset} />
    </>
  );
}

export default function PresetManagement({initialState, targetLocator}) {
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
            path={routerPathFromFlask(presetNewURL, targetIdParams)}
            render={() => <PresetCreateRoute dispatch={dispatch} targetLocator={targetLocator} />}
          />
          <Route
            exact
            path={routerPathFromFlask(presetDetailURL, [...targetIdParams, 'preset_id'])}
            render={() => (
              <PresetEditRoute
                presets={state.ownPresets}
                dispatch={dispatch}
                targetLocator={targetLocator}
              />
            )}
          />
          <Route
            exact
            path={routerPathFromFlask(presetListURL, targetIdParams)}
            render={() => (
              <PresetListPane dispatch={dispatch} targetLocator={targetLocator} {...state} />
            )}
          />
        </Switch>
      </Router>
    </>
  );
}

PresetEditRoute.propTypes = {
  presets: PropTypes.array.isRequired,
  dispatch: PropTypes.func.isRequired,
  targetLocator: PropTypes.object.isRequired,
};

PresetCreateRoute.propTypes = {
  dispatch: PropTypes.func.isRequired,
  targetLocator: PropTypes.object.isRequired,
};

PresetManagement.propTypes = {
  initialState: PropTypes.shape({
    ownPresets: PropTypes.array,
    inheritedPresets: PropTypes.array,
    defaultPresetId: PropTypes.number,
    explicitDefaultPresetId: PropTypes.number,
  }).isRequired,
  targetLocator: PropTypes.object.isRequired,
};
