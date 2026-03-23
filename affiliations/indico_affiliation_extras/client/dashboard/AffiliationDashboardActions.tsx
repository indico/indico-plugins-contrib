// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import React, {useState} from 'react';
import {Button, Dropdown} from 'semantic-ui-react';

import {Translate} from 'indico/react/i18n';

import ItemManagerModal from '../components/ItemManagerModal';
import TagManager from './TagManager';
import GroupManager from './GroupManager';
import EmailAffiliations from './EmailAffiliations';
import {ExtendedAffiliation} from './types';

export default function AffiliationDashboardActions({
  affiliations,
  visibleAffiliations,
}: {
  affiliations: ExtendedAffiliation[];
  visibleAffiliations: ExtendedAffiliation[];
}) {
  const [modalOpen, setModalOpen] = useState<string | null>(null);
  const openModal = (modal: string) => () => setModalOpen(modal);
  const closeModal = () => setModalOpen(null);

  const modal = {
    groups: (
      <ItemManagerModal
        header={Translate.string('Manage affiliation groups')}
        onClose={closeModal}
        itemManager={GroupManager}
      />
    ),
    tags: (
      <ItemManagerModal
        header={Translate.string('Manage affiliation tags')}
        onClose={closeModal}
        itemManager={TagManager}
      />
    ),
    'email-repr-all': <EmailAffiliations affiliations={affiliations} onClose={closeModal} />,
    'email-repr-filtered': (
      <EmailAffiliations affiliations={visibleAffiliations} onClose={closeModal} />
    ),
  }[modalOpen];

  return (
    <>
      <Button.Group>
        <Button
          type="button"
          icon="object group"
          content={Translate.string('Groups')}
          onClick={openModal('groups')}
        />
        <Button
          type="button"
          icon="tags"
          content={Translate.string('Tags')}
          onClick={openModal('tags')}
        />
      </Button.Group>
      <Dropdown
        icon={null}
        trigger={
          <Button type="button" icon="mail" content={Translate.string('Email representatives')} />
        }
        disabled={affiliations.length === 0}
        floating
      >
        <Dropdown.Menu>
          <Dropdown.Item
            text={Translate.string('All affiliations')}
            description={`(${affiliations.length})`}
            disabled={affiliations.length === 0}
            onClick={openModal('email-repr-all')}
          />
          <Dropdown.Item
            text={Translate.string('Filtered affiliations')}
            description={`(${visibleAffiliations.length}/${affiliations.length})`}
            disabled={
              visibleAffiliations.length === 0 || visibleAffiliations.length === affiliations.length
            }
            onClick={openModal('email-repr-filtered')}
          />
        </Dropdown.Menu>
      </Dropdown>
      {modal}
    </>
  );
}
