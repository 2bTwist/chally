# Wallet System (M7 Implementation)

## Overview

The Chally wallet system implements the M7 (Money Movement Management) pattern with FIFO (First-In-First-Out) token allocation. This ensures accurate tracking of deposit sources and enables precise refunds to original payment methods.

## Architecture Principles

### 1. FIFO Allocation Model
- **First In, First Out**: Tokens are withdrawn in the same order they were deposited
- **Lot Tracking**: Each deposit creates a distinct "lot" with metadata
- **Refund Accuracy**: Withdrawals automatically refund to original payment methods
- **Audit Trail**: Complete history of token movement between lots

### 2. ACID Compliance
- **Atomic Operations**: All wallet changes happen in database transactions
- **Consistent State**: Balance calculations always match allocation records
- **Isolated Transactions**: Concurrent operations don't interfere
- **Durable Records**: All operations persisted to database

### 3. Advisory Lock Pattern
- **User-level Locking**: Each user's wallet operations are serialized
- **Deadlock Prevention**: Consistent lock ordering prevents deadlocks
- **Performance**: Fine-grained locking for better concurrency
- **PostgreSQL Native**: Uses built-in advisory lock functionality

## Database Schema

### wallet_entries (Transaction Log)
Primary record of all wallet activity:

```sql
CREATE TABLE wallet_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    type VARCHAR(20) NOT NULL CHECK (type IN ('DEPOSIT', 'STAKE', 'PAYOUT', 'WITHDRAWAL')),
    amount INTEGER NOT NULL,
    currency VARCHAR(3) DEFAULT 'usd',
    external_id VARCHAR(255),
    note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Sign constraints ensure correct transaction direction
    CONSTRAINT positive_deposits CHECK (type != 'DEPOSIT' OR amount > 0),
    CONSTRAINT negative_stakes CHECK (type != 'STAKE' OR amount < 0),
    CONSTRAINT positive_payouts CHECK (type != 'PAYOUT' OR amount > 0),
    CONSTRAINT negative_withdrawals CHECK (type != 'WITHDRAWAL' OR amount < 0)
);

-- Indexes for performance
CREATE INDEX idx_wallet_entries_user_id ON wallet_entries(user_id);
CREATE INDEX idx_wallet_entries_external_id ON wallet_entries(external_id);
CREATE INDEX idx_wallet_entries_created_at ON wallet_entries(created_at);
```

### wallet_allocations (FIFO Lots)
Tracks individual deposit lots for FIFO processing:

```sql
CREATE TABLE wallet_allocations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    original_amount INTEGER NOT NULL CHECK (original_amount > 0),
    remaining_amount INTEGER NOT NULL CHECK (remaining_amount >= 0),
    payment_intent_id VARCHAR(255) NOT NULL,
    deposit_entry_id UUID NOT NULL REFERENCES wallet_entries(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Remaining amount cannot exceed original
    CONSTRAINT valid_remaining CHECK (remaining_amount <= original_amount)
);

-- Critical indexes for FIFO processing
CREATE INDEX idx_wallet_allocations_user_fifo ON wallet_allocations(user_id, created_at);
CREATE INDEX idx_wallet_allocations_remaining ON wallet_allocations(user_id, remaining_amount);
CREATE INDEX idx_wallet_allocations_payment_intent ON wallet_allocations(payment_intent_id);
```

### wallet_refunds (Refund Tracking)
Records refunds against original deposits:

```sql
CREATE TABLE wallet_refunds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    allocation_id UUID NOT NULL REFERENCES wallet_allocations(id),
    amount INTEGER NOT NULL CHECK (amount > 0),
    stripe_refund_id VARCHAR(255) NOT NULL,
    withdrawal_entry_id UUID NOT NULL REFERENCES wallet_entries(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Ensure unique refund tracking
CREATE INDEX idx_wallet_refunds_allocation ON wallet_refunds(allocation_id);
CREATE INDEX idx_wallet_refunds_stripe ON wallet_refunds(stripe_refund_id);
```

## Core Operations

### 1. Balance Calculation

Real-time balance calculated by summing all wallet_entries:

