# OpenAPI

Read-only REST API for Indico resources, described with an OpenAPI v3 document.

The API reuses Indico's own request handlers, marshmallow schemas and access
checks, so a request authenticated with a token returns exactly the data its
owner can see in the web interface.

## Endpoints

| Path | Description |
| --- | --- |
| `/api/v1/events/<event_id>` | Event details |
| `/api/v1/openapi.json` | OpenAPI v3 document |
| `/api/v1/docs` | Swagger UI |

## Authentication

Create a personal token under your Indico profile with the `read:everything`
scope and send it as a bearer token:

```sh
curl -H 'Authorization: Bearer indp_...' https://indico.example.com/api/v1/events/1
```
