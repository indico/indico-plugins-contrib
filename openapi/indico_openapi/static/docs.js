// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 Unconventional
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

/* global SwaggerUIBundle */

window.addEventListener('load', () => {
  const container = document.getElementById('swagger-ui');
  SwaggerUIBundle({
    url: container.dataset.specUrl,
    dom_id: '#swagger-ui',
    deepLinking: true,
    withCredentials: true,
    tryItOutEnabled: true,
    persistAuthorization: true,
    // Indico rejects a request carrying both a token and a session cookie,
    // so the cookie is only sent when no token was entered.
    requestInterceptor: req => {
      req.credentials = req.headers.Authorization ? 'omit' : 'include';
      return req;
    },
  });
});
