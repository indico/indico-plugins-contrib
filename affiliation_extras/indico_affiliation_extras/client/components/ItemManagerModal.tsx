// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import React, {useCallback, useState} from 'react';
import {Button, Modal} from 'semantic-ui-react';

import {Translate} from 'indico/react/i18n';

export default function ItemManagerModal({
  header,
  onClose,
  itemManager: Component,
}: {
  header: string;
  onClose: () => void;
  itemManager: React.ComponentType<{addButtonContainer?: Element}>;
}) {
  const [addButtonContainer, setAddButtonContainer] = useState<HTMLElement | null>(null);
  const addButtonContainerRef = useCallback(
    (node: HTMLElement | null) => {
      if (node && node !== addButtonContainer) {
        setAddButtonContainer(node);
      }
    },
    [addButtonContainer]
  );

  return (
    <Modal open onClose={onClose} size="tiny" closeIcon>
      <Modal.Header>{header}</Modal.Header>
      <Modal.Content style={{overflowY: 'auto', maxHeight: '80vh'}}>
        <Component addButtonContainer={addButtonContainer} />
      </Modal.Content>
      <Modal.Actions>
        <span ref={addButtonContainerRef} />
        <Button onClick={onClose} content={Translate.string('Close')} />
      </Modal.Actions>
    </Modal>
  );
}
