# Service Level Agreement (SLA)

## Scope

This Service Level Agreement applies to all FlowDesk Enterprise customers with active contracts. Starter and Professional plans are governed by standard terms of service and do not include SLA guarantees.

## Uptime Guarantee

| Plan | Uptime SLA | Permitted Monthly Downtime |
|------|-----------|---------------------------|
| Enterprise Standard | 99.9% | ~43 minutes |
| Enterprise Premium | 99.99% | ~4.3 minutes |

**Uptime** is calculated as: `(Total minutes in month - Downtime minutes) / Total minutes in month × 100`

**Downtime** is defined as any period during which the FlowDesk API or web application returns HTTP 5xx errors for more than 5 consecutive minutes, excluding scheduled maintenance.

## Scheduled Maintenance

- Maintenance windows: Sundays 2:00 AM – 6:00 AM EST
- Customers are notified at least 72 hours in advance via email and in-app notification
- Scheduled maintenance is excluded from uptime calculations
- Emergency maintenance may occur outside the scheduled window with as much advance notice as possible

## Incident Response

| Severity | Definition | Response Time | Update Frequency |
|----------|-----------|---------------|------------------|
| Sev 1 — Outage | Platform fully unavailable | 15 minutes | Every 30 minutes |
| Sev 2 — Degraded | Core feature significantly impaired | 30 minutes | Every 1 hour |
| Sev 3 — Minor | Non-critical feature affected | 4 hours | Every 4 hours |

## Service Credits

If FlowDesk fails to meet the uptime SLA, eligible customers may request service credits:

| Monthly Uptime | Credit (% of monthly fee) |
|---------------|--------------------------|
| 99.0% – 99.9% | 10% |
| 95.0% – 99.0% | 25% |
| Below 95.0% | 50% |

### Requesting Credits
1. Email sla@flowdesk.com within 30 days of the incident
2. Include your account ID and the dates/times of the downtime
3. Credits are applied to the next billing cycle — they are not paid out as cash
4. Maximum credit in any month: 50% of that month's fees

## Exclusions

The SLA does not apply to:
- Issues caused by customer misuse or misconfiguration
- Third-party service outages (e.g., cloud provider regional failures beyond our redundancy architecture)
- Force majeure events (natural disasters, war, government actions)
- Features in beta or preview status
- Scheduled maintenance within the defined windows

## Status Page

Real-time platform status is available at https://status.flowdesk.com. Subscribe to updates via email, SMS, or RSS for immediate incident notifications.

## SLA Review

SLAs are reviewed annually. Changes to SLA terms are communicated at least 60 days before the renewal date. Enterprise customers may negotiate custom SLA terms as part of their contract.
