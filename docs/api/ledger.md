# Ledger API

## Overview

The Ledger API provides comprehensive transaction history, analytics, and financial reporting for the Chally platform. It tracks all token movements, platform revenue, and provides detailed audit trails for compliance and analysis.

## Base URL
```
http://localhost:8000/ledger
```

## Authentication
All ledger endpoints require authentication with a valid access token:
```
Authorization: Bearer <access_token>
```

## Transaction Types

The ledger system tracks various transaction types:

- **DEPOSIT**: User deposits via Stripe payment
- **WITHDRAWAL**: User withdraws to external payment method
- **STAKE_PAYMENT**: User pays stake to join challenge
- **STAKE_REFUND**: Stake returned (rare, specific conditions)
- **CHALLENGE_PAYOUT**: Winner receives share of challenge pool
- **PLATFORM_REVENUE**: Platform captures revenue from failed challenges
- **ADJUSTMENT**: Manual admin adjustment (with approval workflow)

## Endpoints

### Get Transaction History

**Endpoint:** `GET /ledger/transactions`

**Description:** Get paginated transaction history with filtering options.

**Query Parameters:**
- **user_id** (string, optional): Filter transactions for specific user (admin only)
- **transaction_type** (string, optional): Filter by transaction type
- **challenge_id** (string, optional): Filter by specific challenge
- **date_from** (string, optional): ISO date - transactions after this date
- **date_to** (string, optional): ISO date - transactions before this date
- **amount_min** (integer, optional): Minimum transaction amount in tokens
- **amount_max** (integer, optional): Maximum transaction amount in tokens
- **status** (string, optional): Filter by status (`pending`, `completed`, `failed`)
- **limit** (integer, optional): Results per page (default: 50, max: 500)
- **offset** (integer, optional): Results to skip (default: 0)
- **order_by** (string, optional): Sort field (`created_at`, `amount`) (default: `created_at`)
- **order_direction** (string, optional): Sort direction (`asc`, `desc`) (default: `desc`)

**Response (200 OK):**
```json
{
  "transactions": [
    {
      "id": "tx-550e8400-e29b-41d4-a716-446655440000",
      "user_id": "user-uuid",
      "username": "alice",
      "transaction_type": "CHALLENGE_PAYOUT",
      "amount": 167,
      "balance_before": 1250,
      "balance_after": 1417,
      "challenge_id": "challenge-uuid",
      "challenge_title": "30-Day Push-up Challenge",
      "description": "Winner payout - 1 of 3 winners",
      "metadata": {
        "total_pool": 500,
        "winner_count": 3,
        "position": 1,
        "challenge_participants": 10
      },
      "status": "completed",
      "created_at": "2024-01-31T23:59:59Z",
      "processed_at": "2024-01-31T23:59:59Z",
      "stripe_payment_intent_id": null,
      "reference_id": "payout-batch-20240131"
    },
    {
      "id": "tx-550e8400-e29b-41d4-a716-446655440001",
      "user_id": "user-uuid",
      "username": "alice",
      "transaction_type": "STAKE_PAYMENT",
      "amount": -50,
      "balance_before": 1300,
      "balance_after": 1250,
      "challenge_id": "challenge-uuid",
      "challenge_title": "30-Day Push-up Challenge",
      "description": "Stake payment to join challenge",
      "metadata": {
        "stake_amount": 50,
        "challenge_participants": 1,
        "joined_as_participant": true
      },
      "status": "completed",
      "created_at": "2024-01-01T10:00:00Z",
      "processed_at": "2024-01-01T10:00:00Z",
      "stripe_payment_intent_id": null,
      "reference_id": "stake-payment-20240101"
    }
  ],
  "total": 247,
  "limit": 50,
  "offset": 0,
  "filters_applied": {
    "transaction_type": null,
    "challenge_id": null,
    "date_from": null,
    "date_to": null
  },
  "summary": {
    "total_amount": 117,
    "deposit_total": 500,
    "withdrawal_total": -150,
    "stake_payments": -300,
    "challenge_payouts": 567,
    "net_change": 117
  }
}
```

### Get User Balance History

**Endpoint:** `GET /ledger/balance-history`

