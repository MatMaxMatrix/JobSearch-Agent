#!/usr/bin/env python
"""
Windows Compatibility Verification Script

This script verifies that the Windows async compatibility fixes are working
properly for Playwright and the job search system.
"""
import sys
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def verify_windows_compatibility():
    """Verify Windows async compatibility setup"""
    print("🔍 Verifying Windows async compatibility...")
    
    if sys.platform != "win32":
        print("✅ Not on Windows - no compatibility issues expected")
        return True
    
    # Check event loop policy
    try:
        current_policy = asyncio.get_event_loop_policy()
        if isinstance(current_policy, asyncio.WindowsProactorEventLoopPolicy):
            print("✅ Windows ProactorEventLoop policy is active")
        else:
            print(f"⚠️  Current policy: {type(current_policy).__name__}")
            print("🔧 Setting Windows ProactorEventLoop policy...")
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            print("✅ Windows ProactorEventLoop policy applied")
    except Exception as e:
        print(f"❌ Error checking event loop policy: {e}")
        return False
    
    # Test async subprocess capability
    try:
        async def test_subprocess():
            """Test if async subprocess works"""
            try:
                # Simple subprocess test
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, '-c', 'print("test")',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                await proc.wait()
                return proc.returncode == 0
            except Exception as e:
                logger.error(f"Subprocess test failed: {e}")
                return False
        
        # Run the test
        result = asyncio.run(test_subprocess())
        if result:
            print("✅ Async subprocess functionality working")
        else:
            print("❌ Async subprocess functionality failed")
            return False
            
    except Exception as e:
        print(f"❌ Error testing async subprocess: {e}")
        return False
    
    # Test Playwright import and basic initialization
    try:
        from playwright.async_api import async_playwright
        print("✅ Playwright import successful")
        
        async def test_playwright():
            """Test basic Playwright initialization"""
            try:
                playwright = await async_playwright().start()
                await playwright.stop()
                return True
            except Exception as e:
                logger.error(f"Playwright test failed: {e}")
                return False
        
        playwright_result = asyncio.run(test_playwright())
        if playwright_result:
            print("✅ Playwright basic initialization working")
        else:
            print("❌ Playwright initialization failed")
            return False
            
    except ImportError:
        print("⚠️  Playwright not installed - install with: pip install playwright")
        return False
    except Exception as e:
        print(f"❌ Playwright test error: {e}")
        return False
    
    print("🎉 All Windows compatibility checks passed!")
    return True

async def test_browser_manager():
    """Test the browser manager with Windows compatibility"""
    print("\n🔍 Testing BrowserManager with Windows compatibility...")
    
    try:
        from jobsearch_agent.scraper.search.linkedin_scraper.browser import BrowserManager
        
        # Test browser manager initialization
        browser_manager = BrowserManager(browser="chromium", headless=True)
        print("✅ BrowserManager initialization successful")
        
        # Test setup (this is where the error typically occurs)
        await browser_manager.setup_driver()
        print("✅ Browser setup successful")
        
        # Test navigation to a simple page
        await browser_manager.navigate_to("https://www.example.com")
        print("✅ Navigation test successful")
        
        # Cleanup
        await browser_manager.close()
        print("✅ Browser cleanup successful")
        
        return True
        
    except Exception as e:
        logger.error(f"BrowserManager test failed: {e}")
        return False

def main():
    """Main verification function"""
    print("🚀 Starting Windows Compatibility Verification\n")
    
    # Basic compatibility check
    basic_check = verify_windows_compatibility()
    
    if not basic_check:
        print("\n❌ Basic compatibility check failed")
        return False
    
    # Advanced browser manager test
    try:
        browser_check = asyncio.run(test_browser_manager())
        if browser_check:
            print("\n🎉 All tests passed! Windows compatibility is working correctly.")
            return True
        else:
            print("\n❌ Browser manager test failed")
            return False
    except Exception as e:
        print(f"\n❌ Browser manager test error: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
