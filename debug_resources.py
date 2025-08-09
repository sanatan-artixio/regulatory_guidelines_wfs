#!/usr/bin/env python3
"""
Resource monitoring script for debugging browser automation issues in cloud environments
"""

import asyncio
import psutil
import os
import sys
from pathlib import Path

def check_system_resources():
    """Check available system resources"""
    print("🔍 System Resource Analysis")
    print("=" * 50)
    
    # Memory
    memory = psutil.virtual_memory()
    print(f"💾 Memory:")
    print(f"  Total: {memory.total / (1024**3):.2f} GB")
    print(f"  Available: {memory.available / (1024**3):.2f} GB")
    print(f"  Used: {memory.used / (1024**3):.2f} GB ({memory.percent:.1f}%)")
    print(f"  Free: {memory.free / (1024**3):.2f} GB")
    
    # Disk
    disk = psutil.disk_usage('/')
    print(f"\n💿 Disk (/):")
    print(f"  Total: {disk.total / (1024**3):.2f} GB")
    print(f"  Used: {disk.used / (1024**3):.2f} GB ({disk.used/disk.total*100:.1f}%)")
    print(f"  Free: {disk.free / (1024**3):.2f} GB")
    
    # CPU
    cpu_count = psutil.cpu_count()
    cpu_percent = psutil.cpu_percent(interval=1)
    print(f"\n🖥️  CPU:")
    print(f"  Cores: {cpu_count}")
    print(f"  Usage: {cpu_percent:.1f}%")
    
    # Load average (Unix-like systems)
    if hasattr(os, 'getloadavg'):
        load_avg = os.getloadavg()
        print(f"  Load Average: {load_avg[0]:.2f}, {load_avg[1]:.2f}, {load_avg[2]:.2f}")
    
    # Check if we're in a container
    if Path('/.dockerenv').exists():
        print(f"\n🐳 Running in Docker container")
    
    # Check for memory limits (common in containers)
    cgroup_memory = Path('/sys/fs/cgroup/memory/memory.limit_in_bytes')
    if cgroup_memory.exists():
        try:
            with open(cgroup_memory) as f:
                limit = int(f.read().strip())
                if limit < memory.total:
                    print(f"⚠️  Container memory limit: {limit / (1024**3):.2f} GB")
        except:
            pass

def check_browser_requirements():
    """Check browser-related requirements"""
    print("\n🌐 Browser Requirements Check")
    print("=" * 50)
    
    # Check if Playwright is installed
    try:
        import playwright
        print(f"✅ Playwright installed: {playwright.__version__}")
    except ImportError:
        print("❌ Playwright not installed")
        return
    
    # Check for Chromium
    try:
        from playwright.async_api import async_playwright
        
        async def check_chromium():
            async with async_playwright() as p:
                try:
                    browser = await p.chromium.launch(headless=True)
                    print("✅ Chromium browser available")
                    await browser.close()
                    return True
                except Exception as e:
                    print(f"❌ Chromium launch failed: {e}")
                    return False
        
        chromium_works = asyncio.run(check_chromium())
        
    except Exception as e:
        print(f"❌ Playwright test failed: {e}")
    
    # Check system dependencies
    print("\n🔧 System Dependencies:")
    
    # Common libraries needed by Chromium
    required_libs = [
        'libnss3.so',
        'libxss1.so', 
        'libasound2.so',
        'libxrandr2.so',
        'libatk1.0.so',
        'libgtk-3.so',
        'libgdk-pixbuf2.0.so'
    ]
    
    for lib in required_libs:
        # Try to find the library
        found = False
        for path in ['/lib', '/usr/lib', '/lib/x86_64-linux-gnu', '/usr/lib/x86_64-linux-gnu']:
            lib_path = Path(path) / lib
            if lib_path.exists():
                print(f"✅ {lib} found")
                found = True
                break
        
        if not found:
            print(f"⚠️  {lib} not found (may cause browser issues)")

def recommend_fixes():
    """Provide recommendations based on findings"""
    print("\n💡 Recommendations")
    print("=" * 50)
    
    memory = psutil.virtual_memory()
    
    if memory.available < 1 * (1024**3):  # Less than 1GB available
        print("⚠️  LOW MEMORY WARNING:")
        print("   - Available memory is very low for browser automation")
        print("   - Consider increasing container memory limits")
        print("   - Use --single-process browser flag (already added)")
        print("   - Consider using --disable-dev-shm-usage (already added)")
    
    if memory.total < 2 * (1024**3):  # Less than 2GB total
        print("⚠️  MEMORY CONSTRAINT:")
        print("   - Total memory is limited for Chromium browser")
        print("   - Browser automation may be unreliable")
        print("   - Consider alternative approaches (API, simpler HTTP requests)")
    
    print("\n🔧 Browser Optimization Tips:")
    print("   - Use headless mode (reduces memory usage)")
    print("   - Disable unnecessary features (extensions, plugins, etc.)")
    print("   - Use single-process mode in constrained environments")
    print("   - Increase timeout values for slow networks")
    print("   - Consider using Firefox instead of Chromium (lighter)")

if __name__ == "__main__":
    print("🚀 FDA Crawler - Resource Diagnostic Tool")
    print("=" * 60)
    
    check_system_resources()
    check_browser_requirements()
    recommend_fixes()
    
    print("\n✅ Resource analysis complete!")
    print("💡 Run this in your cloud environment to diagnose browser issues")