**Description:** Get user's wallet balance over time with transaction details.

**Query Parameters:**
- **user_id** (string, optional): Specific user ID (admin only, defaults to authenticated user)
- **date_from** (string, optional): ISO date for history start
- **date_to** (string, optional): ISO date for history end
- **granularity** (string, optional): Data points (`daily`, `weekly`, `monthly`) (default: `daily`)

**Response (200 OK):**
```json
{
  "user_id": "user-uuid",
  "username": "alice",
  "current_balance": 1417,
  "balance_history": [
    {
      "date": "2024-01-31",
      "starting_balance": 1250,
      "ending_balance": 1417,
      "total_credits": 167,
      "total_debits": 0,
      "transaction_count": 1,
      "largest_transaction": 167,
      "primary_activity": "CHALLENGE_PAYOUT"
    },
    {
      "date": "2024-01-01",
      "starting_balance": 1300,
      "ending_balance": 1250,
      "total_credits": 0,
      "total_debits": 50,
      "transaction_count": 1,
      "largest_transaction": -50,
      "primary_activity": "STAKE_PAYMENT"
    }
  ],
  "summary": {
    "period_start": "2024-01-01",
    "period_end": "2024-01-31",
    "starting_balance": 1300,
    "ending_balance": 1417,
    "net_change": 117,
    "total_transactions": 2,
    "average_daily_change": 3.77
  }
}
```

### Get Challenge Financial Report

**Endpoint:** `GET /ledger/challenges/{challenge_id}/report`

**Description:** Detailed financial report for a specific challenge.

**Response (200 OK):**
```json
{
  "challenge_id": "challenge-uuid",
  "challenge_title": "30-Day Push-up Challenge",
  "challenge_status": "paid_out",
  "creator_id": "creator-uuid",
  "financial_summary": {
    "total_participants": 10,
    "stake_amount": 50,
    "total_stakes_collected": 500,
    "successful_participants": 3,
    "failed_participants": 7,
    "total_payouts": 500,
    "platform_revenue": 0,
    "payout_per_winner": 167
  },
  "stake_payments": [
    {
      "user_id": "user-uuid-1",
      "username": "alice",
      "amount": 50,
      "transaction_id": "tx-uuid-1",
      "paid_at": "2024-01-01T10:00:00Z"
    }
  ],
  "payouts": [
    {
      "user_id": "user-uuid-1",
      "username": "alice",
      "amount": 167,
      "transaction_id": "tx-uuid-payout-1",
      "paid_at": "2024-01-31T23:59:59Z",
      "winner_rank": 1
    }
  ],
  "timeline": [
    {
      "date": "2024-01-01T00:00:00Z",
      "event": "challenge_created",
      "participants": 1,
      "total_stakes": 50
    },
    {
      "date": "2024-01-31T23:59:59Z",
      "event": "challenge_ended",
      "participants": 10,
      "total_stakes": 500
    },
    {
      "date": "2024-01-31T23:59:59Z",
      "event": "payouts_processed",
      "winners": 3,
      "total_paid": 500
    }
  ]
}
```

### Get Platform Analytics

**Endpoint:** `GET /ledger/analytics`

**Description:** Platform-wide financial analytics and metrics (admin only).

**Query Parameters:**
- **date_from** (string, optional): ISO date for analytics period start
- **date_to** (string, optional): ISO date for analytics period end
- **granularity** (string, optional): Data granularity (`daily`, `weekly`, `monthly`)

**Response (200 OK):**
```json
{
  "period": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2024-01-31T23:59:59Z",
    "duration_days": 31
  },
  "financial_overview": {
    "total_deposits": 15750,
    "total_withdrawals": 8200,
    "total_stakes_collected": 12500,
    "total_payouts": 11800,
    "platform_revenue": 700,
    "net_token_flow": 7550,
    "active_user_wallets": 1247,
    "total_wallet_balance": 45300
  },
  "challenge_metrics": {
    "total_challenges": 45,
    "completed_challenges": 38,
    "active_challenges": 7,
    "average_participants_per_challenge": 8.2,
    "average_success_rate": 0.67,
    "total_participants": 369,
    "successful_participants": 247
  },
  "revenue_breakdown": {
    "failed_challenge_stakes": 650,
    "platform_fees": 50,
    "withdrawal_fees": 0,
    "total_revenue": 700
  },
  "transaction_volume": {
    "total_transactions": 1834,
    "deposits": 157,
    "withdrawals": 82,
    "stake_payments": 369,
    "payouts": 247,
    "adjustments": 3
  },
  "daily_metrics": [
    {
      "date": "2024-01-31",
      "transactions": 23,
      "total_volume": 1150,
      "new_users": 5,
      "active_challenges": 7,
      "payouts": 3
    }
  ]
}
```

