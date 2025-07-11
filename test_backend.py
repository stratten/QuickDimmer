#!/usr/bin/env python3
"""
QuickDimmer Backend Test Script
Tests core functionality of the Python backend components
"""
import sys
import asyncio
import time
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

def test_imports():
    """Test that all required modules can be imported"""
    print("🔍 Testing imports...")
    
    try:
        from display_manager import DisplayManager
        print("✅ DisplayManager imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import DisplayManager: {e}")
        return False
    
    try:
        from focus_detector import FocusDetector
        print("✅ FocusDetector imported successfully") 
    except ImportError as e:
        print(f"❌ Failed to import FocusDetector: {e}")
        return False
        
    try:
        from api_server import APIServer
        print("✅ APIServer imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import APIServer: {e}")
        return False
    
    return True

def test_display_manager():
    """Test DisplayManager functionality"""
    print("\n🖥️  Testing DisplayManager...")
    
    try:
        from display_manager import DisplayManager
        
        dm = DisplayManager()
        print("✅ DisplayManager created")
        
        # Test display detection
        dm.cache_display_info()
        print(f"✅ Found {len(dm.display_bounds)} display(s)")
        
        # Print display information
        for display_id, bounds in dm.display_bounds.items():
            print(f"   Display {display_id}: {bounds[2]}x{bounds[3]} at ({bounds[0]}, {bounds[1]})")
        
        # Test status
        status = dm.get_status()
        print(f"✅ Status: {status}")
        
        return True
        
    except Exception as e:
        print(f"❌ DisplayManager test failed: {e}")
        return False

def test_focus_detector():
    """Test FocusDetector functionality"""
    print("\n🎯 Testing FocusDetector...")
    
    try:
        from display_manager import DisplayManager
        from focus_detector import FocusDetector
        
        dm = DisplayManager()
        dm.cache_display_info()
        
        fd = FocusDetector(dm)
        print("✅ FocusDetector created")
        
        # Test focus detection
        focused_display = fd.get_focused_display()
        print(f"✅ Focused display: {focused_display}")
        
        # Test focus info
        focus_info = fd.get_focus_info()
        print(f"✅ Focus info: {focus_info}")
        
        return True
        
    except Exception as e:
        print(f"❌ FocusDetector test failed: {e}")
        return False

async def test_api_server():
    """Test APIServer functionality"""
    print("\n🌐 Testing APIServer...")
    
    try:
        from display_manager import DisplayManager
        from api_server import APIServer
        
        dm = DisplayManager()
        dm.cache_display_info()
        
        api = APIServer(dm)
        print("✅ APIServer created")
        
        # Test server startup
        await api.start('localhost', 8081)  # Use different port for testing
        print("✅ APIServer started on port 8081")
        
        # Brief pause to let server initialize
        await asyncio.sleep(1)
        
        # Test HTTP endpoint
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get('http://localhost:8081/status') as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ HTTP API working: {data}")
                else:
                    print(f"❌ HTTP API returned status {response.status}")
                    return False
        
        # Cleanup
        await api.stop()
        print("✅ APIServer stopped")
        
        return True
        
    except Exception as e:
        print(f"❌ APIServer test failed: {e}")
        return False

def test_permissions():
    """Test macOS permissions and requirements"""
    print("\n🔐 Testing macOS permissions...")
    
    try:
        import subprocess
        
        # Test AppleScript access
        result = subprocess.run([
            'osascript', '-e', 
            'tell application "System Events" to get name of first application process whose frontmost is true'
        ], capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            app_name = result.stdout.strip()
            print(f"✅ AppleScript access working - focused app: {app_name}")
        else:
            print(f"❌ AppleScript access failed: {result.stderr}")
            print("   💡 You may need to grant accessibility permissions")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Permission test failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("🚀 QuickDimmer Backend Test Suite")
    print("=" * 40)
    
    tests = [
        ("Import Test", test_imports),
        ("DisplayManager Test", test_display_manager), 
        ("FocusDetector Test", test_focus_detector),
        ("APIServer Test", test_api_server),
        ("Permissions Test", test_permissions),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 40)
    print("📊 Test Results Summary:")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Backend is ready to run.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test suite crashed: {e}")
        sys.exit(1) 