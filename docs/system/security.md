# Security Model

## Overview

Chally implements a comprehensive security model covering authentication, authorization, data protection, and financial security. The system follows industry best practices and compliance standards to protect user data and financial transactions.

## Authentication System

### JWT-Based Authentication

```mermaid
sequenceDiagram
    participant User
    participant API
    participant Database
    
    User->>API: POST /auth/login (email, password)
    API->>Database: Verify user credentials
    Database-->>API: User record + hashed password
    API->>API: Verify password with bcrypt
    API->>API: Generate JWT tokens
    API-->>User: Access + Refresh tokens
    
    User->>API: Protected request + Bearer token
    API->>API: Verify JWT signature + expiry
    API->>Database: Get user context
    API-->>User: Authorized response
```

### Token Management

```python
# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALG = "HS256"
ACCESS_TTL_MIN = int(os.getenv("ACCESS_TTL_MIN", "15"))      # 15 minutes
REFRESH_TTL_MIN = int(os.getenv("REFRESH_TTL_MIN", "10080")) # 7 days

def make_access_token(sub: str) -> str:
    """Generate short-lived access token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ACCESS_TTL_MIN)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def make_refresh_token(sub: str) -> str:
    """Generate long-lived refresh token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "type": "refresh", 
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=REFRESH_TTL_MIN)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)
```

### Password Security

```python
from passlib.context import CryptContext

# Password hashing configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hash password using bcrypt with automatic salt generation."""
    return pwd_context.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against stored hash."""
    return pwd_context.verify(password, password_hash)

# Password requirements (enforced client-side and API validation)
PASSWORD_REQUIREMENTS = {
    "min_length": 8,
    "require_uppercase": True,
    "require_lowercase": True, 
    "require_numbers": True,
    "require_special_chars": False,
    "max_length": 128
}
```

## Authorization Framework

### Role-Based Access Control (RBAC)

```python
from enum import Enum

class UserRole(Enum):
    USER = "user"           # Standard user - can participate in challenges
    MODERATOR = "moderator" # Can moderate content and disputes
    ADMIN = "admin"         # Full platform access
    SYSTEM = "system"       # System-level operations

class Permission(Enum):
    # Challenge permissions
    CREATE_CHALLENGE = "create_challenge"
    JOIN_CHALLENGE = "join_challenge"  
    VERIFY_SUBMISSION = "verify_submission"
    
    # Moderation permissions
    MODERATE_CONTENT = "moderate_content"
    RESOLVE_DISPUTES = "resolve_disputes"
    
    # Admin permissions
    MANAGE_USERS = "manage_users"
    VIEW_ANALYTICS = "view_analytics"
    MANAGE_PLATFORM = "manage_platform"

# Role-Permission mapping
ROLE_PERMISSIONS = {
    UserRole.USER: [
        Permission.CREATE_CHALLENGE,
        Permission.JOIN_CHALLENGE,
        Permission.VERIFY_SUBMISSION
    ],
    UserRole.MODERATOR: [
        # All user permissions plus moderation
        *ROLE_PERMISSIONS[UserRole.USER],
        Permission.MODERATE_CONTENT,
        Permission.RESOLVE_DISPUTES
    ],
    UserRole.ADMIN: [
        # All permissions
        *Permission
    ]
}
```

### Authorization Decorators

```python
from functools import wraps

def require_permission(permission: Permission):
    """Decorator to require specific permission for endpoint access."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user = kwargs.get('user') or args[-1]  # Assumes user is last param
            
            if not user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            user_permissions = ROLE_PERMISSIONS.get(user.role, [])
            
            if permission not in user_permissions:
                raise HTTPException(
                    status_code=403, 
                    detail=f"Permission required: {permission.value}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Usage example
@router.delete("/challenges/{challenge_id}")
@require_permission(Permission.MANAGE_PLATFORM)
async def delete_challenge(challenge_id: UUID, user=Depends(get_current_user)):
    """Only admins can delete challenges."""
    pass
```

### Resource-Level Authorization

```python
async def check_challenge_access(user: User, challenge: Challenge, action: str) -> bool:
    """Check if user can perform action on specific challenge."""
    
    # Creator can always modify their challenges
    if challenge.creator_id == user.id:
        return True
    
    # Participants can view and submit to challenges they joined
    if action in ["view", "submit"]:
        participant = await get_participant(challenge.id, user.id)
        return participant is not None
    
    # Public challenges can be viewed by anyone
    if action == "view" and challenge.visibility == "public":
        return True
    
    # Moderators can moderate any challenge
    if user.role in [UserRole.MODERATOR, UserRole.ADMIN]:
        return True
    
    return False
```

