# Stripe Integration — Design & Decisions

## Overview

Stripe handles subscription billing for Doubleday. Cognito remains the authentication layer (Google federation); Stripe + a DynamoDB entitlements table form the authorization layer.

## Design Decisions

### Authentication vs. Authorization separation

- **Cognito/Google** = authentication (who are you?)
- **DynamoDB entitlements table** = authorization (what can you access?)
- **Stripe** = payment processing (have they paid?)
- The Lambda authorizer stays JWT-only (unchanged). Subscription checks happen inside each data endpoint, avoiding the 300s authorizer cache staleness problem.

### Endpoint-level subscription checks (not authorizer-level)

The API Gateway authorizer caches results for 300 seconds keyed by JWT. If we added subscription checks there, a user who just paid would be denied for up to 5 minutes. Instead, each data endpoint (pitches, neighbors) checks the entitlements table directly. This adds one DynamoDB GetItem per request but eliminates the cache staleness problem.

### Catalog stays free

The catalog endpoint (player/pitcher browsing) remains accessible to all authenticated users. Only data endpoints (pitches, neighbors) require an active subscription. This lets users browse before subscribing.

### Entitlements table schema

Single-table design with PK-only key (`USER#{cognito_sub}`). No sort key needed initially — one entitlement record per user. Tier and feature fields are present but start simple (just `active`/`inactive` status). Schema can evolve as product tiers are defined.

### Cognito-to-Stripe customer linkage

When creating a Stripe Checkout session, we store `cognito_sub` in both:
- `client_reference_id` on the Checkout Session (available in `checkout.session.completed` webhook)
- `metadata.cognito_sub` on the Stripe Customer object (available in all subsequent subscription lifecycle webhooks via `stripe.Customer.retrieve()`)

This avoids needing a DynamoDB GSI on `stripe_customer_id`.

### Webhook signing secret — Stripe CLI for dev

The webhook signing secret (`whsec_...`) is created when you register a webhook endpoint in the Stripe Dashboard. Since the endpoint URL must exist first, the dev workflow is:

1. Deploy the webhook Lambda
2. Use `stripe listen --forward-to <endpoint-url>` for local/dev testing (provides a temporary signing secret)
3. Register the real webhook endpoint in Stripe Dashboard when ready for production
4. Store the production signing secret in Secrets Manager (`{env}/doubleday/stripe/webhook_signing_secret`)

For dev, the Stripe CLI signing secret can be stored in Secrets Manager temporarily, or passed as an environment variable override.

### Secrets management

Stripe secrets live in AWS Secrets Manager, following the existing pattern (same as Google OAuth credentials):
- `{env}/doubleday/stripe/api_keys` → `{"secret_key": "sk_...", "publishable_key": "pk_..."}`
- `{env}/doubleday/stripe/webhook_signing_secret` → `{"signing_secret": "whsec_..."}`

Read by Terraform via `data "aws_secretsmanager_secret_version"`, decoded, and passed as Lambda environment variables.

## Stripe Account Setup

### Sandbox keys (already obtained)

- Publishable key: `pk_test_...`
- Secret key: `sk_test_...`

### Still needed

- [ ] Create a Product and Price in Stripe Dashboard (subscription plan)
- [ ] Register webhook endpoint (after Lambda is deployed) to get signing secret
- [ ] Configure Stripe Customer Portal (branding, allowed actions)

## Deploy Order

`Phase 1 (infra) → Phase 2 (webhook) → Phase 4 (checkout/portal/status) → Phase 5 (frontend) → Phase 3 (enforcement)`

Enforcement is enabled last so users can subscribe before being gated.
