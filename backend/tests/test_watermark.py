#!/usr/bin/env python3
"""
Test script for the new watermarking system using the provided test image.
This demonstrates the visual watermark and EXIF metadata embedding.
"""

import sys
import os
from pathlib import Path

# Add backend to Python path (we're already in backend/tests/)
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.services.overlay import embed_watermark, overlay_code
from app.services.media import analyze_image
from PIL import Image
import piexif

def test_watermarking():
    print("🧪 Testing Chally Watermarking System")
    print("=" * 50)
    
    # Load test image
    image_path = "images/test_image.jpeg"
    if not os.path.exists(image_path):
        print(f"❌ Test image not found: {image_path}")
        return
    
    with open(image_path, 'rb') as f:
        original_data = f.read()
    
    print(f"📷 Original image size: {len(original_data):,} bytes")
    
    # Test parameters
    challenge_id = 123
    participant_id = 456
    
    # Generate expected verification code
    expected_code = overlay_code(str(challenge_id), str(participant_id), "morning")
    print(f"🔑 Expected verification code: {expected_code}")
    
    try:
        # Apply watermark
        print("\n🎨 Applying watermark...")
        slot_key = "morning"  # Test slot
        watermarked_data, verification_code = embed_watermark(
            original_data, challenge_id, participant_id, slot_key
        )
        
        print(f"✅ Watermark applied successfully!")
        print(f"📊 Watermarked image size: {len(watermarked_data):,} bytes")
        print(f"🔑 Embedded verification code: {verification_code}")
        print(f"✓ Code matches expected: {verification_code == expected_code}")
        
        # Save watermarked image for inspection
        output_path = "images/test_watermarked.jpeg"
        with open(output_path, 'wb') as f:
            f.write(watermarked_data)
        print(f"💾 Watermarked image saved as: {output_path}")
        
        # Analyze both images
        print("\n📊 Image Analysis:")
        
        # Original image
        original_mime, original_phash, original_exif = analyze_image(original_data)
        print(f"📷 Original - MIME: {original_mime}, pHash: {original_phash[:16]}...")
        
        # Watermarked image
        watermarked_mime, watermarked_phash, watermarked_exif = analyze_image(watermarked_data)
        print(f"🎨 Watermarked - MIME: {watermarked_mime}, pHash: {watermarked_phash[:16]}...")
        
        # Check EXIF metadata
        if watermarked_exif:
            print(f"📋 EXIF data found in watermarked image")
            if 'UserComment' in watermarked_exif:
                print(f"💬 UserComment: {watermarked_exif['UserComment']}")
            if 'ImageDescription' in watermarked_exif:
                print(f"📝 ImageDescription: {watermarked_exif['ImageDescription']}")
        
        # Test watermark extraction
        print("\n🔍 Watermark Extraction Test:")
        from app.services.overlay import extract_watermark_code, verify_watermark
        
        extracted_code = extract_watermark_code(watermarked_data)
        print(f"🔑 Extracted watermark code: {extracted_code}")
        print(f"✓ Extraction successful: {extracted_code is not None}")
        print(f"✓ Code matches embedded: {extracted_code == verification_code}")
        
        # Test full verification
        is_valid = verify_watermark(watermarked_data, str(challenge_id), str(participant_id), "morning")
        print(f"✅ Full watermark verification: {is_valid}")
        
        # Test watermark visibility
        print("\n👁️  Visual Inspection:")
        print("Open both images to see the watermark:")
        print(f"  - Original: {image_path}")
        print(f"  - Watermarked: {output_path}")
        print("Look for subtle 'CHALLY_XXXXX' text in the watermarked version")
        
    except Exception as e:
        print(f"❌ Error during watermarking: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_watermarking()