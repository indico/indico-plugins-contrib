// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import clonePresetURL from 'indico-url:plugin_affiliation_extras.api_clone_preset';
import deletePresetURL from 'indico-url:plugin_affiliation_extras.api_delete_preset';
import toggleDefaultPresetURL from 'indico-url:plugin_affiliation_extras.api_toggle_default_preset';
import presetDetailURL from 'indico-url:plugin_affiliation_extras.category_preset_detail';
import presetListURL from 'indico-url:plugin_affiliation_extras.manage_category_affiliations';
import presetNewURL from 'indico-url:plugin_affiliation_extras.create_category_preset';

import _ from 'lodash';
import PropTypes from 'prop-types';
import React, {useState} from 'react';
import {Link} from 'react-router-dom';
import {Button, Icon} from 'semantic-ui-react';

import {RequestConfirmDelete} from 'indico/react/components';
import {Param, Translate} from 'indico/react/i18n';
import {handleAxiosError, indicoAxios} from 'indico/utils/axios';

import './PresetListPane.module.scss';

function PresetRow({
  preset,
  dispatch,
  setDeletePrompt,
  targetLocator,
  inherited,
  defaultPresetId,
  explicitDefaultPresetId,
}) {
  const isDefault = preset.id === defaultPresetId;
  const isInheritedDefault = isDefault && preset.id !== explicitDefaultPresetId;
  const deletePreset = async () => {
    try {
      await indicoAxios.delete(deletePresetURL({preset_id: preset.id, ...targetLocator}));
      dispatch({type: 'DELETE_PRESET', id: preset.id});
    } catch (err) {
      handleAxiosError(err);
      return true;
    }
  };

  const clonePreset = async evt => {
    evt.target.dispatchEvent(new Event('indico:closeAutoTooltip'));
    try {
      const {data: clonedPreset} = await indicoAxios.post(
        clonePresetURL({preset_id: preset.id, ...targetLocator})
      );
      dispatch({type: 'ADD_PRESET', preset: clonedPreset});
    } catch (err) {
      handleAxiosError(err);
    }
  };

  const toggleDefaultPreset = async evt => {
    evt.target.dispatchEvent(new Event('indico:closeAutoTooltip'));
    try {
      const {data} = await indicoAxios.post(
        toggleDefaultPresetURL({preset_id: preset.id, ...targetLocator})
      );
      dispatch({
        type: 'SET_DEFAULT_PRESET',
        defaultPresetId: data.default_preset_id,
        explicitDefaultPresetId: data.explicit_default_preset_id,
      });
    } catch (err) {
      handleAxiosError(err);
    }
  };

  const openDeletePrompt = evt => {
    evt.target.dispatchEvent(new Event('indico:closeAutoTooltip'));
    setDeletePrompt({name: preset.name, func: deletePreset});
  };

  const defaultTitle = isInheritedDefault
    ? Translate.string('This is the inherited default preset')
    : isDefault
      ? Translate.string('Clear default preset')
      : Translate.string('Set as default preset');

  return (
    <tr>
      <td>
        {inherited ? (
          preset.name
        ) : (
          <Link to={presetDetailURL({preset_id: preset.id, ...targetLocator})}>{preset.name}</Link>
        )}
      </td>
      <td className="text-superfluous">
        {inherited && preset.owner && (
          <Translate>
            from category{' '}
            <Param
              name="title"
              value={preset.owner.title}
              wrapper={<a href={presetListURL(preset.owner.locator)} />}
            />
          </Translate>
        )}
      </td>
      <td styleName="preset-actions">
        <div className="thin toolbar right">
          <Icon
            name="pin"
            color={isDefault ? 'blue' : 'grey'}
            title={defaultTitle}
            disabled={isInheritedDefault}
            onClick={toggleDefaultPreset}
          />
          {!inherited && (
            <Link to={presetDetailURL({preset_id: preset.id, ...targetLocator})}>
              <Icon name="edit" color="blue" title={Translate.string('Edit preset')} />
            </Link>
          )}
          <Icon
            name="clone"
            color="blue"
            title={Translate.string('Clone preset')}
            onClick={clonePreset}
          />
          {!inherited && (
            <Icon
              name="trash"
              color="red"
              title={Translate.string('Delete preset')}
              onClick={openDeletePrompt}
            />
          )}
        </div>
      </td>
    </tr>
  );
}

PresetRow.propTypes = {
  preset: PropTypes.object.isRequired,
  dispatch: PropTypes.func.isRequired,
  setDeletePrompt: PropTypes.func,
  targetLocator: PropTypes.object.isRequired,
  inherited: PropTypes.bool,
  defaultPresetId: PropTypes.number,
  explicitDefaultPresetId: PropTypes.number,
};

PresetRow.defaultProps = {
  inherited: false,
  setDeletePrompt: null,
  defaultPresetId: null,
  explicitDefaultPresetId: null,
};

export default function PresetListPane({
  ownPresets,
  inheritedPresets,
  targetLocator,
  dispatch,
  defaultPresetId,
  explicitDefaultPresetId,
}) {
  const [deletePrompt, setDeletePrompt] = useState(null);

  return (
    <div styleName="preset-list">
      <RequestConfirmDelete
        onClose={() => setDeletePrompt(null)}
        requestFunc={deletePrompt?.func || (() => null)}
        open={deletePrompt !== null}
      >
        <Translate>
          Are you sure you want to delete the preset{' '}
          <Param name="name" value={deletePrompt?.name} wrapper={<strong />} />?
        </Translate>
      </RequestConfirmDelete>

      {!!inheritedPresets.length && (
        <section>
          <h3>
            <Translate>Inherited presets</Translate>
          </h3>
          <table className="i-table-widget">
            <tbody>
              {_.sortBy(inheritedPresets, 'name').map(preset => (
                <PresetRow
                  key={preset.id}
                  preset={preset}
                  dispatch={dispatch}
                  targetLocator={targetLocator}
                  inherited
                  defaultPresetId={defaultPresetId}
                  explicitDefaultPresetId={explicitDefaultPresetId}
                />
              ))}
            </tbody>
          </table>
        </section>
      )}

      <section>
        <div className="flexrow f-a-center f-j-space-between">
          <h3>
            <Translate>Presets</Translate>
          </h3>
          <Button
            as={Link}
            to={presetNewURL(targetLocator)}
            icon="plus"
            content={Translate.string('Add new preset')}
            className="mini primary icon"
          />
        </div>
        {ownPresets.length ? (
          <table className="i-table-widget">
            <tbody>
              {_.sortBy(ownPresets, 'name').map(preset => (
                <PresetRow
                  key={preset.id}
                  preset={preset}
                  dispatch={dispatch}
                  setDeletePrompt={setDeletePrompt}
                  targetLocator={targetLocator}
                  defaultPresetId={defaultPresetId}
                  explicitDefaultPresetId={explicitDefaultPresetId}
                />
              ))}
            </tbody>
          </table>
        ) : (
          <Translate as="div" className="italic text-not-important">
            No presets
          </Translate>
        )}
      </section>
    </div>
  );
}

PresetListPane.propTypes = {
  ownPresets: PropTypes.array.isRequired,
  inheritedPresets: PropTypes.array.isRequired,
  targetLocator: PropTypes.object.isRequired,
  dispatch: PropTypes.func.isRequired,
  defaultPresetId: PropTypes.number,
  explicitDefaultPresetId: PropTypes.number,
};
