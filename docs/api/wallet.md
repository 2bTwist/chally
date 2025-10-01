# Wallet API

## Overview

The Wallet API manages user token balances, deposits via Stripe, and withdrawals through FIFO refunds. It implements the M7 wallet system with complete audit trails and ACID compliance.

## Base URL
```
http://localhost:8000/wallet
```

## Authentication
All wallet endpoints require authentication with a valid access token:
```
Authorization: Bearer <access_token>
```

## Endpoints

### Get Wallet Balance and History

**Endpoint:** `GET /wallet`

**Description:** Retrieve current wallet balance and transaction history.

**Response (200 OK):**
```json
{
  "balance": 1250,
  "entries": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "type": "DEPOSIT",
      "amount": 1000,
      "currency": "usd",
      "external_id": "pi_1234567890",
      "note": "stripe_deposit",
      "created_at": "2024-01-01T12:00:00Z"
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "type": "STAKE",
      "amount": -50,
      "currency": "usd",
      "external_id": null,
      "note": "Challenge stake payment",
      "created_at": "2024-01-01T13:00:00Z"
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440002",
      "type": "PAYOUT",
      "amount": 300,
      "currency": "usd",
      "external_id": null,
      "note": "Challenge completion payout",
      "created_at": "2024-01-01T14:00:00Z"
    }
  ]
}
```

**Entry Types:**
- **DEPOSIT**: Tokens added from Stripe payment (+)
- **STAKE**: Tokens deducted for challenge participation (-)
- **PAYOUT**: Tokens received from challenge winnings (+)
- **WITHDRAWAL**: Tokens removed via Stripe refund (-)

### Create Deposit Checkout Session

**Endpoint:** `POST /wallet/deposit/checkout`

**Description:** Create a Stripe checkout session for purchasing tokens.

**Request Body:**
```json
{
  "tokens": 1000,
  "success_url": "https://yourapp.com/success?session_id={CHECKOUT_SESSION_ID}",
  "cancel_url": "https://yourapp.com/cancel"
}
```

**Request Parameters:**
- **tokens** (integer, required): Number of tokens to purchase (min: 1, max: 100,000)
- **success_url** (string, required): URL to redirect after successful payment
- **cancel_url** (string, required): URL to redirect if payment is cancelled

**Response (200 OK):**
```json
{
  "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_...",
  "session_id": "cs_test_a1wMv8sJWhyhsfvJpVGQLOXWnbr3LqPoMCYqoaYJqtACrGnu3fsUZt0bVO"
}
```

**Usage Flow:**
1. Create checkout session via API
2. Redirect user to `checkout_url`
3. User completes payment on Stripe
4. Stripe webhook automatically credits tokens to wallet
5. User redirected to `success_url`

**Error Responses:**
- **400 Bad Request**: Invalid token amount or URLs
- **429 Too Many Requests**: Exceeded daily deposit limit or rate limit
- **500 Internal Server Error**: Stripe not configured

### Withdraw Tokens

**Endpoint:** `POST /wallet/withdraw`

**Description:** Withdraw tokens back to original payment methods via FIFO refunds.

**Request Body:**
```json
{
  "tokens": 500
}
```

**Request Parameters:**
- **tokens** (integer, required): Number of tokens to withdraw

**Response (200 OK):**
```json
{
  "requested": 500,
  "refunded": 500,
  "stripe_refunds": [
    "re_1234567890abcdef",
    "re_0987654321fedcba"
  ]
}
```

**Response Fields:**
- **requested**: Number of tokens requested for withdrawal
- **refunded**: Number of tokens actually refunded (may be less if some deposits are outside refund window)
- **stripe_refunds**: Array of Stripe refund IDs created

**FIFO Processing:**
Withdrawals are processed in First-In-First-Out order:
1. Oldest deposits are refunded first
2. Refunds go back to original payment methods
3. Each refund maps to a specific Stripe payment_intent
4. Process continues until requested amount is refunded or no more eligible deposits

**Error Responses:**
- **400 Bad Request**: Invalid amount or insufficient balance
- **503 Service Unavailable**: Withdrawals currently disabled

## Wallet System Details

### Token Economics
- **1 Token = 1 USD Cent** (configurable via `TOKEN_PRICE_USD_CENTS`)
- Example: $10.00 purchase = 1,000 tokens

### Daily Limits
- **Deposit Limit**: 100,000 tokens ($1,000) per user per day
- **Rate Limits**: 10 deposit attempts per hour per IP

### Refund Window
- **Default**: 90 days from original deposit
- Only deposits within the refund window are eligible for withdrawal
- Older deposits cannot be withdrawn (prevents payment processor disputes)

## Advanced Features

### FIFO Allocation Example

