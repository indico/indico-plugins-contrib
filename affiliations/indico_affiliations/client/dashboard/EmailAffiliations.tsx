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
import React, {useState, useMemo} from 'react';
import {Message, Dimmer, Loader, Modal, List, Accordion} from 'semantic-ui-react';
import {FormSpy, Field, useForm} from 'react-final-form';

import {EmailDialog} from 'indico/modules/events/persons/EmailDialog';
import indicoAxios from 'indico/utils/axios';
import {FinalCheckbox, FinalDropdown, handleSubmitError} from 'indico/react/forms';
import {Plural, PluralTranslate, Singular, Translate} from 'indico/react/i18n';
import {useIndicoAxios} from 'indico/react/hooks';

import {ExtendedAffiliation} from './types';

import './EmailAffiliations.module.scss';
import {ContactList} from '../components/ContactListField';

const SUCCESS_TIMEOUT = 5000;

const filterContactLists = (
  affiliation: ExtendedAffiliation,
  contactLists: string[],
  includeUnnamedLists: boolean
) =>
  affiliation.contacts.filter(
    ({name}: ContactList) =>
      contactLists.length === 0 ||
      contactLists.includes(name) ||
      (includeUnnamedLists && name === '')
  );

const getAffiliationEmails = (
  affiliation: ExtendedAffiliation,
  contactLists: string[] = [],
  includeUnnamedLists: boolean = true
) =>
  Array.from(
    new Set(
      filterContactLists(affiliation, contactLists, includeUnnamedLists).flatMap(
        contactList => contactList.emails
      )
    )
  );

function RecipientsField({contactListOptions}: {contactListOptions: string[]}) {
  const form = useForm();
  return (
    <>
      <FinalDropdown
        name="contact_lists"
        label={Translate.string('Recipients')}
        placeholder={Translate.string('Send to all contact lists')}
        options={contactListOptions?.map((name: string) => ({value: name, text: name})) ?? []}
        disabled={!contactListOptions?.length}
        onChange={value => {
          if (value.length === 0) {
            form.change('include_unnamed_lists', true);
          }
        }}
        selection
        multiple
        fluid
      />
      <Field name="contact_lists" subscription={{value: true}}>
        {({input: {value: contactLists}}) => (
          <FinalCheckbox
            name="include_unnamed_lists"
            label={Translate.string('Send to contacts in unnamed lists')}
            disabled={!contactListOptions?.length || !contactLists.length}
            showAsToggle
          />
        )}
      </Field>
    </>
  );
}

interface RecipientsComponentProps {
  affiliations: ExtendedAffiliation[];
  invalidEmails: Set<string>;
  contactLists: string[];
  includeUnnamedLists: boolean;
}

function RecipientsWarning({
  affiliations,
  invalidEmails,
  contactLists,
  includeUnnamedLists,
}: RecipientsComponentProps) {
  const affiliationsWithoutEmails = affiliations.reduce(
    (n, a) => n + (filterContactLists(a, contactLists, includeUnnamedLists).length === 0 ? 1 : 0),
    0
  );
  return (
    <>
      {affiliationsWithoutEmails > 0 && (
        <Message
          visible
          warning
          icon="warning sign"
          header={
            contactLists.length > 0
              ? PluralTranslate.string(
                  '{count} affiliation does not have contact emails for the selected lists.',
                  '{count} affiliations do not have contact emails for the selected lists.',
                  affiliationsWithoutEmails,
                  {
                    count: affiliationsWithoutEmails,
                  }
                )
              : PluralTranslate.string(
                  '{count} affiliation does not have contact emails.',
                  '{count} affiliations do not have contact emails.',
                  affiliationsWithoutEmails,
                  {
                    count: affiliationsWithoutEmails,
                  }
                )
          }
          content={PluralTranslate.string(
            'This affiliation will be skipped when sending the emails.',
            'These affiliations will be skipped when sending the emails.',
            affiliationsWithoutEmails
          )}
        />
      )}
      {affiliations.some(a =>
        getAffiliationEmails(a, contactLists, includeUnnamedLists).filter(e => invalidEmails.has(e))
      ) && (
        <Message
          visible
          warning
          icon="warning sign"
          header={Translate.string('Some affiliations have invalid contact emails')}
          content={Translate.string(
            'These email addresses will be skipped when sending the emails.'
          )}
        />
      )}
    </>
  );
}

