// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import React from 'react';
import {FinalModalForm} from 'indico/react/forms/final-form';

export default function ItemModal({
  header,
  onSubmit,
  initialValues,
  onClose,
  children,
}: {
  header: string;
  onSubmit: (formData: Record<string, unknown>, form: unknown) => Promise<unknown> | unknown;
  initialValues: object;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const handleSubmit = async (formData: Record<string, unknown>, form: unknown) => {
    const error = await onSubmit(formData, form);
    if (error) {
      return error;
    }
    onClose();
  };

  return (
    <FinalModalForm
      id="item-form"
      onSubmit={handleSubmit}
      onClose={onClose}
      initialValues={initialValues}
      header={header}
    >
      {children}
    </FinalModalForm>
  );
}
