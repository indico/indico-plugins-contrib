// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import React, {useState} from 'react';
import {Icon} from 'semantic-ui-react';

import {Translate} from 'indico/react/i18n';

import {ExtendedAffiliation} from './types';
import EmailAffiliations from './EmailAffiliations';

export default function AffiliationRowActions({affiliation}: {affiliation: ExtendedAffiliation}) {
  const [modalOpen, setModalOpen] = useState<string | null>(null);
  const openModal = (modal: string) => () => setModalOpen(modal);
  const closeModal = () => setModalOpen(null);

  const modal = {
    email: <EmailAffiliations affiliations={[affiliation]} onClose={closeModal} />,
  }[modalOpen];

  return (
    <>
      <Icon
        name="mail"
        link={affiliation.contact_emails.length > 0}
        title={Translate.string('Email representatives')}
        color="grey"
        onClick={openModal('email')}
        disabled={affiliation.contact_emails.length === 0}
      />
      {modal}
    </>
  );
}
