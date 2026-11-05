# Data Privacy and GDPR Compliance

## Our Commitment to Privacy

FlowDesk is committed to protecting the privacy and security of your data. We comply with the General Data Protection Regulation (GDPR), the California Consumer Privacy Act (CCPA), and other applicable data protection laws.

## Data We Collect

| Data Category | Examples | Purpose |
|--------------|----------|---------|
| Account information | Name, email, company, role | Account management, authentication |
| Usage data | Feature usage, login history, page views | Product improvement, analytics |
| Support data | Tickets, conversations, attachments | Providing support services |
| Payment data | Card details, billing address | Payment processing (via PCI-compliant processor) |
| Device data | Browser type, OS, IP address | Security, troubleshooting |

## Data Storage and Retention

- All data is stored in encrypted form (AES-256 at rest, TLS 1.3 in transit)
- Data is hosted in Google Cloud Platform (GCP) data centers:
  - Primary: US (Iowa)
  - EU customers: EU (Belgium) — data does not leave the EU
- **Retention periods**:
  - Active account data: retained for the duration of the subscription
  - Deleted account data: permanently deleted within 90 days of account deactivation
  - Support tickets: retained for 3 years after resolution for quality assurance
  - Payment data: retained as required by tax and financial regulations (typically 7 years)

## Your Rights (GDPR / CCPA)

As a data subject, you have the right to:

1. **Access**: Request a copy of all personal data we hold about you
2. **Rectification**: Request correction of inaccurate or incomplete data
3. **Erasure ("Right to be Forgotten")**: Request deletion of your personal data
4. **Portability**: Receive your data in a structured, machine-readable format (JSON or CSV)
5. **Restriction**: Request that we limit processing of your data
6. **Objection**: Object to processing based on legitimate interests or direct marketing
7. **Withdraw consent**: Withdraw previously given consent at any time

## Exercising Your Rights

To exercise any of these rights:
1. Email privacy@flowdesk.com with your request
2. Include your account email and specify which right you wish to exercise
3. We will verify your identity within 2 business days
4. Requests are fulfilled within 30 days (GDPR) or 45 days (CCPA)

## Data Processing Agreements (DPA)

Enterprise customers can request a signed Data Processing Agreement:
- Contact legal@flowdesk.com
- Standard DPA includes Standard Contractual Clauses (SCCs) for international data transfers
- Custom DPA terms are available for Enterprise plan customers

## Sub-Processors

FlowDesk uses the following sub-processors:
- **Google Cloud Platform**: Infrastructure and hosting
- **Stripe**: Payment processing
- **SendGrid**: Transactional email delivery
- **Pinecone**: Vector database (for AI features)

A full list of sub-processors is maintained at https://flowdesk.com/legal/sub-processors and customers are notified 30 days before any new sub-processor is added.

## Security Measures

- SOC 2 Type II certified
- Annual penetration testing by independent third parties
- Bug bounty program: security@flowdesk.com
- Employee access to customer data is logged and audited
- Least-privilege access model — employees access only what is necessary for their role