## Data Protection

### Input Validation and Sanitization

```python
from pydantic import BaseModel, validator, Field
import html
import re

class CreateChallengeRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(max_length=2000)
    stake_amount: int = Field(gt=0, le=10000)
    
    @validator('title', 'description')
    def sanitize_text(cls, v):
        """Remove potentially dangerous HTML/script content."""
        if not v:
            return v
        
        # HTML escape
        v = html.escape(v.strip())
        
        # Remove any remaining script-like content
        v = re.sub(r'<script[^>]*>.*?</script>', '', v, flags=re.IGNORECASE | re.DOTALL)
        v = re.sub(r'javascript:', '', v, flags=re.IGNORECASE)
        
        return v
    
    @validator('stake_amount')
    def validate_stake_amount(cls, v):
        """Ensure stake amount is within reasonable bounds."""
        if v <= 0:
            raise ValueError('Stake amount must be positive')
        if v > 10000:  # $100 max stake
            raise ValueError('Stake amount too high')
        return v
```

### SQL Injection Prevention

```python
# Using SQLAlchemy ORM with parameterized queries
async def get_user_challenges(session: AsyncSession, user_id: UUID, status: str = None):
    """Get challenges for user with optional status filter."""
    
    query = select(Challenge).where(Challenge.creator_id == user_id)
    
    # Parameterized query - safe from SQL injection
    if status:
        query = query.where(Challenge.status == status)
    
    result = await session.execute(query)
    return result.scalars().all()

# Raw SQL when necessary - always use parameters
async def get_wallet_balance_raw(session: AsyncSession, user_id: UUID) -> int:
    """Example of safe raw SQL usage."""
    result = await session.execute(
        text("SELECT COALESCE(SUM(amount), 0) FROM wallet_entries WHERE user_id = :user_id"),
        {"user_id": user_id}
    )
    return result.scalar() or 0
```

### Cross-Site Scripting (XSS) Prevention

```python
from markupsafe import escape

def sanitize_user_content(content: str) -> str:
    """Sanitize user-generated content for safe display."""
    
    if not content:
        return ""
    
    # HTML escape all content
    safe_content = escape(content)
    
    # Allow basic markdown-style formatting
    safe_content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', safe_content)
    safe_content = re.sub(r'\*(.*?)\*', r'<em>\1</em>', safe_content)
    
    # Convert URLs to links (safely)
    url_pattern = re.compile(r'https?://[^\s<>"]+')
    safe_content = url_pattern.sub(
        lambda m: f'<a href="{escape(m.group())}" target="_blank" rel="noopener noreferrer">{escape(m.group())}</a>',
        safe_content
    )
    
    return safe_content
```

## Financial Security

### Transaction Integrity

```python
from sqlalchemy import text

async def secure_wallet_operation(session: AsyncSession, user_id: UUID, operation: callable):
    """Execute wallet operation with advisory locks and transaction safety."""
    
    # Calculate lock ID from user ID (32-bit signed integer)
    lock_id = hash(str(user_id)) % (2**31)
    
    # Acquire advisory lock
    await session.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": lock_id})
    
    try:
        # Begin nested transaction
        async with session.begin_nested():
            # Execute the wallet operation
            result = await operation(session, user_id)
            
            # Verify wallet consistency after operation
            if not await verify_wallet_consistency(session, user_id):
                raise Exception("Wallet consistency check failed")
            
            return result
            
    except Exception as e:
        # Transaction will be rolled back automatically
        logger.error(f"Wallet operation failed for user {user_id}: {e}")
        raise
        
    finally:
        # Always release the lock
        await session.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": lock_id})

async def verify_wallet_consistency(session: AsyncSession, user_id: UUID) -> bool:
    """Verify wallet state consistency."""
    
    # Check that balance equals sum of all entries
    balance_from_entries = await session.scalar(
        select(func.sum(WalletEntry.amount))
        .where(WalletEntry.user_id == user_id)
    ) or 0
    
    # Check that allocation remaining amounts are consistent
    allocation_balance = await session.scalar(
        select(func.sum(WalletAllocation.remaining_amount))
        .where(WalletAllocation.user_id == user_id)
    ) or 0
    
    return balance_from_entries == allocation_balance
```

