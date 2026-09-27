# Payments: Dodo → Zoya license

Someone subscribes on Dodo. Dodo asks the relay for a key. The relay makes a normal `zoya_…` key, hands it to Dodo, and Dodo emails it to the customer. When the subscription stops, Dodo tells the relay and the key stops working. The monthly cap works exactly as it does for beta keys.

## How it works

| Dodo event (`POST /webhooks/dodo`) | What the relay does |
| --- | --- |
| `entitlement_grant.created`, license-key grant, status `Pending` | Makes a `zoya_` key, sends it to `POST {DODO_API_BASE_URL}/grants/{grant_id}/license-key`, stores its SHA-256 as an active `paid` license (cap 800 cents). Dodo emails the key. |
| `entitlement_grant.delivered` (fulfilled, or restored after on-hold / pause) | Marks the key active. |
| `entitlement_grant.revoked` (cancelled, expired, on hold after a failed renewal, paused, plan changed, manual) | Marks the key inactive. |
| anything else | Acknowledged and ignored. |

Dodo itself maps the subscription lifecycle to the grant: renewal and the `past_due` grace period keep the key; `on_hold`, `paused`, `cancelled` and `expired` revoke it; coming off hold or unpausing restores it ([License Keys → How Keys Are Issued](https://docs.dodopayments.com/features/license-keys)).

- **Signature.** Every request is checked against the `webhook-id`, `webhook-timestamp` and `webhook-signature` headers with HMAC-SHA256 over `{id}.{timestamp}.{body}` using `DODO_WEBHOOK_SECRET` (the `whsec_` prefix is stripped, the rest base64-decoded), with a 5-minute replay window. Bad or missing signature → `401`.
- **Idempotency.** Each `webhook-id` is stored in `dodo_events` in the same transaction as the license change. A repeated `webhook-id` returns `200` and changes nothing. A failure is not recorded, so Dodo's retry runs it again.
- **Ordering.** Each license row keeps the timestamp of the last Dodo event applied to it; an older event that arrives late is ignored.
- **Retries of the fulfilment call.** If Dodo answers `409` (the grant already has a key), the relay acknowledges the event and does nothing else: the key Dodo holds reaches the relay through `entitlement_grant.delivered`.

Only keys with `kind = 'paid'` are ever changed by a webhook. Beta keys from `npm run license` are untouched.

## Owner setup

Live Dodo credentials don't exist yet. Do all of this in **test mode** first, then repeat in live mode.

### 1. Database (once)

Run the schema against the relay's Neon database. It is additive: it makes `licenses.email` optional (Dodo does not send the customer's email in grant events), adds `dodo_grant_id`, `dodo_customer_id` and `dodo_event_at`, and creates `dodo_events`.

```sh
cd relay
npm run license -- setup
```

### 2. Dodo dashboard

1. **Entitlement.** Entitlements → **+** → **License Keys**.
   - Name: `Zoya`.
   - **Fulfillment Mode: Manual.** This is essential. On Automatic, Dodo would make its own keys, and the Mac app only accepts `zoya_` keys.
   - License Length: **No expiration**. Subscription keys follow the subscription.
   - Activations Limit: your choice. The relay does not use activations.
   - Activation Message, for example: `Paste this key into Zoya when she asks for your license.`
2. **Product.** Products → new **Subscription** product, $20 per month. Attach the `Zoya` entitlement under **Entitlements**.
3. **Webhook.** Developer → Webhooks → **Add endpoint**.
   - URL: `https://<relay host>/webhooks/dodo`.
   - Events: `entitlement_grant.created`, `entitlement_grant.delivered`, `entitlement_grant.revoked`. Select at least one event: an endpoint with none selected receives every event.
   - Save, then copy the signing secret from the endpoint's **Overview** tab.
4. **API key.** Developer → API Keys → **Add API Key**, in the same mode (test or live) as the base URL below. The relay uses it only to fulfil grants.

### 3. Relay secrets and vars

```sh
cd relay
npx wrangler secret put DODO_WEBHOOK_SECRET   # the whsec_… signing secret from step 2.3
npx wrangler secret put DODO_API_KEY          # the API key from step 2.4
```

`DODO_API_BASE_URL` is a plain var in `wrangler.jsonc`. It is `https://test.dodopayments.com` now. **Change it to `https://live.dodopayments.com` when you switch to live keys**, and put the live webhook secret and API key in. Test and live keys don't mix.

For `npm run dev`, add the same three names to the repo's `.env`.

### 4. Test it

1. Webhooks → your endpoint → **Testing** → send an `entitlement_grant.revoked` example. Expect `200`. A `401` means the signing secret is wrong. (A sample `created` event may point at a grant that doesn't exist, so the fulfilment call can fail with `503`; that is expected for samples.)
2. Buy the product in test mode with a test card. Within seconds the email arrives with a `zoya_…` key. `npm run license -- usage <key>` shows it as `paid`, active.
3. Paste the key into Zoya. `GET /v1/license` answers `valid: true`.
4. Cancel the subscription in test mode. `usage <key>` now shows `active = false`, and Zoya reports the key as not valid.

### If a webhook was missed

Dodo retries 8 times over about a day. After that, open the endpoint in the dashboard and replay the failed message. A failed event was never recorded, so the replay is applied normally.

To revoke by hand, use `npm run license -- revoke <key>` (paid keys have no email, so pass the key). The next Dodo event for that key overrides it.

## Docs relied on

- Webhooks, signature scheme, retries, idempotency: https://docs.dodopayments.com/developer-resources/webhooks
- Entitlement grant events and payload (`integration_type`, `status`, `license_key.key`, `revocation_reason`): https://docs.dodopayments.com/developer-resources/webhooks/intents/entitlement-grant
- License keys, manual fulfilment, lifecycle table: https://docs.dodopayments.com/features/license-keys
- Fulfil a pending grant (`POST /grants/{grant_id}/license-key`, body `{ "key" }`, `409` when already fulfilled): https://docs.dodopayments.com/api-reference/entitlements/fulfill-license-key
- Manual fulfilment guide (test/live hosts): https://docs.dodopayments.com/developer-resources/manual-license-key-fulfillment
- Subscription events: https://docs.dodopayments.com/developer-resources/webhooks/intents/subscription
