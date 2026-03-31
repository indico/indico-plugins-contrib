// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import {Affiliation} from 'indico/modules/users/affiliations/types';

export function getAffiliationSubheader(affiliation: Affiliation) {
  const city = affiliation.city;
  const country = affiliation.country_name;
  if (city && country) {
    return `${city}, ${country}`;
  }
  return city || country || undefined;
}
