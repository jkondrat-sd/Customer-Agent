# API Integration Guide

## Overview

The FlowDesk API allows you to programmatically interact with the platform. Create and manage tickets, query analytics, manage users, and integrate FlowDesk into your existing workflows.

**Base URL**: `https://api.flowdesk.com/v2`

**Authentication**: All requests must include an API key in the `Authorization` header:
```
Authorization: Bearer fd_live_xxxxxxxxxxxxxxxxxxxxxxxx
```

## Generating an API Key

1. Go to **Settings** → **Integrations** → **API Keys**
2. Click **Generate New Key**
3. Name the key (e.g., "Jira Integration") and set permissions:
   - **Read**: Can read tickets, users, and analytics
   - **Write**: Can create/update tickets and users
   - **Admin**: Full access including billing and settings
4. Copy the key immediately — it will not be shown again
5. Store the key securely (e.g., in a secrets manager, not in source code)

## Rate Limits

| Plan | Rate Limit | Burst |
|------|-----------|-------|
| Professional | 100 requests/minute | 20 requests/second |
| Enterprise | Custom (default: 500 req/min) | 50 requests/second |

Rate limit headers are included in every response:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1672531200
```

When rate limited, the API returns HTTP 429 with a `Retry-After` header.

## Key Endpoints

### Tickets

- `POST /tickets` — Create a new ticket
- `GET /tickets/{id}` — Get ticket details
- `PATCH /tickets/{id}` — Update a ticket
- `GET /tickets?status=open&assignee=agent@company.com` — List tickets with filters
- `POST /tickets/{id}/reply` — Add a reply to a ticket

### Users

- `GET /users` — List all users
- `POST /users` — Create a new user
- `GET /users/{id}` — Get user details
- `DELETE /users/{id}` — Remove a user

### Analytics

- `GET /analytics/overview?period=7d` — Get overview metrics for the last 7 days
- `GET /analytics/agents?period=30d` — Get per-agent performance metrics
- `GET /analytics/csat` — Get customer satisfaction scores

### Webhooks

- `POST /webhooks` — Register a new webhook
- `GET /webhooks` — List all webhooks
- `DELETE /webhooks/{id}` — Remove a webhook

Supported webhook events:
- `ticket.created`, `ticket.updated`, `ticket.resolved`, `ticket.escalated`
- `user.created`, `user.removed`
- `csat.submitted`

## Pagination

List endpoints return paginated results:
```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "per_page": 25,
    "total": 142,
    "total_pages": 6
  }
}
```

Use `?page=2&per_page=50` query parameters to navigate pages.

## Error Codes

| Code | Meaning | Action |
|------|---------|--------|
| 400 | Bad Request — invalid parameters | Check request body/query params |
| 401 | Unauthorized — invalid or missing API key | Verify your API key |
| 403 | Forbidden — insufficient permissions | Check key permissions |
| 404 | Not Found — resource doesn't exist | Verify the resource ID |
| 429 | Too Many Requests — rate limited | Wait and retry with exponential backoff |
| 500 | Internal Server Error | Retry; contact support if persistent |

## SDKs and Libraries

Official SDKs:
- **Python**: `pip install flowdesk-sdk` — [GitHub](https://github.com/flowdesk/python-sdk)
- **Node.js**: `npm install @flowdesk/sdk` — [GitHub](https://github.com/flowdesk/node-sdk)
- **Go**: `go get github.com/flowdesk/go-sdk` — [GitHub](https://github.com/flowdesk/go-sdk)

Community SDKs are also available for Ruby, PHP, and Java — see our [developer portal](https://developers.flowdesk.com).
