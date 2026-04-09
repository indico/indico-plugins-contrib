// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import React from 'react';
import ReactDOM from 'react-dom';

import PresetManagement from './PresetManagement';

export default function setupAffiliationPresets(
  elem,
  ownPresets,
  inheritedPresets,
  defaultPresetId,
  explicitDefaultPresetId,
  targetLocator
) {
  ReactDOM.render(
    <PresetManagement
      initialState={{ownPresets, inheritedPresets, defaultPresetId, explicitDefaultPresetId}}
      targetLocator={targetLocator}
    />,
    elem
  );
}
