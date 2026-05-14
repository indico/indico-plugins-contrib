// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import inviteByAffiliationURL from 'indico-url:plugin_affiliation_extras.api_invite_by_affiliation';
import userCountByIdsURL from 'indico-url:plugin_affiliation_extras.api_affiliation_user_count_by_ids';

import React from 'react';

import {Param, Plural, PluralTranslate, Singular} from 'indico/react/i18n';

import FinalAffiliationList from '../components/AffiliationListField';

const AffiliationField = ({eventId, regformId}) => {
  const countURL = userCountByIdsURL({event_id: eventId, reg_form_id: regformId});
  const renderItemExtra = item =>
    item.extraInfo !== undefined
      ? React.createElement(
          React.Fragment,
          null,
          ' (',
          React.createElement(
            PluralTranslate,
            {count: item.extraInfo},
            React.createElement(
              Singular,
              null,
              React.createElement(Param, {name: 'count', value: item.extraInfo}),
              ' user'
            ),
            React.createElement(
              Plural,
              null,
              React.createElement(Param, {name: 'count', value: item.extraInfo}),
              ' users'
            )
          ),
          ')'
        )
      : null;

  return React.createElement(FinalAffiliationList, {
    name: 'affiliations',
    showExtraInfo: true,
    extraInfoURL: countURL,
    renderItemExtra,
  });
};

const affiliationInvitations = {
  key: 'affiliations',
  buttonLabel: 'Affiliations',
  Component: AffiliationField,
  extraFields: ['affiliations'],
  initialValues: {affiliations: {affiliations: [], groups: [], tags: [], _extraInfo: null}},
  getCount: ({affiliations: v}) => {
    if (!v || Array.isArray(v)) {
      return 0;
    }
    const rowCount =
      (v.affiliations?.length ?? 0) + (v.groups?.length ?? 0) + (v.tags?.length ?? 0);
    if (rowCount === 0) {
      return 0;
    }
    return v._extraInfo ?? rowCount;
  },
  getSubmitURL: ({eventId, regformId}) =>
    inviteByAffiliationURL({event_id: eventId, reg_form_id: regformId}),
};

export default affiliationInvitations;