Given these deposits:
```
Deposit A: 1000 tokens (Jan 1, payment_intent_1)
Deposit B: 500 tokens  (Jan 2, payment_intent_2) 
Deposit C: 300 tokens  (Jan 3, payment_intent_3)
```

Withdrawal of 800 tokens would process:
1. Refund 1000 tokens from Deposit A → $10.00 refund to payment_intent_1
2. Need 800 tokens total, so refund is complete
3. Remaining: Deposit A: 200 tokens, Deposit B: 500 tokens, Deposit C: 300 tokens

### Wallet Entries vs Allocations

**Wallet Entries** (transaction log):
- Primary record of all wallet activity
- Used for balance calculation: `SUM(amount) WHERE user_id = ?`
- Immutable audit trail

**Wallet Allocations** (FIFO tracking):
- Tracks individual deposit "lots" with original payment information
- Enables accurate FIFO refund processing
- Links to original Stripe payment_intent_id for refunds

### Advisory Locks
All wallet operations use PostgreSQL advisory locks to prevent race conditions:
- Each user gets a unique lock based on their user_id
- Prevents concurrent wallet modifications
- Ensures ACID compliance across complex operations

## Webhook Integration

### Stripe Webhook Events
The system automatically processes these Stripe webhook events:

**checkout.session.completed:**
```json
{
  "type": "checkout.session.completed",
  "data": {
    "object": {
      "id": "cs_test_...",
      "payment_status": "paid",
      "payment_intent": "pi_1234567890",
      "client_reference_id": "user-uuid",
      "amount_total": 1000
    }
  }
}
```

**Automatic Processing:**
1. Webhook verifies signature
2. Extracts user_id, payment_intent_id, and amount
3. Calls `credit_deposit_idempotent()` to add tokens
4. Creates wallet_entry and wallet_allocation records
5. User's balance is immediately updated

## Error Handling

### Insufficient Funds
```bash
# Example: User has 100 tokens, tries to withdraw 200
curl -X POST http://localhost:8000/wallet/withdraw \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tokens": 200}'

# Response: 400 Bad Request
{
  "detail": "Insufficient balance. Have 100, need 200"
}
```

### Daily Limit Exceeded
```bash
# Example: User tries to deposit more than daily limit
curl -X POST http://localhost:8000/wallet/deposit/checkout \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tokens": 150000, "success_url": "...", "cancel_url": "..."}'

# Response: 400 Bad Request
{
  "detail": "Daily deposit limit exceeded"
}
```

### Refund Window Exceeded
```bash
# Example: User tries to withdraw old deposits
curl -X POST http://localhost:8000/wallet/withdraw \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tokens": 500}'

# Response: 400 Bad Request
{
  "detail": "Tokens outside 90-day refund window"
}
```

### Stripe Errors
If Stripe refund fails during withdrawal:
```json
{
  "requested": 500,
  "refunded": 200,
  "stripe_refunds": ["re_1234567890"],
  "note": "Partial refund completed. Some refunds failed and are flagged for manual review."
}
```

## Testing Examples

### Complete Deposit Flow Test
```bash
# 1. Check initial wallet balance
curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/wallet

# 2. Create checkout session
curl -X POST http://localhost:8000/wallet/deposit/checkout \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tokens": 1000,
    "success_url": "https://example.com/success",
    "cancel_url": "https://example.com/cancel"
  }'

# 3. Complete payment on Stripe (manual step)
# 4. Webhook automatically processes payment
# 5. Check updated balance
curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/wallet
```

### Complete Withdrawal Flow Test
```bash
# 1. Withdraw tokens
curl -X POST http://localhost:8000/wallet/withdraw \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tokens": 500}'

# 2. Check wallet balance (should be reduced)
curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/wallet

# 3. Check Stripe dashboard for refund creation
# 4. Refunds appear in user's bank account (5-10 business days)
```

## Security Considerations

### Transaction Integrity
- All wallet operations are atomic (succeed completely or fail completely)
- Advisory locks prevent race conditions
- Database constraints ensure data consistency
- Complete audit trail for all operations

### Financial Security
- Idempotent webhook processing prevents duplicate credits
- FIFO refund processing ensures accurate refund destinations  
- Rate limiting prevents abuse
- Daily limits prevent excessive exposure

### Stripe Integration Security
- Webhook signature verification prevents spoofing
- PCI compliance through Stripe (no card data stored)
- Secure communication via HTTPS only
- Proper error handling for payment failures

## Monitoring and Analytics

### Key Metrics to Monitor
- Daily deposit volume and transaction count
- Withdrawal request volume and success rate
- Average wallet balance per user
- Stripe webhook processing latency
- Failed transaction rates and error patterns

### Financial Reconciliation
Regular reconciliation between:
- Wallet balances (sum of wallet_entries)
- Allocation balances (sum of remaining_amount)
- Stripe payment records
- Platform ledger entries

All amounts should balance to ensure financial integrity.