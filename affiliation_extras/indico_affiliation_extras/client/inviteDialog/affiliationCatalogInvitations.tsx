// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import affiliationCatalogInviteMetadataURL from 'indico-url:plugin_affiliation_extras.api_affiliation_catalog_invite_metadata';
import affiliationCatalogInviteRecipientCountURL from 'indico-url:plugin_affiliation_extras.api_affiliation_catalog_invite_recipient_count';
import inviteAffiliationCatalogURL from 'indico-url:plugin_affiliation_extras.api_invite_affiliation_catalog';

import React, {useEffect, useMemo, useRef} from 'react';
import {useForm, useFormState} from 'react-final-form';
import {Icon, Loader, Message, Segment} from 'semantic-ui-react';

import {FinalDropdown} from 'indico/react/forms';
import {useIndicoAxios} from 'indico/react/hooks';
import {Param, Plural, PluralTranslate, Singular, Translate} from 'indico/react/i18n';

import ContactListRecipientFields from '../components/ContactListRecipientFields';

interface AffiliationCatalogFieldsProps {
  eventId: number;
  regformId: number;
}

type RecipientSource = 'focal_points' | 'contacts' | 'both';

interface AffiliationCatalogInvitationValues {
  affiliation_catalog_recipient_count: number;
  recipient_source: RecipientSource | null;
  contact_lists: string[];
  include_unnamed_lists: boolean;
}

interface AffiliationCatalogMetadata {
  affiliationCount: number;
  focalPointCount: number;
  contactListOptions: {name: string; hasContacts: boolean}[];
  hasAffiliationCatalog: boolean;
}

interface RecipientCountData {
  recipientCount: number;
}

interface InvitationModeContext {
  eventId: number;
  regformId: number;
}

interface AffiliationCatalogInvitationMode {
  key: string;
  buttonLabel: string;
  Component: React.ComponentType<AffiliationCatalogFieldsProps>;
  extraFields: (keyof AffiliationCatalogInvitationValues)[];
  initialValues: AffiliationCatalogInvitationValues;
  getCount: (values: AffiliationCatalogInvitationValues) => number;
  getSubmitURL: (context: InvitationModeContext) => string;
}

