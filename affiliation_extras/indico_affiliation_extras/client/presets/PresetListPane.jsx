// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import deletePresetURL from 'indico-url:plugin_affiliation_extras.api_delete_preset';
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

function PresetRow({preset, dispatch, setDeletePrompt, targetLocator, inherited}) {
  const deletePreset = async () => {
    try {
      await indicoAxios.delete(deletePresetURL({preset_id: preset.id, ...targetLocator}));
      dispatch({type: 'DELETE_PRESET', id: preset.id});
    } catch (err) {
      handleAxiosError(err);
      return true;
    }
  };

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
        {!inherited && (
          <div className="thin toolbar right">
            <Link
              to={presetDetailURL({preset_id: preset.id, ...targetLocator})}
              onClick={evt => evt.target.dispatchEvent(new Event('indico:closeAutoTooltip'))}
            >
              <Icon name="edit" color="blue" title={Translate.string('Edit preset')} />
            </Link>
            <Icon
              name="trash"
              color="red"
              title={Translate.string('Delete preset')}
              onClick={evt => {
                evt.target.dispatchEvent(new Event('indico:closeAutoTooltip'));
                setDeletePrompt({
                  name: preset.name,
                  func: deletePreset,
                });
              }}
            />
          </div>
        )}
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
};

PresetRow.defaultProps = {
  inherited: false,
  setDeletePrompt: null,
};

export default function PresetListPane({ownPresets, inheritedPresets, targetLocator, dispatch}) {
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
};
