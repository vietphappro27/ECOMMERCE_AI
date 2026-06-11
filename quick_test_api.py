#!/usr/bin/env python3
"""
Quick API Integration Test - Without Docker
Tests if services are already running
"""

import json
import requests
import time
from datetime import datetime
from typing import Dict, List

# Configuration
API_GATEWAY_URL = "http://127.0.0.1:8000"

# API Test Cases
TEST_CASES = [
    {"name": "Product Service Health", "method": "GET", "url": API_GATEWAY_URL + "/api/products/?limit=1"},
    {"name": "Get Categories", "method": "GET", "url": API_GATEWAY_URL + "/api/categories/"},
    {"name": "Get Products", "method": "GET", "url": API_GATEWAY_URL + "/api/products/?limit=5"},
]

def test_api(test_name: str, method: str, url: str, data: dict = None) -> Dict:
    """Test a single API endpoint"""
    result = {
        "name": test_name,
        "method": method,
        "url": url,
        "status": "FAILED",
        "status_code": None,
        "response_time": None,
        "error": None,
        "data": None,
    }
    
    try:
        start_time = time.time()
        headers = {"Content-Type": "application/json"}
        
        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=5)
        elif method == "POST":
            resp = requests.post(url, json=data, headers=headers, timeout=5)
        else:
            raise ValueError(f"Unknown method: {method}")
        
        result["response_time"] = round((time.time() - start_time) * 1000, 2)
        result["status_code"] = resp.status_code
        
        if resp.status_code < 400:
            result["status"] = "✅ PASSED"
        else:
            result["status"] = "❌ FAILED"
        
        try:
            result["data"] = resp.json()
        except:
            result["data"] = resp.text[:100]
        
    except requests.ConnectionError:
        result["error"] = "Connection refused - services not running"
        result["status"] = "🔌 CONNECTION_ERROR"
    except requests.Timeout:
        result["error"] = "Request timeout"
        result["status"] = "⏱️ TIMEOUT"
    except Exception as e:
        result["error"] = str(e)
        result["status"] = "❌ ERROR"
    
    return result


def main():
    print("\n" + "=" * 80)
    print("🧪 QUICK API INTEGRATION TEST")
    print("=" * 80)
    print(f"Testing: {API_GATEWAY_URL}\n")
    
    results = []
    for test in TEST_CASES:
        print(f"Testing: {test['name']}...", end=" ", flush=True)
        result = test_api(test['name'], test['method'], test['url'])
        results.append(result)
        print(result['status'])
        
        if result['status_code']:
            print(f"  └─ Status Code: {result['status_code']} | Time: {result['response_time']}ms")
        
        if result['error']:
            print(f"  └─ Error: {result['error']}")
        
        if result['data']:
            if isinstance(result['data'], dict):
                print(f"  └─ Response Keys: {list(result['data'].keys())[:5]}")
            else:
                print(f"  └─ Response: {str(result['data'])[:60]}...")
        
        time.sleep(1)
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for r in results if "PASSED" in r['status'])
    total = len(results)
    
    print(f"✅ Passed: {passed}/{total}")
    
    if passed == total:
        print("\n✅ All tests passed! Your API is working correctly.")
    else:
        print("\n❌ Some tests failed. Check the service status.")
    
    print(f"\n📍 API Gateway URL: {API_GATEWAY_URL}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
