// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import {Translate} from 'indico/react/i18n';

import RepresentationInput, {RepresentationSettings} from './RepresentationInput';

const representationField = {
  name: 'ext__representation',
  title: Translate.string('Representation'),
  icon: 'id-badge',
  inputComponent: RepresentationInput,
  settingsComponent: RepresentationSettings,
};

export default representationField;