### Stripe Security

```python
import stripe
import hmac
import hashlib

def verify_stripe_webhook(payload: bytes, signature: str) -> dict:
    """Verify Stripe webhook signature to prevent spoofing."""
    
    # Parse signature header
    elements = signature.split(',')
    signature_dict = {}
    
    for element in elements:
        key, value = element.split('=')
        signature_dict[key] = value
    
    # Get timestamp and signatures
    timestamp = signature_dict.get('t')
    v1_signature = signature_dict.get('v1')
    
    if not timestamp or not v1_signature:
        raise ValueError("Invalid signature format")
    
    # Create expected signature
    signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
    expected_signature = hmac.new(
        settings.stripe_webhook_secret.encode('utf-8'),
        signed_payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Verify signature
    if not hmac.compare_digest(expected_signature, v1_signature):
        raise ValueError("Invalid signature")
    
    # Check timestamp (prevent replay attacks)
    current_time = time.time()
    if abs(current_time - int(timestamp)) > 300:  # 5 minute tolerance
        raise ValueError("Timestamp too old")
    
    # Parse and return event
    return json.loads(payload.decode('utf-8'))
```

### Rate Limiting and DDoS Protection

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Create rate limiter
limiter = Limiter(key_func=get_remote_address)

# Apply to FastAPI app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Rate limit authentication endpoints
@router.post("/auth/login")
@limiter.limit("5/minute")  # 5 login attempts per minute per IP
async def login(request: Request, credentials: LoginRequest):
    """Login with rate limiting."""
    pass

@router.post("/auth/register") 
@limiter.limit("2/minute")  # 2 registrations per minute per IP
async def register(request: Request, user_data: RegisterRequest):
    """Registration with rate limiting.""" 
    pass

# Rate limit financial operations
@router.post("/wallet/deposit/checkout")
@limiter.limit("10/hour")  # 10 deposit attempts per hour per IP
async def create_deposit_checkout(request: Request, payload: CreateDepositRequest):
    """Deposit with rate limiting."""
    pass
```

## File Upload Security

### Secure File Handling

```python
import magic
from pathlib import Path

ALLOWED_MIME_TYPES = {
    'image/jpeg', 'image/png', 'image/gif', 'image/webp',
    'video/mp4', 'video/quicktime', 'video/webm',
    'application/pdf', 'text/plain'
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

async def validate_uploaded_file(file: UploadFile) -> dict:
    """Validate uploaded file for security."""
    
    # Check file size
    if file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")
    
    # Read file content for validation
    content = await file.read()
    await file.seek(0)  # Reset file pointer
    
    # Detect actual MIME type (don't trust client)
    detected_mime = magic.from_buffer(content, mime=True)
    
    if detected_mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415, 
            detail=f"File type not allowed: {detected_mime}"
        )
    
    # Generate secure filename
    secure_filename = generate_secure_filename(file.filename, detected_mime)
    
    # Scan for malicious content (basic check)
    if contains_malicious_content(content):
        raise HTTPException(status_code=400, detail="File contains malicious content")
    
    return {
        "original_filename": file.filename,
        "secure_filename": secure_filename,
        "mime_type": detected_mime,
        "size": len(content),
        "content": content
    }

def generate_secure_filename(original: str, mime_type: str) -> str:
    """Generate secure filename for storage."""
    
    # Get file extension from MIME type
    extensions = {
        'image/jpeg': '.jpg',
        'image/png': '.png', 
        'video/mp4': '.mp4',
        'application/pdf': '.pdf'
    }
    
    extension = extensions.get(mime_type, '')
    secure_name = f"{uuid.uuid4()}{extension}"
    
    return secure_name

def contains_malicious_content(content: bytes) -> bool:
    """Basic malicious content detection."""
    
    # Check for embedded scripts in images/documents
    dangerous_patterns = [
        b'<script',
        b'javascript:',
        b'vbscript:',
        b'onload=',
        b'onerror='
    ]
    
    content_lower = content.lower()
    return any(pattern in content_lower for pattern in dangerous_patterns)
```

### S3/MinIO Security

```python
import boto3
from botocore.exceptions import ClientError

def create_secure_s3_client():
    """Create S3 client with security best practices."""
    
    return boto3.client(
        's3',
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name='us-east-1',
        config=boto3.session.Config(
            signature_version='s3v4',  # Use latest signature version
            s3={'addressing_style': 'path'}  # Path-style addressing
        )
    )

