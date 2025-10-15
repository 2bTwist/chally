from __future__ import annotations
import os, hmac, hashlib, base64, io
from PIL import Image, ImageDraw, ImageFont
import piexif

_OVERLAY_SECRET = os.getenv("OVERLAY_SECRET", "dev-overlay-secret-change-me").encode()

def overlay_code(challenge_id: str, participant_id: str, slot_key: str, length: int = 6) -> str:
    """
    Deterministic 6-char code per (challenge, participant, slot).
    """
    msg = f"{challenge_id}.{participant_id}.{slot_key}".encode()
    digest = hmac.new(_OVERLAY_SECRET, msg, hashlib.sha256).digest()
    # Base32, strip padding, uppercase alpha+digits — then slice
    code = base64.b32encode(digest).decode("ascii").rstrip("=").upper()
    return code[:length]

def embed_watermark(image_data: bytes, challenge_id: str, participant_id: str, slot_key: str) -> bytes:
    """
    Embed both visual and EXIF watermarks into an image.
    Returns modified image data with watermarks.
    """
    # Generate the overlay code
    code = overlay_code(challenge_id, participant_id, slot_key)
    watermark_text = f"CHALLY_{code}"
    
    # Load the image
    img = Image.open(io.BytesIO(image_data))
    
    # Ensure we're working with RGB mode for drawing
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    # Create a copy for drawing
    watermarked = img.copy()
    draw = ImageDraw.Draw(watermarked)
    
    # Add visual watermark (bottom-right corner, subtle red)
    width, height = watermarked.size
    
    # Try to use a system font, fallback to default
    try:
        # Try common system font paths
        font_paths = [
            "/System/Library/Fonts/Arial.ttf",  # macOS
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
            "arial.ttf"  # Windows
        ]
        font = None
        for font_path in font_paths:
            try:
                font = ImageFont.truetype(font_path, 12)
                break
            except (OSError, IOError):
                continue
        
        if font is None:
            font = ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()
    
    # Calculate text position (bottom-right with padding)
    bbox = draw.textbbox((0, 0), watermark_text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = width - text_width - 10  # 10px padding from right
    y = height - text_height - 10  # 10px padding from bottom
    
    # Draw subtle red watermark (low opacity effect using grey)
    draw.text((x, y), watermark_text, fill=(180, 60, 60), font=font)  # Subtle red-grey
    
    # Add EXIF metadata watermark
    try:
        # Try to load existing EXIF data
        if img.format == 'JPEG':
            try:
                exif_dict = piexif.load(image_data)
            except Exception:
                # Create new EXIF structure if none exists
                exif_dict = {
                    "0th": {},
                    "Exif": {},
                    "GPS": {},
                    "1st": {},
                    "thumbnail": None
                }
        else:
            # For non-JPEG images, create basic EXIF structure
            exif_dict = {
                "0th": {},
                "Exif": {},
                "GPS": {},
                "1st": {},
                "thumbnail": None
            }
        
        # Add our watermark to UserComment (tag 37510)
        watermark_comment = f"CHALLY_WATERMARK:{watermark_text}:SUBMISSION:{challenge_id}:{participant_id}:{slot_key}"
        exif_dict["Exif"][piexif.ExifIFD.UserComment] = watermark_comment.encode()
        
        # Add software tag (tag 305) to indicate processing
        exif_dict["0th"][piexif.ImageIFD.Software] = "Chally App v1.0".encode()
        
    except Exception as e:
        # If EXIF processing fails, continue without it
        print(f"EXIF processing failed: {e}")
        exif_dict = None
    
    # Save the watermarked image
    output = io.BytesIO()
    
    if img.format == 'JPEG' and exif_dict:
        try:
            exif_bytes = piexif.dump(exif_dict)
            watermarked.save(output, format='JPEG', exif=exif_bytes, quality=95)
        except Exception:
            # Fallback: save without EXIF if there's an issue
            watermarked.save(output, format='JPEG', quality=95)
    else:
        # For PNG or if EXIF fails, save without EXIF
        format_to_save = img.format if img.format in ['JPEG', 'PNG'] else 'JPEG'
        watermarked.save(output, format=format_to_save, quality=95 if format_to_save == 'JPEG' else None)
    
    return output.getvalue(), code

def extract_watermark_code(image_data: bytes) -> str | None:
    """
    Extract the watermark code from an image's EXIF data.
    Returns the code if found, None otherwise.
    """
    try:
        # Try to load EXIF data
        img = Image.open(io.BytesIO(image_data))
        if img.format != 'JPEG':
            return None
            
        exif_dict = piexif.load(image_data)
        
        # Look for our watermark in UserComment
        user_comment = exif_dict.get("Exif", {}).get(piexif.ExifIFD.UserComment)
        if not user_comment:
            return None
        
        comment_str = user_comment.decode('utf-8', errors='ignore')
        
        # Parse our watermark format: "CHALLY_WATERMARK:CHALLY_XXXXX:SUBMISSION:..."
        if comment_str.startswith("CHALLY_WATERMARK:"):
            parts = comment_str.split(":")
            if len(parts) >= 2:
                watermark_text = parts[1]  # Should be "CHALLY_XXXXX"
                if watermark_text.startswith("CHALLY_"):
                    return watermark_text.replace("CHALLY_", "")
        
        return None
    except Exception:
        return None

def verify_watermark(image_data: bytes, challenge_id: str, participant_id: str, slot_key: str) -> bool:
    """
    Verify if the image contains the expected watermark for the given parameters.
    """
    expected_code = overlay_code(challenge_id, participant_id, slot_key)
    extracted_code = extract_watermark_code(image_data)
    
    return extracted_code == expected_code if extracted_code else False