### Export Transaction Data

**Endpoint:** `GET /ledger/export`

**Description:** Export transaction data in various formats for accounting and analysis.

**Query Parameters:**
- **format** (string, required): Export format (`csv`, `json`, `xlsx`)
- **user_id** (string, optional): Filter to specific user (admin only)
- **date_from** (string, required): ISO date for export start
- **date_to** (string, required): ISO date for export end
- **transaction_types** (array, optional): Filter by transaction types
- **include_metadata** (boolean, optional): Include transaction metadata (default: false)

**Response:**
- **200 OK**: File download with appropriate headers
- **Content-Type**: `text/csv`, `application/json`, or `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`

**CSV Format Example:**
```csv
transaction_id,user_id,username,transaction_type,amount,balance_before,balance_after,challenge_id,description,status,created_at,processed_at
tx-uuid-1,user-uuid-1,alice,DEPOSIT,500,0,500,,Stripe deposit - $50.00,completed,2024-01-01T10:00:00Z,2024-01-01T10:00:01Z
tx-uuid-2,user-uuid-1,alice,STAKE_PAYMENT,-50,500,450,challenge-uuid-1,Stake payment for Push-up Challenge,completed,2024-01-01T11:00:00Z,2024-01-01T11:00:00Z
```

### Get Transaction Details

**Endpoint:** `GET /ledger/transactions/{transaction_id}`

**Description:** Get detailed information about a specific transaction.

**Response (200 OK):**
```json
{
  "id": "tx-550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user-uuid",
  "username": "alice",
  "transaction_type": "DEPOSIT",
  "amount": 500,
  "balance_before": 950,
  "balance_after": 1450,
  "challenge_id": null,
  "challenge_title": null,
  "description": "Stripe deposit - $50.00 USD",
  "metadata": {
    "stripe_payment_intent_id": "pi_1234567890",
    "stripe_charge_id": "ch_1234567890",
    "usd_amount": 50.00,
    "exchange_rate": 10.0,
    "payment_method": "card",
    "card_last4": "4242",
    "card_brand": "visa"
  },
  "status": "completed",
  "created_at": "2024-01-15T10:00:00Z",
  "processed_at": "2024-01-15T10:00:02Z",
  "stripe_payment_intent_id": "pi_1234567890",
  "reference_id": "deposit-20240115-001",
  "related_transactions": [],
  "audit_trail": [
    {
      "timestamp": "2024-01-15T10:00:00Z",
      "action": "transaction_created",
      "details": "Deposit initiated via Stripe",
      "system_user": "stripe_webhook"
    },
    {
      "timestamp": "2024-01-15T10:00:02Z",
      "action": "transaction_completed",
      "details": "Payment confirmed, wallet credited",
      "system_user": "payment_processor"
    }
  ]
}
```

### User Financial Summary

**Endpoint:** `GET /ledger/summary`

**Description:** Get financial summary for the authenticated user.

**Query Parameters:**
- **period** (string, optional): Summary period (`week`, `month`, `quarter`, `year`, `all_time`) (default: `month`)

