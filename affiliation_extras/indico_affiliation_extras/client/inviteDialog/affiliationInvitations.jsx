// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import affiliationGroupsURL from 'indico-url:plugin_affiliation_extras.api_reg_form_affiliation_groups';
import affiliationCountriesURL from 'indico-url:plugin_affiliation_extras.api_reg_form_countries';
import searchAffiliationsURL from 'indico-url:plugin_affiliation_extras.api_reg_form_search_affiliations';
import affiliationTagsURL from 'indico-url:plugin_affiliation_extras.api_reg_form_affiliation_tags';
import affiliationUserCountURL from 'indico-url:plugin_affiliation_extras.api_affiliation_user_count';
import inviteByAffiliationURL from 'indico-url:plugin_affiliation_extras.api_invite_by_affiliation';

import React from 'react';

import {Param, Plural, PluralTranslate, Singular, Translate} from 'indico/react/i18n';

import FinalAffiliationList from '../components/AffiliationListField';

const AffiliationField = ({eventId, regformId}) => {
  const regformLocator = {event_id: eventId, reg_form_id: regformId};
  const countURL = affiliationUserCountURL({event_id: eventId, reg_form_id: regformId});
  const groupsURL = affiliationGroupsURL(regformLocator);
  const tagsURL = affiliationTagsURL(regformLocator);
  const searchURL = searchAffiliationsURL(regformLocator);
  const countriesURL = affiliationCountriesURL(regformLocator);
  const renderItemExtra = item =>
    item.extraInfo !== undefined ? (
      <>
        {' ('}
        <PluralTranslate count={item.extraInfo}>
          <Singular>
            <Param name="count" value={item.extraInfo} /> user
          </Singular>
          <Plural>
            <Param name="count" value={item.extraInfo} /> users
          </Plural>
        </PluralTranslate>
        {')'}
      </>
    ) : null;

  return (
    <FinalAffiliationList
      name="affiliations"
      showExtraInfo
      groupsURL={groupsURL}
      tagsURL={tagsURL}
      searchURL={searchURL}
      countriesURL={countriesURL}
      userCountURL={countURL}
      renderItemExtra={renderItemExtra}
    />
  );
};

const affiliationInvitations = {
  key: 'affiliations',
  buttonLabel: Translate.string('Affiliations'),
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
