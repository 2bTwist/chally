# Anti-Cheat Watermarking System

## Overview

The watermarking system prevents users from submitting old/fake photos in challenges by embedding unique, verifiable codes into photos when they are captured.

## Architecture: Client-Side Watermarking

**Key Design Decision:** Watermarks are embedded **CLIENT-SIDE** (in the mobile app when photos are captured), not server-side. The backend only **verifies** watermarks.

### Why Client-Side?

1. **User Experience**: Users see the watermarked photo immediately on their device
2. **Performance**: Server doesn't process every image
3. **Proof of Capture**: Watermark proves photo was taken through the app at the right time
4. **Storage**: Only watermarked images are stored, reducing storage needs

## Components

### Backend API

#### 1. Generate Watermark Code Endpoint

```
GET /challenges/{challenge_id}/watermark-code?slot_key=YYYY-MM-DD
Authorization: Bearer <token>
```

**Purpose**: Mobile app calls this before capturing a photo to get the unique code to embed.

**Response**:
```json
{
  "challenge_id": "uuid",
  "participant_id": "uuid",
  "slot_key": "2025-10-15",
  "code": "NDIDNO",
  "watermark_text": "CHALLY_NDIDNO",
  "full_string": "CHALLY_WATERMARK:CHALLY_NDIDNO:SUBMISSION:..."
}
```

**Code Generation**: 
- Deterministic HMAC-SHA256 based on (challenge_id, participant_id, slot_key)
- Uses secret key from `OVERLAY_SECRET` environment variable
- Same parameters always generate the same code

#### 2. Verification Job

**File**: `app/jobs/verify_submission.py`

**Purpose**: After submission, verifies the watermark matches expected code.

**Process**:
1. Extract code from EXIF UserComment field
2. Generate expected code using same parameters
3. Compare extracted vs expected
4. Flag submission as `watermark_mismatch` if codes don't match

### Mobile App (To Be Implemented)

#### Watermarking Flow

1. **User initiates photo capture** in challenge context
2. **App determines slot_key** (usually current date in challenge timezone)
3. **App calls backend API** to get watermark code for (challenge_id, slot_key)
4. **User takes photo** with device camera
5. **App immediately embeds watermark**:
   - Visual overlay: Text "CHALLY_XXXXXX" in bottom-right corner
   - EXIF metadata: UserComment field with full watermark string
6. **App displays watermarked preview** to user
7. **User submits** already-watermarked image to backend

#### Implementation Reference

The backend function `embed_watermark()` in `app/services/overlay.py` shows the exact logic:

```python
def embed_watermark(image_data: bytes, challenge_id: str, participant_id: str, slot_key: str) -> bytes:
    # 1. Generate code
    code = overlay_code(challenge_id, participant_id, slot_key)
    watermark_text = f"CHALLY_{code}"
    
    # 2. Visual overlay (PIL/Pillow equivalent in React Native)
    # - Add text in bottom-right corner
    # - Subtle red-grey color: RGB(180, 60, 60)
    # - 10px padding from edges
    
    # 3. EXIF metadata (piexif equivalent in React Native)
    # - UserComment: "CHALLY_WATERMARK:CHALLY_{code}:SUBMISSION:{challenge_id}:{participant_id}:{slot_key}"
    # - Software: "Chally App v1.0"
    
    return watermarked_image_bytes
```

**React Native Libraries** (suggestions for mobile team):
- `react-native-image-manipulator` or `react-native-image-resizer` for visual overlay
- `react-native-image-picker` with EXIF writing support
- May need native modules for full EXIF metadata control

## Security Features

### Deterministic Codes

- Same (challenge, participant, slot) always generates same code
- Prevents users from submitting photos from different slots
- Backend can verify without storing codes

### Dual-Layer Protection

1. **Visual Overlay**: User-visible proof, deters casual cheating
2. **EXIF Metadata**: Hidden verification, prevents sophisticated attacks

### HMAC-SHA256

- Cryptographically secure code generation
- Secret key prevents code prediction
- 6-character codes from 32-byte digest (high entropy)

## Verification Rules

Configured in challenge `rules_json.anti_cheat`:

```json
{
  "anti_cheat": {
    "overlay_required": true,      // Require watermark verification
    "exif_required": true,          // Require EXIF timestamp
    "phash_check": "per_challenge"  // Check for duplicate images
  }
}
```

### Verification Process

1. **Watermark Check** (if `overlay_required: true`):
   - Extract code from EXIF UserComment
   - Compare with expected code
   - Reject if mismatch or missing

2. **EXIF Timestamp Check** (if `exif_required: true`):
   - Parse EXIF DateTimeOriginal
   - Verify photo taken within submission window (±5 min grace period)
   - Reject if missing or out of window

3. **Perceptual Hash Check** (if `phash_check` enabled):
   - Compare image phash with previous submissions
   - Detect duplicate/similar images
   - Reject if duplicate found

## Testing

### Test Watermark Generation

```bash
http GET "localhost:8000/challenges/{id}/watermark-code?slot_key=2025-10-15" \
  Authorization:"Bearer <token>"
```

### Verify EXIF Data

```bash
exiftool /path/to/submitted/image.jpg | grep -i "user comment"
# Should show: CHALLY_WATERMARK:CHALLY_XXXXXX:SUBMISSION:...
```

## Migration Notes

**Previous Architecture**: Server-side watermarking with RQ worker jobs

**Changes Made**:
- ✅ Removed `watermark_submission` job
- ✅ Removed watermark job enqueue from submission endpoint
- ✅ Added watermark code generation API endpoint
- ✅ Direct verification job enqueue (no watermarking step)
- ✅ Kept `embed_watermark()` as reference for mobile implementation

**Backwards Compatibility**: None needed (new feature)

## Configuration

### Environment Variables

```bash
OVERLAY_SECRET="your-secret-key-here"  # HMAC secret for code generation
```

**Important**: Change this in production and keep it secure!

## Future Enhancements

1. **Code Length**: Currently 6 chars, could be configurable per challenge
2. **Visual Customization**: Allow challenges to customize watermark appearance
3. **Multiple Codes**: Support multiple watermark codes per submission (e.g., for video frames)
4. **ML Verification**: Use ML to detect watermark removal attempts