**Response (200 OK):**
```json
{
  "user_id": "user-uuid",
  "username": "alice",
  "period": "month",
  "period_start": "2024-01-01T00:00:00Z",
  "period_end": "2024-01-31T23:59:59Z",
  "current_balance": 1417,
  "financial_summary": {
    "total_deposits": 1000,
    "total_withdrawals": 200,
    "total_stakes_paid": 300,
    "total_payouts_received": 917,
    "net_change": 1417,
    "return_on_stakes": 305.7
  },
  "challenge_performance": {
    "challenges_joined": 6,
    "challenges_completed": 4,
    "challenges_won": 4,
    "success_rate": 66.7,
    "total_stakes_paid": 300,
    "total_winnings": 917,
    "net_profit": 617,
    "roi_percentage": 205.7
  },
  "transaction_breakdown": {
    "deposits": 2,
    "withdrawals": 1,
    "stake_payments": 6,
    "challenge_payouts": 4,
    "adjustments": 0,
    "total_transactions": 13
  },
  "monthly_trend": [
    {
      "month": "2024-01",
      "ending_balance": 1417,
      "net_change": 1417,
      "challenges_won": 4
    }
  ]
}
```

## Advanced Analytics

### Revenue Analytics (Admin Only)

**Endpoint:** `GET /ledger/admin/revenue-analytics`

**Description:** Detailed platform revenue analysis for business intelligence.

**Query Parameters:**
- **date_from** (string, required): Analysis period start
- **date_to** (string, required): Analysis period end
- **breakdown_by** (string, optional): Group results by (`day`, `week`, `month`, `challenge_type`)

**Response (200 OK):**
```json
{
  "period": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2024-01-31T23:59:59Z"
  },
  "revenue_sources": {
    "failed_challenge_stakes": {
      "amount": 650,
      "percentage": 92.9,
      "challenge_count": 7,
      "average_per_challenge": 92.9
    },
    "platform_fees": {
      "amount": 50,
      "percentage": 7.1,
      "transaction_count": 25,
      "average_per_transaction": 2.0
    }
  },
  "challenge_revenue_analysis": {
    "total_challenges": 45,
    "revenue_generating_challenges": 7,
    "revenue_rate": 15.6,
    "average_revenue_per_failed_challenge": 92.9,
    "top_revenue_challenges": [
      {
        "challenge_id": "challenge-uuid-1",
        "title": "Failed Fitness Challenge",
        "participants": 12,
        "winners": 0,
        "revenue": 150,
        "stake_amount": 25
      }
    ]
  },
  "user_behavior_impact": {
    "average_user_lifetime_value": 245.5,
    "user_retention_rate": 78.4,
    "average_challenges_per_user": 3.2,
    "success_rate_impact_on_revenue": {
      "high_success_users": {"revenue_per_user": 45.2, "percentage": 65},
      "low_success_users": {"revenue_per_user": 125.8, "percentage": 35}
    }
  },
  "forecasting": {
    "projected_monthly_revenue": 850,
    "growth_rate": 15.2,
    "revenue_confidence_interval": {"lower": 720, "upper": 980}
  }
}
```

### Audit Trail

**Endpoint:** `GET /ledger/audit-trail`

**Description:** Comprehensive audit trail for compliance and security monitoring.

**Query Parameters:**
- **user_id** (string, optional): Filter by user (admin only)
- **action_type** (string, optional): Filter by action type
- **date_from** (string, optional): Audit period start
- **date_to** (string, optional): Audit period end
- **include_system_actions** (boolean, optional): Include automated system actions

**Response (200 OK):**
```json
{
  "audit_entries": [
    {
      "id": "audit-uuid-1",
      "timestamp": "2024-01-15T10:00:00Z",
      "user_id": "user-uuid",
      "username": "alice",
      "action_type": "wallet_credit",
      "transaction_id": "tx-uuid",
      "amount": 500,
      "balance_before": 950,
      "balance_after": 1450,
      "ip_address": "192.168.1.100",
      "user_agent": "Chally Mobile/1.0",
      "details": {
        "source": "stripe_deposit",
        "payment_intent": "pi_1234567890",
        "automated": true
      }
    }
  ],
  "summary": {
    "total_entries": 1247,
    "date_range": {
      "start": "2024-01-01T00:00:00Z",
      "end": "2024-01-31T23:59:59Z"
    },
    "action_breakdown": {
      "wallet_credit": 567,
      "wallet_debit": 428,
      "admin_adjustment": 3,
      "system_automation": 249
    }
  }
}
```

## Error Handling

### Common Error Scenarios

#### Insufficient Permissions for User Data
```bash
curl -X GET "http://localhost:8000/ledger/transactions?user_id=other-user-uuid" \
  -H "Authorization: Bearer NON_ADMIN_TOKEN"

# Response: 403 Forbidden
{
  "detail": "Insufficient permissions to access other user's transaction data."
}
```