async def upload_file_securely(file_content: bytes, key: str) -> str:
    """Upload file with security measures."""
    
    s3_client = create_secure_s3_client()
    
    try:
        # Upload with server-side encryption
        s3_client.put_object(
            Bucket=settings.s3_bucket_uploads,
            Key=key,
            Body=file_content,
            ServerSideEncryption='AES256',  # Encrypt at rest
            Metadata={
                'uploaded-by': 'chally-api',
                'upload-time': datetime.now(timezone.utc).isoformat()
            }
        )
        
        return key
        
    except ClientError as e:
        logger.error(f"S3 upload failed: {e}")
        raise HTTPException(status_code=500, detail="File upload failed")

def generate_presigned_url(key: str, expiration: int = 3600) -> str:
    """Generate secure presigned URL for file access."""
    
    s3_client = create_secure_s3_client()
    
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.s3_bucket_uploads,
                'Key': key
            },
            ExpiresIn=expiration,  # URL expires in 1 hour
            HttpMethod='GET'
        )
        return url
        
    except ClientError as e:
        logger.error(f"Presigned URL generation failed: {e}")
        raise HTTPException(status_code=500, detail="File access failed")
```

## Monitoring and Incident Response

### Security Logging

```python
import structlog

# Security-focused logger
security_logger = structlog.get_logger("security")

class SecurityEvents:
    """Log security-relevant events."""
    
    @staticmethod
    def log_login_attempt(user_email: str, success: bool, ip_address: str):
        """Log login attempts for security monitoring."""
        security_logger.info(
            "login_attempt",
            user_email=user_email,
            success=success,
            ip_address=ip_address,
            timestamp=datetime.now(timezone.utc),
            event_type="authentication"
        )
    
    @staticmethod
    def log_failed_authorization(user_id: str, resource: str, action: str):
        """Log failed authorization attempts."""
        security_logger.warning(
            "authorization_failed",
            user_id=user_id,
            resource=resource,
            action=action,
            timestamp=datetime.now(timezone.utc),
            event_type="authorization"
        )
    
    @staticmethod
    def log_suspicious_activity(user_id: str, activity: str, details: dict):
        """Log suspicious user activity."""
        security_logger.warning(
            "suspicious_activity",
            user_id=user_id,
            activity=activity,
            details=details,
            timestamp=datetime.now(timezone.utc),
            event_type="suspicious"
        )
```

### Intrusion Detection

```python
from collections import defaultdict
import asyncio

class IntrusionDetection:
    """Basic intrusion detection system."""
    
    def __init__(self):
        self.failed_attempts = defaultdict(list)
        self.blocked_ips = set()
    
    def record_failed_login(self, ip_address: str):
        """Record failed login attempt."""
        now = datetime.now(timezone.utc)
        self.failed_attempts[ip_address].append(now)
        
        # Clean old attempts (older than 1 hour)
        cutoff = now - timedelta(hours=1)
        self.failed_attempts[ip_address] = [
            attempt for attempt in self.failed_attempts[ip_address]
            if attempt > cutoff
        ]
        
        # Block IP if too many failed attempts
        if len(self.failed_attempts[ip_address]) > 10:
            self.blocked_ips.add(ip_address)
            security_logger.warning(
                "ip_blocked",
                ip_address=ip_address,
                failed_attempts=len(self.failed_attempts[ip_address])
            )
    
    def is_blocked(self, ip_address: str) -> bool:
        """Check if IP is blocked."""
        return ip_address in self.blocked_ips
    
    async def cleanup_blocked_ips(self):
        """Periodic cleanup of blocked IPs."""
        while True:
            # Unblock IPs after 24 hours (in production, use Redis for persistence)
            await asyncio.sleep(86400)  # 24 hours
            self.blocked_ips.clear()

# Global intrusion detection instance
intrusion_detector = IntrusionDetection()

# Middleware to check blocked IPs
async def intrusion_detection_middleware(request: Request, call_next):
    """Middleware to block suspicious IPs."""
    
    client_ip = get_remote_address(request)
    
    if intrusion_detector.is_blocked(client_ip):
        raise HTTPException(
            status_code=429,
            detail="IP temporarily blocked due to suspicious activity"
        )
    
    response = await call_next(request)
    return response