const AffiliationCatalogFields = ({eventId, regformId}: AffiliationCatalogFieldsProps) => {
  const form = useForm<AffiliationCatalogInvitationValues>();
  const {
    values: {
      recipient_source: recipientSource = null,
      contact_lists: contactLists = [],
      include_unnamed_lists: includeUnnamedLists = false,
    },
  } = useFormState<AffiliationCatalogInvitationValues>({
    subscription: {values: true},
  });
  const {data: metadataData, loading} = useIndicoAxios(
    affiliationCatalogInviteMetadataURL({event_id: eventId, reg_form_id: regformId}),
    {camelize: true}
  );
  const data = metadataData as AffiliationCatalogMetadata | null;
  const recipientCountConfig = useMemo(
    () => ({
      url: affiliationCatalogInviteRecipientCountURL({
        event_id: eventId,
        reg_form_id: regformId,
      }),
      method: 'POST',
      data: {
        recipient_source: recipientSource,
        contact_lists: contactLists,
        include_unnamed_lists: includeUnnamedLists,
      },
    }),
    [contactLists, eventId, includeUnnamedLists, recipientSource, regformId]
  );
  const hasUnnamedContactLists = data?.contactListOptions.some(({name}) => name === '');
  const namedContactLists = data?.contactListOptions.filter(({name}) => name).map(({name}) => name) ?? [];
  const hasContactLists = !!data?.contactListOptions.length;
  const hasFocalPoints = !!(data && data.focalPointCount);
  const includesContacts = recipientSource === 'contacts' || recipientSource === 'both';
  const recipientSourceOptions = useMemo<{value: RecipientSource; text: string}[]>(
    () => [
      ...(hasFocalPoints
        ? [{value: 'focal_points' as const, text: Translate.string('Focal points')}]
        : []),
      ...(hasContactLists
        ? [{value: 'contacts' as const, text: Translate.string('Contacts')}]
        : []),
      ...(hasFocalPoints && hasContactLists
        ? [{value: 'both' as const, text: Translate.string('Focal points and contacts')}]
        : []),
    ],
    [hasContactLists, hasFocalPoints]
  );
  const onlyRecipientSource =
    recipientSourceOptions.length === 1 ? recipientSourceOptions[0].value : null;
  const showNoContactsError = !!(
    includesContacts &&
    data &&
    !data.contactListOptions.some(
      ({name, hasContacts}) =>
        hasContacts && (name === '' ? includeUnnamedLists : contactLists.includes(name))
    )
  );

  const {
    data: recipientCountResponse,
    error: recipientCountError,
    loading: recipientCountLoading,
  } = useIndicoAxios(recipientCountConfig, {
    camelize: true,
    manual: !data || !recipientSource || showNoContactsError,
  });
  const recipientCountData = recipientCountResponse as RecipientCountData | null;
  const previousRecipientCountConfig = useRef(recipientCountConfig);
  const recipientCountConfigChanged = previousRecipientCountConfig.current !== recipientCountConfig;

  useEffect(() => {
    if (previousRecipientCountConfig.current !== recipientCountConfig) {
      previousRecipientCountConfig.current = recipientCountConfig;
      form.change('affiliation_catalog_recipient_count', 0);
    }
  }, [form, recipientCountConfig]);

  useEffect(() => {
    if (
      recipientSource &&
      !recipientCountLoading &&
      !recipientCountError &&
      !recipientCountConfigChanged &&
      recipientCountData
    ) {
      form.change(
        'affiliation_catalog_recipient_count',
        showNoContactsError ? 0 : recipientCountData.recipientCount
      );
    }
  }, [
    form,
    showNoContactsError,
    recipientCountConfigChanged,
    recipientCountData,
    recipientCountError,
    recipientCountLoading,
    recipientSource,
  ]);

  useEffect(() => {
    if (hasUnnamedContactLists === false && includeUnnamedLists) {
      form.change('include_unnamed_lists', false);
    }
  }, [form, hasUnnamedContactLists, includeUnnamedLists]);

  useEffect(() => {
    if (!recipientSource && onlyRecipientSource) {
      form.change('recipient_source', onlyRecipientSource);
    }
  }, [form, onlyRecipientSource, recipientSource]);

  if (loading || !data) {
    return <Loader active inline="centered" />;
  }

  return (
    <>
      {!data.hasAffiliationCatalog ? (
        <Message error visible icon>
          <Icon name="warning sign" />
          <Message.Content>
            <Translate as={Message.Header}>No affiliation catalog selected</Translate>
            <Translate as="p">
              Select an affiliation catalog for this event before sending invitations.
            </Translate>
          </Message.Content>
        </Message>
      ) : data.affiliationCount ? (
        <Message info icon>
          <Icon name="building outline" />
          <Message.Content>
            <PluralTranslate as={Message.Header} count={data.affiliationCount}>
              <Singular>
                The event catalog contains <Param name="count" value={data.affiliationCount} />{' '}
                affiliation.
              </Singular>
              <Plural>
                The event catalog contains <Param name="count" value={data.affiliationCount} />{' '}
                affiliations.
              </Plural>
            </PluralTranslate>
            <Translate as="p">
              Choose whether focal points, contacts, or both should receive an invitation.
            </Translate>
            <Translate as="p">Existing invitations and registrations will be skipped.</Translate>
          </Message.Content>
        </Message>
      ) : (
        <Message error visible icon>
          <Icon name="warning sign" />
          <Message.Content>
            <Translate as={Message.Header}>No affiliations found</Translate>
            <Translate as="p">
              No affiliations were found on the selected catalog for this event.
            </Translate>
          </Message.Content>
        </Message>
      )}
      <FinalDropdown
        name="recipient_source"
        label={Translate.string('Recipients')}
        placeholder={Translate.string('Select recipient source')}
        options={recipientSourceOptions}
        disabled={recipientSourceOptions.length <= 1}
        selection
        fluid
        required
      />
      {data.affiliationCount > 0 && !recipientSourceOptions.length && (
        <Message negative content={Translate.string('No invitation recipients found.')} />
      )}
      {includesContacts && (hasContactLists || showNoContactsError) && (
        <Segment>
          {hasContactLists && (
            <ContactListRecipientFields
              label={Translate.string('Contact lists')}
              contactListOptions={namedContactLists}
              hasUnnamedContactLists={hasUnnamedContactLists}
              allowNoContactLists
            />
          )}
          {showNoContactsError && (
            <Message
              negative
              size="small"
              content={Translate.string('No contacts match the selected contact lists.')}
            />
          )}
        </Segment>
      )}
    </>
  );
};

const affiliationCatalogInvitations: AffiliationCatalogInvitationMode = {
  key: 'affiliation_catalog',
  buttonLabel: Translate.string('Affiliation Catalog'),
  Component: AffiliationCatalogFields,
  extraFields: ['recipient_source', 'contact_lists', 'include_unnamed_lists'],
  initialValues: {
    affiliation_catalog_recipient_count: 0,
    recipient_source: null,
    contact_lists: [],
    include_unnamed_lists: true,
  },
  getCount: ({affiliation_catalog_recipient_count: recipientCount}) => recipientCount,
  getSubmitURL: ({eventId, regformId}) =>
    inviteAffiliationCatalogURL({event_id: eventId, reg_form_id: regformId}),
};

export default affiliationCatalogInvitations;