function RecipientsList({
  affiliations,
  invalidEmails,
  contactLists,
  includeUnnamedLists,
}: RecipientsComponentProps) {
  const affiliationsEmails = new Map<number, string[]>(
    affiliations.map(affiliation => [
      affiliation.id,
      getAffiliationEmails(affiliation, contactLists, includeUnnamedLists),
    ])
  );
  const content = (
    <List celled>
      {affiliations.map(affiliation => {
        const emails = affiliationsEmails.get(affiliation.id);
        const hasInvalidEmails = emails.some(e => invalidEmails.has(e));
        const hasValidEmails = emails.some(e => !invalidEmails.has(e));
        return (
          <List.Item
            key={affiliation.id}
            icon={
              hasValidEmails && !hasInvalidEmails
                ? 'group'
                : {
                    name: 'warning sign',
                    color: hasValidEmails ? 'orange' : 'red',
                  }
            }
            content={
              <>
                <List.Header
                  styleName={
                    hasValidEmails && !hasInvalidEmails
                      ? undefined
                      : hasValidEmails
                        ? 'warning'
                        : 'error'
                  }
                >
                  {affiliation.name}
                </List.Header>
                {emails.length === 0 ? (
                  <List.Description>
                    {contactLists.length > 0
                      ? Translate.string(
                          'This affiliation has no contact emails for the selected lists.'
                        )
                      : Translate.string('This affiliation has no contact emails.')}
                  </List.Description>
                ) : (
                  <>
                    {hasInvalidEmails && (
                      <Translate as={List.Description}>
                        This affiliation has one or more invalid contact emails.
                      </Translate>
                    )}
                    <List.List>
                      {emails.map(email => (
                        <List.Item
                          key={email}
                          className="mono"
                          styleName={invalidEmails.has(email) ? 'error' : undefined}
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

  const count = [...affiliationsEmails.values()].reduce(
    (acc, emails) => acc + emails.reduce((n, e) => n + (invalidEmails.has(e) ? 0 : 1), 0),
    0
  );
  return (
    <Accordion
      panels={[
        {
          key: 'recipients',
          title: {
            content: PluralTranslate.string(
              'This email will be sent to {count} recipient.',
              'This email will be sent to {count} recipients.',
              count,
              {count}
            ),
          },
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
  const [sentCount, setSentCount] = useState(0);
  const [skippedCount, setSkippedCount] = useState(0);
  const recipientData = {affiliation_ids: affiliations.map(a => a.id)};
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
    invalidEmails: _invalidEmails = [],
    contactListOptions = [],
    placeholders = [],
  } = data || {};
  const invalidEmails = useMemo(() => new Set<string>(_invalidEmails), [_invalidEmails]);
  const validEmailsCount = useMemo(
    () =>
      affiliations.reduce(
        (acc, affiliation) =>
          acc + getAffiliationEmails(affiliation).filter(e => !invalidEmails.has(e)).length,
        0
      ),
    [affiliations, invalidEmails]
  );

  const handleSubmit = async data => {
    const requestData = {...data, ...recipientData};
    let resp: AxiosResponse;
    try {
      resp = await indicoAxios.post(emailSendURL({}), requestData);
    } catch (err) {
      return handleSubmitError(err);
    }
    setSentCount(resp.data.count);
    setSkippedCount(resp.data.skipped);
    setTimeout(() => onClose(), SUCCESS_TIMEOUT);
  };

  if (loading) {
    return (
      <Dimmer active page inverted>
        <Loader />
      </Dimmer>
    );
  }

  if (validEmailsCount === 0) {
    const invalidAffiliations = affiliations
      .map(affiliation => ({
        id: affiliation.id,
        name: affiliation.name,
        emails: getAffiliationEmails(affiliation).filter(e => invalidEmails.has(e)),
      }))
      .filter(({emails}) => emails.length > 0);
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
            {invalidAffiliations.length > 0 && affiliations.length > 1 && (
              <>
                <PluralTranslate as="p" count={invalidAffiliations.length}>
                  <Singular>The following affiliation has invalid contact emails:</Singular>
                  <Plural>The following affiliations have invalid contact emails:</Plural>
                </PluralTranslate>
                <List bulleted>
                  {invalidAffiliations.map(({id, name, emails}) => (
                    <List.Item key={id}>
                      {name}
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
        actions={[
          {
            key: 'close',
            content: Translate.string('Close'),
            onClick: onClose,
          },
        ]}
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
      sentEmailsCount={sentCount}
      sentEmailsWarning={
        skippedCount
          ? PluralTranslate.string(
              '{count} affiliation was skipped because it has no valid contact emails.',
              '{count} affiliations were skipped because they have no valid contact emails.',
              skippedCount,
              {count: skippedCount}
            )
          : null
      }
      initialFormValues={{contact_lists: [], include_unnamed_lists: true}}
      recipientsField={
        <>
          <FormSpy subscription={{values: true}}>
            {({values}) => (
              <RecipientsWarning
                affiliations={affiliations}
                invalidEmails={invalidEmails}
                contactLists={values.contact_lists}
                includeUnnamedLists={values.include_unnamed_lists}
              />
            )}
          </FormSpy>
          <RecipientsField contactListOptions={contactListOptions} />
          <FormSpy subscription={{values: true}}>
            {({values}) => (
              <RecipientsList
                affiliations={affiliations}
                invalidEmails={invalidEmails}
                contactLists={values.contact_lists}
                includeUnnamedLists={values.include_unnamed_lists}
              />
            )}
          </FormSpy>
        </>
      }
      recipientsFirst
    />
  );
}
