// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import emailMetadataURL from 'indico-url:plugin_affiliations.email_representatives_metadata';
import emailSendURL from 'indico-url:plugin_affiliations.email_representatives_send';
import emailPreviewURL from 'indico-url:plugin_affiliations.email_representatives_preview';
import emailImageUploadURL from 'indico-url:plugin_affiliations.email_representatives_image_upload';

import {AxiosResponse} from 'axios';
import React from 'react';
import {Dimmer, Loader, Message, Form, Modal, List, Accordion} from 'semantic-ui-react';

import {EmailDialog} from 'indico/modules/events/persons/EmailDialog';
import indicoAxios from 'indico/utils/axios';
import {handleSubmitError} from 'indico/react/forms';
import {Param, Plural, PluralTranslate, Singular, Translate} from 'indico/react/i18n';
import {useIndicoAxios} from 'indico/react/hooks';

import {ExtendedAffiliation} from './types';

import './EmailAffiliations.module.scss';

const SUCCESS_TIMEOUT = 5000;

function RecipientsList({
  affiliations,
  invalidAffiliations,
  recipientsCount,
}: {
  affiliations: ExtendedAffiliation[];
  invalidAffiliations: Map<number, string[]>;
  recipientsCount: number;
}) {
  const title = (
    <PluralTranslate count={recipientsCount}>
      <Singular>
        <Param name="count" value={recipientsCount} /> recipient will receive this email.
      </Singular>
      <Plural>
        <Param name="count" value={recipientsCount} /> recipients will receive this email.
      </Plural>
    </PluralTranslate>
  );

  const content = (
    <List celled>
      {affiliations.map((affiliation: ExtendedAffiliation) => {
        const hasEmails = affiliation.contact_emails.length > 0;
        const invalidEmails = invalidAffiliations.get(affiliation.id) || [];
        const hasValidEmails =
          hasEmails && affiliation.contact_emails.some(email => !invalidEmails.includes(email));
        return (
          <List.Item
            key={affiliation.id}
            icon={
              hasValidEmails && !invalidEmails.length
                ? 'group'
                : {name: 'warning sign', color: hasValidEmails ? 'orange' : 'red'}
            }
            content={
              <>
                <List.Header
                  styleName={
                    hasValidEmails && !invalidEmails.length
                      ? undefined
                      : hasValidEmails
                        ? 'warning'
                        : 'error'
                  }
                >
                  {affiliation.name}
                </List.Header>
                {!hasEmails ? (
                  <Translate as={List.Description}>
                    This affiliation has no contact emails.
                  </Translate>
                ) : (
                  <>
                    {invalidAffiliations.has(affiliation.id) && (
                      <Translate as={List.Description}>
                        This affiliation has one or more invalid contact emails.
                      </Translate>
                    )}
                    <List.List>
                      {affiliation.contact_emails.map(email => (
                        <List.Item
                          key={email}
                          className="mono"
                          styleName={invalidEmails.includes(email) ? 'error' : undefined}
                        >
                          {email}
                        </List.Item>
                      ))}
                    </List.List>
                  </>
                )}
              </>
            }
          />
        );
      })}
    </List>
  );

  return (
    <Accordion
      panels={[
        {
          key: 'recipients',
          title: {content: title},
          content: {content},
        },
      ]}
      fluid
    />
  );
}

export default function EmailAffiliations({
  affiliations,
  onClose,
}: {
  affiliations: ExtendedAffiliation[];
  onClose: () => void;
}) {
  const recipientData = {
    affiliation_ids: affiliations.map(a => a.id),
  };
  const {data, loading} = useIndicoAxios(
    {
      url: emailMetadataURL({}),
      method: 'POST',
      data: recipientData,
    },
    {camelize: true}
  );
  const {
    senders = [],
    recipientsCount = 0,
    invalidAffiliations: _invalidAffiliations = [],
    placeholders = [],
  } = data || {};
  const invalidAffiliations = new Map<number, string[]>(
    _invalidAffiliations.map(({id, invalidEmails}: {id: number; invalidEmails: string[]}) => [
      id,
      invalidEmails,
    ])
  );

  const handleSubmit = async data => {
    const requestData = {...data, ...recipientData};
    let resp: AxiosResponse;
    try {
      resp = await indicoAxios.post(emailSendURL({}), requestData);
    } catch (err) {
      return handleSubmitError(err);
    }
    setTimeout(() => onClose(), SUCCESS_TIMEOUT);
  };

  const affiliationsWithoutEmails = affiliations.reduce(
    (n, a) => n + (a.contact_emails.length === 0 ? 1 : 0),
    0
  );

  if (loading) {
    return (
      <Dimmer active page inverted>
        <Loader />
      </Dimmer>
    );
  }

  if (recipientsCount === 0) {
    return (
      <Modal
        open
        onClose={onClose}
        size="small"
        icon="warning sign"
        header={Translate.string('No valid recipient emails')}
        content={
          <Modal.Content>
            <Message
              error
              icon="warning sign"
              content={PluralTranslate.string(
                'The selected affiliation does not have valid contact emails. Please add contact emails to the affiliation before trying to send emails.',
                'None of the selected affiliations have valid contact emails. Please add contact emails to the affiliations before trying to send emails.',
                affiliations.length
              )}
            />
            {invalidAffiliations.size > 0 && affiliations.length > 1 && (
              <>
                <PluralTranslate as="p" count={invalidAffiliations.size}>
                  <Singular>The following affiliation has invalid contact emails:</Singular>
                  <Plural>The following affiliations have invalid contact emails:</Plural>
                </PluralTranslate>
                <List bulleted>
                  {[...invalidAffiliations.entries()].map(([aid, emails]) => (
                    <List.Item key={aid}>
                      {affiliations.find(a => a.id === aid)?.name}
                      <List.List>
                        {emails.map((email: string) => (
                          <List.Item key={email} className="mono">
                            {email}
                          </List.Item>
                        ))}
                      </List.List>
                    </List.Item>
                  ))}
                </List>
              </>
            )}
          </Modal.Content>
        }
        actions={[{key: 'close', content: Translate.string('Close'), onClick: onClose}]}
      />
    );
  }

  return (
    <EmailDialog
      title={Translate.string('Email affiliation representatives')}
      onClose={onClose}
      onSubmit={handleSubmit}
      senders={senders}
      previewURL={emailPreviewURL({})}
      previewContext={recipientData}
      placeholders={placeholders}
      imageUploadURL={emailImageUploadURL({})}
      sentEmailsCount={recipientsCount}
      recipientsField={
        <>
          {invalidAffiliations.size > 0 ? (
            <Message
              warning
              icon="warning sign"
              header={Translate.string('Some affiliations have invalid contact emails')}
              list={[...invalidAffiliations.keys()].map(
                aid => affiliations.find(a => a.id === aid)?.name
              )}
            />
          ) : (
            affiliationsWithoutEmails > 0 && (
              <Message
                visible
                warning
                icon="warning sign"
                header={Translate.string('{count} affiliations do not have contact emails.', {
                  count: affiliationsWithoutEmails,
                })}
                content={Translate.string(
                  'These affiliations will be skipped when sending emails. You can use the "Representation" filter to list these affiliations.'
                )}
              />
            )
          )}
          <Form.Field>
            <Translate as="label">Recipients</Translate>
            <RecipientsList
              affiliations={affiliations}
              invalidAffiliations={invalidAffiliations}
              recipientsCount={recipientsCount}
            />
          </Form.Field>
        </>
      }
      recipientsFirst
    />
  );
}
