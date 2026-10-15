// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import React from 'react';
import {Button, DropdownProps, Label, Popup} from 'semantic-ui-react';

import {EmailListField} from 'indico/react/components';
import {Translate} from 'indico/react/i18n';

import './ContactEmailListField.module.scss';

export default function ContactEmailListField({
  value,
  inactiveEmails = [],
  onChange,
  onInactiveEmailsChange,
}: {
  value: string[];
  inactiveEmails?: string[];
  onChange: (value: string[]) => void;
  onInactiveEmailsChange: (value: string[]) => void;
}) {
  const inactiveEmailSet = new Set(inactiveEmails);

  const toggleInactiveEmail = (email: string) => {
    if (inactiveEmailSet.has(email)) {
      onInactiveEmailsChange(inactiveEmails.filter(x => x !== email));
    } else {
      onInactiveEmailsChange([...inactiveEmails, email]);
    }
  };

  const handleToggleInactiveEmail = (event: React.MouseEvent<HTMLElement>, email: string) => {
    event.stopPropagation();
    toggleInactiveEmail(email);
  };

  const renderLabel: DropdownProps['renderLabel'] = (item, index, defaultLabelProps) => {
    const email = item.value as string;
    const inactive = inactiveEmailSet.has(email);
    return (
      <Label
        {...defaultLabelProps}
        as="span"
        basic={inactive}
        styleName={inactive ? 'inactive-email' : undefined}
        content={
          <>
            <span>{item.text}</span>
            <Popup
              content={
                inactive ? Translate.string('Enable email') : Translate.string('Disable email')
              }
              trigger={
                <Button
                  type="button"
                  icon={inactive ? 'check' : 'ban'}
                  aria-label={
                    inactive
                      ? Translate.string('Enable email {email}', {email})
                      : Translate.string('Disable email {email}', {email})
                  }
                  toggle
                  active={inactive}
                  onClick={event => handleToggleInactiveEmail(event, email)}
                  // Dropdown focus handling would move focus back to its search input.
                  onFocus={event => event.stopPropagation()}
                  // Dropdown shortcuts would intercept Enter/Space meant to activate this button.
                  onKeyDown={event => event.stopPropagation()}
                  styleName="toggle-inactive-email"
                />
              }
            />
          </>
        }
      />
    );
  };

  return <EmailListField value={value} onChange={onChange} renderLabel={renderLabel} />;
}
