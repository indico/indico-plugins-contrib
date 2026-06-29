// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import focalPointInviteMetadataURL from 'indico-url:plugin_affiliation_extras.api_focal_point_invite_metadata';
import inviteFocalPointsURL from 'indico-url:plugin_affiliation_extras.api_invite_focal_points';

import React, {useEffect} from 'react';
import {useForm} from 'react-final-form';
import {Icon, Loader, Message} from 'semantic-ui-react';

import {useIndicoAxios} from 'indico/react/hooks';
import {Param, Plural, PluralTranslate, Singular, Translate} from 'indico/react/i18n';

const FocalPointsField = ({eventId, regformId}) => {
  const form = useForm();
  const {data, loading} = useIndicoAxios(
    focalPointInviteMetadataURL({event_id: eventId, reg_form_id: regformId}),
    {camelize: true}
  );

  useEffect(() => {
    if (data) {
      form.change('focal_points', data);
    }
  }, [data, form]);

  if (loading || !data) {
    return <Loader active inline="centered" />;
  }

  if (!data.focalPointCount) {
    return (
      <Message warning icon>
        <Icon name="info circle" />
        <Message.Content>
          <Translate as={Message.Header}>No focal points found</Translate>
          <Translate as="p">
            No focal points were found for affiliations in this event catalog.
          </Translate>
        </Message.Content>
      </Message>
    );
  }

  return (
    <Message info icon>
      <Icon name="users" />
      <Message.Content>
        <PluralTranslate as={Message.Header} count={data.focalPointCount}>
          <Singular>
            <Param name="count" value={data.focalPointCount} /> focal point will be invited.
          </Singular>
          <Plural>
            <Param name="count" value={data.focalPointCount} /> focal points will be invited.
          </Plural>
        </PluralTranslate>
        <PluralTranslate as="p" count={data.affiliationCount}>
          <Singular>
            This is based on <Param name="count" value={data.affiliationCount} /> catalog
            affiliation.
          </Singular>
          <Plural>
            This is based on <Param name="count" value={data.affiliationCount} /> catalog
            affiliations.
          </Plural>
        </PluralTranslate>
        <Translate as="p">Existing invitations and registrations will be skipped.</Translate>
      </Message.Content>
    </Message>
  );
};

const focalPointInvitations = {
  key: 'focal_points',
  buttonLabel: 'Focal points',
  Component: FocalPointsField,
  extraFields: ['focal_points'],
  initialValues: {focal_points: {focalPointCount: 0, affiliationCount: 0}},
  getCount: ({focal_points: focalPoints}) => focalPoints?.focalPointCount ?? 0,
  getSubmitURL: ({eventId, regformId}) =>
    inviteFocalPointsURL({event_id: eventId, reg_form_id: regformId}),
};

export default focalPointInvitations;
