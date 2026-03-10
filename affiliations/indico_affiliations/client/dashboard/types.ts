// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import {SemanticCOLORS} from 'semantic-ui-react';

import {Affiliation} from 'indico/modules/users/affiliations/types';

import {ContactList} from '../components/ContactListField';

export interface GroupInfo {
  id: number;
  name: string;
  code: string;
}

export interface TagInfo {
  id: number;
  name: string;
  code: string;
  color: SemanticCOLORS;
}

export interface ExtendedAffiliation extends Affiliation {
  contacts: ContactList[];
  groups: GroupInfo[];
  tags: TagInfo[];
  group_tags: TagInfo[];
}
