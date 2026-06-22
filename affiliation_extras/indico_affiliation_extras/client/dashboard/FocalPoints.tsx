// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import focalPointsURL from 'indico-url:plugin_affiliation_extras.api_affiliation_focal_points';

import _ from 'lodash';
import React from 'react';
import {Loader} from 'semantic-ui-react';

import {FinalPrincipalList} from 'indico/react/components';
import {handleSubmitError} from 'indico/react/forms';
import {FinalModalForm} from 'indico/react/forms/final-form';
import {useFavoriteUsers, useIndicoAxios} from 'indico/react/hooks';
import {Translate} from 'indico/react/i18n';
import {indicoAxios} from 'indico/utils/axios';

import {ExtendedAffiliation} from '../types';

interface FocalPointsFormValues {
  focal_points: string[];
}

export default function FocalPoints({
  affiliation,
  onClose,
}: {
  affiliation: ExtendedAffiliation;
  onClose: () => void;
}) {
  const favoriteUsersController = useFavoriteUsers();
  const url = focalPointsURL({affiliation_id: affiliation.id});
  const {data: focalPoints, loading} = useIndicoAxios<string[]>(url);

  const handleSubmit = async ({focal_points}: FocalPointsFormValues) => {
    try {
      await indicoAxios.patch(url, {focal_points});
    } catch (error) {
      return handleSubmitError(error);
    }
    onClose();
  };

  if (loading || !focalPoints) {
    return <Loader active />;
  }

  return (
    <FinalModalForm
      id="affiliation-focal-points"
      size="small"
      onSubmit={handleSubmit}
      onClose={onClose}
      header={Translate.string('Focal points for "{name}"', {name: affiliation.name})}
      submitLabel={Translate.string('Save')}
      initialValues={{focal_points: focalPoints}}
      initialValuesEqual={_.isEqual}
      disabledUntilChange
    >
      <FinalPrincipalList
        name="focal_points"
        favoriteUsersController={favoriteUsersController}
        label={Translate.string('Focal points')}
      />
    </FinalModalForm>
  );
}