```python
async def wallet_balance(session: AsyncSession, user_id: UUID) -> int:
    """Calculate current wallet balance from all transactions."""
    total = await session.scalar(
        select(func.coalesce(func.sum(WalletEntry.amount), 0))
        .where(WalletEntry.user_id == user_id)
    )
    return int(total or 0)
```

**Example Balance Calculation:**
```sql
-- User's wallet_entries:
-- +1000 (DEPOSIT from $10.00)
-- -50   (STAKE for challenge A)  
-- +200  (PAYOUT from challenge B)
-- -150  (WITHDRAWAL request)

SELECT SUM(amount) FROM wallet_entries WHERE user_id = 'user-uuid';
-- Result: 1000 + (-50) + 200 + (-150) = 1000 tokens
```

### 2. Token Crediting (Deposits & Payouts)

Credits tokens and creates allocation lots:

```python
async def credit_tokens(session: AsyncSession, user_id: UUID, amount: int, 
                       external_id: str = None, note: str = None, 
                       entry_type: str = "DEPOSIT") -> bool:
    """Credit tokens to user wallet with lot tracking."""
    
    # 1. Create wallet entry
    entry = WalletEntry(
        user_id=user_id,
        type=entry_type,
        amount=amount,
        external_id=external_id,
        note=note
    )
    session.add(entry)
    await session.flush()  # Get entry.id
    
    # 2. Create allocation lot (if from external payment)
    if entry_type == "DEPOSIT" and external_id:
        allocation = WalletAllocation(
            user_id=user_id,
            original_amount=amount,
            remaining_amount=amount,
            payment_intent_id=external_id,
            deposit_entry_id=entry.id
        )
        session.add(allocation)
    
    return True
```

### 3. Token Debiting (Stakes & Withdrawals)

Debits tokens using FIFO allocation:

```python
async def debit_tokens(session: AsyncSession, user_id: UUID, amount: int, 
                      note: str = None, entry_type: str = "STAKE") -> bool:
    """Debit tokens from user wallet using FIFO allocation."""
    
    # 1. Acquire advisory lock for this user
    lock_id = hash(str(user_id)) % (2**31)  # 32-bit signed int
    await session.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": lock_id})
    
    try:
        # 2. Check current balance
        current_balance = await wallet_balance(session, user_id)
        if current_balance < amount:
            raise InsufficientFunds(f"Balance {current_balance} < required {amount}")
        
        # 3. Get allocations in FIFO order
        allocations = await session.execute(
            select(WalletAllocation)
            .where(WalletAllocation.user_id == user_id)
            .where(WalletAllocation.remaining_amount > 0)
            .order_by(WalletAllocation.created_at.asc())
        )
        
        # 4. Debit from allocations in FIFO order
        remaining_to_debit = amount
        for allocation in allocations.scalars():
            if remaining_to_debit <= 0:
                break
                
            debit_from_lot = min(remaining_to_debit, allocation.remaining_amount)
            allocation.remaining_amount -= debit_from_lot
            remaining_to_debit -= debit_from_lot
        
        # 5. Create wallet entry for the debit
        entry = WalletEntry(
            user_id=user_id,
            type=entry_type,
            amount=-amount,  # Negative for debits
            note=note
        )
        session.add(entry)
        
        return True
        
    finally:
        # 6. Release advisory lock
        await session.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": lock_id})
```

### 4. FIFO Withdrawal Processing

Processes withdrawals by refunding to original payment methods:

```python
async def process_withdrawal(session: AsyncSession, user_id: UUID, amount: int) -> dict:
    """Process withdrawal using FIFO refunds to original payment methods."""
    
    # 1. Acquire advisory lock
    lock_id = hash(str(user_id)) % (2**31)
    await session.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": lock_id})
    
    try:
        # 2. Get allocations with remaining balance (FIFO order)
        allocations = await session.execute(
            select(WalletAllocation)
            .where(WalletAllocation.user_id == user_id)
            .where(WalletAllocation.remaining_amount > 0)
            .order_by(WalletAllocation.created_at.asc())
        )
        
        # 3. Process refunds in FIFO order
        remaining_to_withdraw = amount
        stripe_refunds = []
        
        for allocation in allocations.scalars():
            if remaining_to_withdraw <= 0:
                break
            
            # Determine refund amount for this allocation
            refund_amount = min(remaining_to_withdraw, allocation.remaining_amount)
            refund_cents = refund_amount  # 1 token = 1 cent
            
            # Create Stripe refund
            stripe_refund = stripe.Refund.create(
                payment_intent=allocation.payment_intent_id,
                amount=refund_cents
            )
            
            # Update allocation
            allocation.remaining_amount -= refund_amount
            
            # Record refund
            wallet_refund = WalletRefund(
                user_id=user_id,
                allocation_id=allocation.id,
                amount=refund_amount,
                stripe_refund_id=stripe_refund.id,
                withdrawal_entry_id=None  # Set after creating entry
            )
            session.add(wallet_refund)
            
            stripe_refunds.append(stripe_refund.id)
            remaining_to_withdraw -= refund_amount
        
        # 4. Create withdrawal entry
        withdrawal_entry = WalletEntry(
            user_id=user_id,
            type="WITHDRAWAL",
            amount=-amount,
            note=f"Withdrawal processed via {len(stripe_refunds)} refund(s)"
        )
        session.add(withdrawal_entry)
        await session.flush()
        
        # 5. Update refund records with withdrawal entry reference
        await session.execute(
            update(WalletRefund)
            .where(WalletRefund.user_id == user_id)
            .where(WalletRefund.withdrawal_entry_id.is_(None))
            .values(withdrawal_entry_id=withdrawal_entry.id)
        )
        
        return {
            "requested": amount,
            "refunded": amount - remaining_to_withdraw,
            "stripe_refunds": stripe_refunds
        }
        
    finally:
        await session.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": lock_id})
```

## Advanced Features

### 1. Idempotent Deposits

Prevents duplicate processing of Stripe webhooks:

```python
async def credit_deposit_idempotent(session: AsyncSession, user_id: UUID, 
                                   external_id: str, usd_cents: int) -> bool:
    """Credit tokens from deposit, idempotent by external_id."""
    
    # Check if deposit already processed
    exists = await session.scalar(
        select(WalletEntry).where(WalletEntry.external_id == external_id)
    )
    if exists:
        return False  # Already processed
    
    # Calculate tokens (1 token = 1 cent by default)
    tokens = usd_cents // settings.token_price_usd_cents
    
    # Create deposit
    return await credit_tokens(
        session, user_id, tokens, external_id, 
        "stripe_deposit", "DEPOSIT"
    )
```

### 2. Daily Deposit Limits

Enforces configurable daily deposit limits:

```python
async def check_daily_deposit_limit(session: AsyncSession, user_id: UUID, 
                                   tokens: int) -> bool:
    """Check if deposit would exceed daily limit."""
    
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Sum today's deposits
    todays_deposits = await session.scalar(
        select(func.coalesce(func.sum(WalletEntry.amount), 0))
        .where(WalletEntry.user_id == user_id)
        .where(WalletEntry.type == 'DEPOSIT')
        .where(WalletEntry.created_at >= today_start)
    ) or 0
    
    return (todays_deposits + tokens) <= settings.max_deposit_tokens_day
```

### 3. Refund Window Enforcement

Prevents refunds outside the allowed time window:

```python
async def validate_refund_window(session: AsyncSession, user_id: UUID, 
                                amount: int) -> bool:
    """Validate that tokens being withdrawn are within refund window."""
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=settings.refund_window_days)
    
    # Get allocations within refund window
    valid_allocations = await session.execute(
        select(func.coalesce(func.sum(WalletAllocation.remaining_amount), 0))
        .where(WalletAllocation.user_id == user_id)
        .where(WalletAllocation.remaining_amount > 0)
        .where(WalletAllocation.created_at >= cutoff_date)
    )
    
    valid_amount = valid_allocations.scalar() or 0
    return amount <= valid_amount
```

## Error Handling

### Common Error Scenarios

#### 1. Insufficient Funds
```python
class InsufficientFunds(Exception):
    """Raised when user doesn't have enough tokens for operation."""
    pass

# Usage in API
try:
    await debit_tokens(session, user_id, stake_amount)
except InsufficientFunds:
    raise HTTPException(status_code=400, detail="Insufficient wallet balance")
```

