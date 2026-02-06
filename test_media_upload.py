"""
Test script to verify media upload functionality locally
"""
import os
import sys
import struct
import zlib

def create_minimal_png(width=100, height=100):
    """Create a minimal valid PNG file"""
    def png_chunk(chunk_type, data):
        chunk_len = struct.pack('>I', len(data))
        chunk_crc = struct.pack('>I', zlib.crc32(chunk_type + data) & 0xffffffff)
        return chunk_len + chunk_type + data + chunk_crc
    
    raw_data = b''
    for y in range(height):
        raw_data += b'\x00'  # filter byte
        for x in range(width):
            raw_data += b'\xff\x00\x00'  # RGB red
    
    compressed = zlib.compress(raw_data)
    
    signature = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr = png_chunk(b'IHDR', ihdr_data)
    idat = png_chunk(b'IDAT', compressed)
    iend = png_chunk(b'IEND', b'')
    
    return signature + ihdr + idat + iend

# Test 1: Check if we can create and save a test image
print("=" * 50)
print("TEST 1: Creating test image file")
print("=" * 50)

# Create a simple test image
test_image_path = os.path.join(os.path.dirname(__file__), 'uploads', 'test_image.png')
os.makedirs(os.path.dirname(test_image_path), exist_ok=True)

with open(test_image_path, 'wb') as f:
    f.write(create_minimal_png())
print(f"✓ Test image created: {test_image_path}")
print(f"✓ File exists: {os.path.exists(test_image_path)}")
print(f"✓ File size: {os.path.getsize(test_image_path)} bytes")

print()

# Test 2: Test the main.py media handling logic directly
print("=" * 50)
print("TEST 2: Testing main.py media file handling")
print("=" * 50)

from main import FacebookGroupSpam

# Create poster with media files
poster = FacebookGroupSpam(
    post_content="Test post with image",
    media_files=[test_image_path],
    headless=True,
    use_persistent=False
)

print(f"✓ FacebookGroupSpam created")
print(f"✓ Media files set: {poster.media_files}")
print(f"✓ Media file exists: {os.path.exists(poster.media_files[0]) if poster.media_files else 'No files'}")

print()

# Test 3: Test browser startup and basic functionality
print("=" * 50)
print("TEST 3: Testing browser startup (will close immediately)")
print("=" * 50)

try:
    print("Starting browser...")
    poster.start_browser()
    print("✓ Browser started successfully")
    
    # Check if page exists
    print(f"✓ Page object exists: {poster.page is not None}")
    print(f"✓ Context object exists: {poster.context is not None}")
    
    # Navigate to a simple page
    print("Navigating to example.com...")
    poster.page.goto("https://example.com", timeout=10000)
    print(f"✓ Navigation successful, title: {poster.page.title()}")
    
    # Test file input interaction
    print()
    print("=" * 50)
    print("TEST 4: Testing file input (would work if file input exists)")
    print("=" * 50)
    
    # Create a simple HTML page with file input for testing
    test_html = """
    <html>
    <body>
        <h1>File Upload Test</h1>
        <input type="file" id="testFile" accept="image/*,video/*" />
        <input type="file" id="testFile2" />
    </body>
    </html>
    """
    poster.page.set_content(test_html)
    print("✓ Created test HTML page with file inputs")
    
    # Try to find file inputs
    file_inputs = poster.page.locator('input[type="file"]').all()
    print(f"✓ Found {len(file_inputs)} file inputs")
    
    # Try to upload to file input
    if file_inputs:
        try:
            file_inputs[0].set_input_files(test_image_path)
            print(f"✓ Successfully set file input to: {test_image_path}")
            
            # Verify the file was set
            value = poster.page.evaluate("document.getElementById('testFile').files.length")
            print(f"✓ File input has {value} file(s) selected")
        except Exception as e:
            print(f"✗ Failed to set file input: {e}")
    
    poster.close_browser()
    print("✓ Browser closed")
    
except Exception as e:
    print(f"✗ Browser test failed: {e}")
    import traceback
    traceback.print_exc()
    try:
        poster.close_browser()
    except:
        pass

print()
print("=" * 50)
print("TEST COMPLETE")
print("=" * 50)

# Cleanup
try:
    if os.path.exists(test_image_path):
        os.remove(test_image_path)
        print(f"✓ Cleaned up test image")
except:
    pass