```

## Compliance and Privacy

### GDPR Compliance

```python
@router.delete("/users/{user_id}/data")
@require_permission(Permission.MANAGE_USERS)
async def delete_user_data(user_id: UUID, session: AsyncSession = Depends(get_session)):
    """Delete all user data for GDPR compliance."""
    
    # Anonymize rather than delete financial records (regulatory requirement)
    await session.execute(
        update(WalletEntry)
        .where(WalletEntry.user_id == user_id)
        .values(note="anonymized_user")
    )
    
    # Delete personal data
    await session.execute(
        delete(User).where(User.id == user_id)
    )
    
    # Delete submissions and content
    await session.execute(
        delete(Submission).where(Submission.user_id == user_id)
    )
    
    await session.commit()
    
    security_logger.info(
        "user_data_deleted",
        user_id=str(user_id),
        deleted_by="admin_request",
        compliance="gdpr"
    )

@router.get("/users/{user_id}/data-export")
async def export_user_data(user_id: UUID, session: AsyncSession = Depends(get_session)):
    """Export all user data for GDPR compliance."""
    
    # Collect all user data
    user_data = await collect_user_data(session, user_id)
    
    return {
        "user_id": str(user_id),
        "exported_at": datetime.now(timezone.utc),
        "data": user_data
    }
```

### Audit Trail

```python
class AuditTrail:
    """Comprehensive audit logging for compliance."""
    
    @staticmethod
    async def log_data_access(user_id: str, accessed_by: str, data_type: str):
        """Log data access for audit purposes."""
        audit_logger.info(
            "data_accessed",
            user_id=user_id,
            accessed_by=accessed_by,
            data_type=data_type,
            timestamp=datetime.now(timezone.utc)
        )
    
    @staticmethod
    async def log_financial_transaction(transaction_type: str, amount: int, 
                                       user_id: str, external_id: str = None):
        """Log financial transactions for audit."""
        audit_logger.info(
            "financial_transaction",
            transaction_type=transaction_type,
            amount=amount,
            user_id=user_id,
            external_id=external_id,
            timestamp=datetime.now(timezone.utc)
        )
```

## Security Best Practices

### Environment Configuration

```bash
# Production security environment variables
JWT_SECRET=complex-random-secret-256-bits-minimum
STRIPE_SECRET_KEY=sk_live_actual_production_key
DATABASE_URL=postgresql://secure_user:complex_password@localhost/db

# Security headers
CORS_ORIGINS=https://chally.com
SECURE_COOKIES=true
HTTPS_ONLY=true
HSTS_ENABLED=true

# Rate limiting
REDIS_URL=redis://localhost:6379/1  # Separate DB for rate limiting
```

### Security Headers

```python
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.cors import CORSMiddleware

# Add security middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["chally.com", "*.chally.com"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=3600
)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    
    response = await call_next(request)
    
    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    return response
```

## Incident Response Plan

### Security Incident Classification

1. **Critical**: Data breach, payment fraud, system compromise
2. **High**: Authentication bypass, privilege escalation
3. **Medium**: DDoS attack, suspicious user activity
4. **Low**: Failed login attempts, minor configuration issues

### Response Procedures

```python
class IncidentResponse:
    """Security incident response procedures."""
    
    @staticmethod
    async def handle_security_incident(severity: str, description: str, 
                                     affected_users: list = None):
        """Handle security incident according to severity."""
        
        incident_id = str(uuid.uuid4())
        
        # Log incident
        security_logger.critical(
            "security_incident",
            incident_id=incident_id,
            severity=severity,
            description=description,
            affected_users=affected_users or [],
            timestamp=datetime.now(timezone.utc)
        )
        
        # Automated responses based on severity
        if severity == "critical":
            await enable_maintenance_mode()
            await notify_security_team(incident_id, description)
            await freeze_financial_operations()
        
        elif severity == "high":
            await increase_logging_level()
            await notify_security_team(incident_id, description)
        
        return incident_id
    
    @staticmethod
    async def enable_maintenance_mode():
        """Put platform in maintenance mode."""
        # Implementation would set a global flag to reject non-admin requests
        pass
    
    @staticmethod
    async def freeze_financial_operations():
        """Temporarily freeze all financial operations."""
        # Implementation would disable wallet operations
        pass
```

This comprehensive security documentation covers all major aspects of the Chally security model, from authentication and authorization to incident response procedures. The system implements defense-in-depth principles with multiple layers of security controls.