#### Invalid Date Range
```bash
curl -X GET "http://localhost:8000/ledger/transactions?date_from=2024-01-31&date_to=2024-01-01" \
  -H "Authorization: Bearer TOKEN"

# Response: 400 Bad Request
{
  "detail": "Invalid date range: date_from must be before date_to."
}
```

#### Transaction Not Found
```bash
curl -X GET http://localhost:8000/ledger/transactions/invalid-uuid \
  -H "Authorization: Bearer TOKEN"

# Response: 404 Not Found
{
  "detail": "Transaction not found or access denied."
}
```

#### Export Too Large
```bash
curl -X GET "http://localhost:8000/ledger/export?format=csv&date_from=2020-01-01&date_to=2024-12-31" \
  -H "Authorization: Bearer TOKEN"

# Response: 400 Bad Request
{
  "detail": "Export would contain 50,000+ records. Please narrow date range or contact support for bulk export."
}
```

## Testing Examples

### Complete Ledger Analysis Flow
```bash
# 1. Get recent transactions
curl -X GET "http://localhost:8000/ledger/transactions?limit=10" \
  -H "Authorization: Bearer $TOKEN"

# 2. Get balance history for current month
curl -X GET "http://localhost:8000/ledger/balance-history?date_from=2024-01-01&granularity=daily" \
  -H "Authorization: Bearer $TOKEN"

# 3. Get financial summary
curl -X GET "http://localhost:8000/ledger/summary?period=month" \
  -H "Authorization: Bearer $TOKEN"

# 4. Export transactions as CSV
curl -X GET "http://localhost:8000/ledger/export?format=csv&date_from=2024-01-01&date_to=2024-01-31" \
  -H "Authorization: Bearer $TOKEN" \
  -o transactions_january.csv

# 5. Get specific challenge financial report
curl -X GET "http://localhost:8000/ledger/challenges/$CHALLENGE_ID/report" \
  -H "Authorization: Bearer $TOKEN"
```

### Admin Analytics Example
```bash
# Platform-wide analytics (admin only)
curl -X GET "http://localhost:8000/ledger/analytics?date_from=2024-01-01&date_to=2024-01-31&granularity=daily" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Revenue analysis
curl -X GET "http://localhost:8000/ledger/admin/revenue-analytics?date_from=2024-01-01&date_to=2024-01-31" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Audit trail review
curl -X GET "http://localhost:8000/ledger/audit-trail?date_from=2024-01-31&include_system_actions=false" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

## Data Retention and Compliance

### Data Retention Policy
- **Transaction Records**: Retained indefinitely for financial compliance
- **Audit Trail**: 7 years retention for regulatory compliance
- **Personal Data**: Subject to user deletion requests (GDPR compliance)
- **Analytics Data**: Aggregated data retained indefinitely, personal identifiers removed after 2 years

### Compliance Features
- **GDPR**: Right to deletion, data portability, access requests
- **Financial Regulations**: Complete audit trail, immutable transaction records
- **Tax Reporting**: Export capabilities for tax preparation
- **Data Encryption**: All financial data encrypted at rest and in transit

### Backup and Recovery
- **Daily Backups**: Complete transaction database backup
- **Point-in-Time Recovery**: Up to 30 days of transaction history recovery
- **Disaster Recovery**: Cross-region backup replication
- **Data Integrity Checks**: Daily verification of transaction consistency

## Business Rules Summary

### Transaction Processing
- All transactions are ACID compliant
- Immutable transaction records once processed
- Real-time balance updates with advisory locks
- Automatic reconciliation and consistency checks

### Financial Reporting
- Real-time analytics and reporting
- Export capabilities for accounting integration
- Comprehensive audit trail for compliance
- User-level and platform-level insights

### Access Control
- Users can only access their own transaction data
- Admins have access to all platform data
- Role-based permissions for different data types
- Audit logging for all data access

### Data Accuracy
- Double-entry bookkeeping principles
- Automatic balance verification
- Transaction reversal capabilities for errors
- Reconciliation with external payment systems (Stripe)