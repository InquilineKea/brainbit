#!/usr/bin/env python3
"""
Extract Slack cookie from Chrome for slackdump
"""
import sqlite3
import os
import shutil
from pathlib import Path

def get_chrome_cookies_path():
    """Get Chrome cookies database path for macOS"""
    home = Path.home()
    chrome_path = home / "Library/Application Support/Google/Chrome/Default/Cookies"
    if chrome_path.exists():
        return chrome_path
    return None

def extract_slack_cookie(workspace_name):
    """Extract the 'd' cookie for a Slack workspace"""
    cookies_path = get_chrome_cookies_path()
    
    if not cookies_path:
        print("❌ Chrome cookies database not found")
        return None
    
    # Chrome locks the database, so we need to copy it first
    temp_cookies = "/tmp/chrome_cookies_copy.db"
    try:
        shutil.copy2(cookies_path, temp_cookies)
    except Exception as e:
        print(f"❌ Error copying cookies database: {e}")
        print("💡 Make sure Chrome is closed and try again")
        return None
    
    try:
        conn = sqlite3.connect(temp_cookies)
        cursor = conn.cursor()
        
        # Query for specific Slack cookies we need
        cursor.execute(
            "SELECT name, value, host_key FROM cookies WHERE host_key LIKE '%slack.com%' AND name IN ('d', 'd-s')"
        )
        
        results = cursor.fetchall()
        conn.close()
        
        cookies = {}
        if results:
            for name, value, host in results:
                print(f"✅ Found cookie '{name}' for {host}")
                if value:
                    print(f"   (encrypted or empty)")
                cookies[name] = value
            return cookies
        else:
            print(f"❌ No 'd' cookie found for {workspace_name}.slack.com")
            print("💡 Make sure you're logged into Slack in Chrome")
            return None
            
    except Exception as e:
        print(f"❌ Error reading cookies: {e}")
        return None
    finally:
        # Clean up temp file
        if os.path.exists(temp_cookies):
            os.remove(temp_cookies)

if __name__ == "__main__":
    workspace = "psychedelics-world"
    print(f"🔍 Searching for Slack cookie for {workspace}...")
    print("⚠️  Close Chrome first for best results\n")
    
    cookie = extract_slack_cookie(workspace)
    
    if cookie:
        print(f"\n📋 Copy this cookie value:")
        print(f"{cookie}")
