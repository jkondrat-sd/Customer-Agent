# Account Setup and Management

## Creating Your Account

To get started with FlowDesk:

1. Visit https://app.flowdesk.com/signup
2. Enter your business email address (personal email domains like Gmail or Yahoo are not accepted for enterprise accounts)
3. Set a strong password (minimum 12 characters, must include uppercase, lowercase, number, and special character)
4. Verify your email by clicking the link sent to your inbox
5. Complete your profile: name, company, role, and department

## Account Types

| Type | Users | Features | Price |
|------|-------|----------|-------|
| Starter | 1–5 | Basic support desk, email channel | $29/mo |
| Professional | 6–25 | Multi-channel, basic analytics, API access | $79/mo per seat |
| Enterprise | 25+ | Full platform, custom integrations, dedicated CSM | Custom pricing |

## Managing Team Members

### Adding Users
1. Go to **Settings** → **Team Management**
2. Click **Invite Member**
3. Enter the user's email and assign a role (Admin, Agent, Viewer)
4. The invited user receives an email with setup instructions

### Roles and Permissions
- **Admin**: Full access — can manage billing, team, integrations, and all settings
- **Agent**: Can handle tickets, view dashboards, and use tools — cannot modify billing or team settings
- **Viewer**: Read-only access to dashboards and reports

### Removing Users
1. Go to **Settings** → **Team Management**
2. Find the user and click **Remove**
3. Confirm the removal — the user's tickets will be reassigned to the team queue
4. The removed user's data is retained for 90 days for audit purposes before permanent deletion

## Single Sign-On (SSO)

Enterprise accounts can configure SSO via SAML 2.0:
1. Navigate to **Settings** → **Security** → **SSO Configuration**
2. Upload your Identity Provider (IdP) metadata XML
3. Configure attribute mapping (email, name, role)
4. Test the connection, then enforce SSO for all team members

Supported IdPs: Okta, Azure AD, Google Workspace, OneLogin.

## Account Deactivation

To deactivate your account:
1. Export your data via **Settings** → **Data Export** (available for 30 days after deactivation)
2. Go to **Settings** → **Account** → **Deactivate Account**
3. Confirm deactivation — active subscriptions will be cancelled at the end of the current billing period
4. Reactivation is possible within 90 days by contacting support@flowdesk.com
