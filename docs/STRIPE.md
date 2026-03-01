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
- `client_reference_id` on the Checkout Session (available in `checkout.session.completed` event)
- `metadata.cognito_sub` on the Stripe Customer object (available in all subsequent subscription lifecycle events via `stripe.Customer.retrieve()`)

This avoids needing a DynamoDB GSI on `stripe_customer_id`.

### Event delivery — EventBridge partner integration

Stripe events are delivered via Amazon EventBridge (not a webhook endpoint). This eliminates the need for an API Gateway endpoint, CORS configuration, and signature verification. Stripe sends events directly to a partner event bus in EventBridge, and an EventBridge rule routes the 4 subscription lifecycle events to a Lambda function.

Setup: In Stripe Dashboard → Developers → Webhooks → Add destination → Amazon EventBridge. The event source name (e.g., `aws.partner/stripe.com/<account_id>/<destination_id>`) is passed to Terraform as `stripe_event_source_name`.

### Email in entitlements table

The entitlement record stores the user's email for operational lookups (e.g., `delete_entitlement.sh`). The email comes from the Stripe `checkout.session.completed` event, not from the JWT.

Why not from the authorizer? Browser clients send **access tokens** (the correct OAuth pattern). Access tokens don't carry an `email` claim — only ID tokens do. Switching to ID tokens would be incorrect, and adding a Cognito API call to the authorizer adds latency to every request for a value only needed once at checkout time.

The `checkout.session.completed` event includes the email in `customer_details.email` (populated by Stripe from the checkout form). The handler checks `customer_email` first (pre-filled if the Customer object has an email), then falls back to `customer_details.email`.

### Secrets management

Stripe API keys live in AWS Secrets Manager, following the existing pattern (same as Google OAuth credentials):
- `{env}/doubleday/stripe/api_keys` → `{"secret_key": "sk_...", "publishable_key": "pk_..."}`

Read by Terraform via `data "aws_secretsmanager_secret_version"`, decoded, and passed as Lambda environment variables. No webhook signing secret is needed with EventBridge.

## Prerequisites

### Stripe CLI

Install the Stripe CLI for testing event delivery:

```bash
brew install stripe/stripe-cli/stripe
stripe login
```

Trigger test events:

```bash
stripe trigger checkout.session.completed
```

## Environment Setup Checklist

These steps must be completed for each environment (dev, prod).

### 1. Create Stripe API keys secret

Get API keys from Stripe Dashboard → Developers → API keys, then:

```bash
aws secretsmanager create-secret \
  --name "{env}/doubleday/stripe/api_keys" \
  --secret-string '{"secret_key": "sk_...", "publishable_key": "pk_..."}'
```

### 2. Create a Product and Price

In Stripe Dashboard → Product catalog → Add product:
- Set a name (e.g., "Doubleday Pro")
- Add a recurring price (e.g., $10/month)
- Copy the Price ID (`price_...`)
- Set it in `terraform/environments/{env}/terraform.tfvars` as `stripe_price_id`

### 3. Configure EventBridge destination

In Stripe Dashboard → Developers → Webhooks → Add destination:
1. Select **Amazon EventBridge**
2. Enter your AWS account ID and region (`us-east-1`)
3. Select the 4 event types:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_failed`
4. Copy the event source name (`aws.partner/stripe.com/...`)
5. Set it in `terraform/environments/{env}/terraform.tfvars` as `stripe_event_source_name`

### 4. Deploy infrastructure

Push to a PR branch (deploys dev) or merge to main (deploys prod).

### 5. Verify event delivery

```bash
stripe trigger checkout.session.completed
aws logs tail /aws/lambda/doubleday-{env}-api-stripe-events --since 5m
```

Expect a `checkout.session.completed` log entry with a warning about `missing client_reference_id` (test events don't include a real checkout session).

### 6. Configure Customer Portal

In Stripe Dashboard → Settings → Customer portal:
- Enable cancel subscription
- Enable update payment method
- Enable view invoices

## Operations

### Delete a subscriber's entitlement

To remove a user's entitlement (e.g., for testing), use the script with an email or cognito sub:

```bash
bash scripts/delete_entitlement.sh user@gmail.com          # lookup by email
bash scripts/delete_entitlement.sh <cognito-sub>            # lookup by cognito sub
bash scripts/delete_entitlement.sh user@gmail.com prod      # specify environment
```

The script warns if a Stripe subscription is still active. Cancel the subscription in Stripe first to avoid it being recreated by the next billing event:

```bash
stripe subscriptions cancel <subscription_id>
```

Or cancel via Stripe Dashboard → Customers → find customer → cancel subscription.

## Deploy Order

`Phase 1 (infra + EventBridge) → Phase 4 (checkout/portal/status) → Phase 5 (frontend) → Phase 3 (enforcement)`

Enforcement is enabled last so users can subscribe before being gated.
