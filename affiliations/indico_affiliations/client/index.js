// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import {registerPluginComponent, registerPluginObject} from 'indico/utils/plugins';

import AffiliationDashboardActions from './dashboard/AffiliationDashboardActions';
import dashboardColumns from './dashboard/columns';
import formSection from './dashboard/formSection';
import affiliationFilters from './dashboard/filters';
import AffiliationRowActions from './dashboard/AffiliationRowActions';

const PLUGIN_NAME = 'affiliations';

registerPluginObject(PLUGIN_NAME, 'affiliations-dashboard-columns', dashboardColumns);
registerPluginObject(PLUGIN_NAME, 'affiliation-form-sections', formSection);
registerPluginObject(PLUGIN_NAME, 'affiliations-dashboard-filter-extensions', affiliationFilters);

registerPluginComponent(
  PLUGIN_NAME,
  'affiliation-dashboard-extra-actions',
  AffiliationDashboardActions
);
registerPluginComponent(PLUGIN_NAME, 'affiliation-dashboard-row-actions', AffiliationRowActions);