#### 2. Concurrent Modification
Advisory locks prevent race conditions, but timeout handling is important:

```python
# Set lock timeout to prevent indefinite waiting
await session.execute(text("SET lock_timeout = '5s'"))
try:
    await session.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": lock_id})
    # ... wallet operations ...
except Exception as e:
    if "lock timeout" in str(e).lower():
        raise HTTPException(status_code=503, detail="Wallet temporarily unavailable")
```

#### 3. Stripe Refund Failures
```python
try:
    stripe_refund = stripe.Refund.create(
        payment_intent=payment_intent_id,
        amount=refund_cents
    )
except stripe.error.StripeError as e:
    # Log error and flag for manual review
    logger.error(f"Stripe refund failed: {e}")
    # Don't update wallet until refund succeeds
    raise HTTPException(status_code=502, detail="Payment processor error")
```

## Performance Considerations

### Database Indexing Strategy
```sql
-- Critical indexes for FIFO performance
CREATE INDEX idx_wallet_allocations_user_fifo 
ON wallet_allocations(user_id, created_at) 
WHERE remaining_amount > 0;

-- Partial index for active allocations only
CREATE INDEX idx_wallet_allocations_active 
ON wallet_allocations(user_id, remaining_amount, created_at) 
WHERE remaining_amount > 0;

-- Index for balance calculations
CREATE INDEX idx_wallet_entries_balance 
ON wallet_entries(user_id, amount);
```

### Query Optimization
```python
# Efficient FIFO allocation query
FIFO_QUERY = '''
SELECT id, remaining_amount, payment_intent_id
FROM wallet_allocations 
WHERE user_id = $1 AND remaining_amount > 0
ORDER BY created_at ASC
LIMIT 50  -- Limit to prevent large scans
'''

# Batch update for allocation modifications
BATCH_UPDATE = '''
UPDATE wallet_allocations 
SET remaining_amount = data.new_remaining
FROM (VALUES %s) AS data(id, new_remaining)
WHERE wallet_allocations.id = data.id
'''
```

### Caching Strategy
```python
# Cache wallet balance for read-heavy operations
async def get_cached_balance(user_id: UUID) -> int:
    cache_key = f"wallet:balance:{user_id}"
    cached = await redis.get(cache_key)
    
    if cached is not None:
        return int(cached)
    
    # Calculate and cache for 30 seconds
    balance = await wallet_balance(session, user_id)
    await redis.setex(cache_key, 30, balance)
    return balance
```

## Monitoring and Alerts

### Key Metrics
- **Balance Consistency**: wallet_entries sum equals available balance
- **Allocation Accuracy**: remaining_amount never exceeds original_amount
- **Refund Success Rate**: Percentage of successful Stripe refunds
- **Lock Contention**: Average advisory lock wait time
- **FIFO Efficiency**: Average allocations processed per withdrawal

### Financial Reconciliation
```python
async def validate_wallet_consistency(session: AsyncSession, user_id: UUID) -> dict:
    """Validate wallet state consistency."""
    
    # Calculate balance from entries
    entries_balance = await wallet_balance(session, user_id)
    
    # Calculate balance from allocations
    allocations_balance = await session.scalar(
        select(func.coalesce(func.sum(WalletAllocation.remaining_amount), 0))
        .where(WalletAllocation.user_id == user_id)
    ) or 0
    
    return {
        "entries_balance": entries_balance,
        "allocations_balance": allocations_balance,
        "consistent": entries_balance == allocations_balance
    }
```

## Future Enhancements

### Planned Improvements
1. **Batch Operations**: Process multiple wallet operations atomically
2. **Allocation Merging**: Combine small allocations for efficiency
3. **Predictive Caching**: Pre-calculate balances for active users
4. **Audit Snapshots**: Periodic wallet state snapshots for recovery
5. **Multi-currency Support**: Handle different token types/currencies

### Scalability Enhancements
1. **Horizontal Partitioning**: Partition tables by user_id hash
2. **Read Replicas**: Separate read/write database connections
3. **Event Sourcing**: Immutable event log for all wallet operations
4. **Async Processing**: Background queues for heavy operations
5. **Microservice Split**: Separate wallet service from main API