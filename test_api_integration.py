#!/usr/bin/env python3
"""
Automated API Integration Tester
- Start docker-compose services
- Test all API endpoints
- Generate report
- Rebuild frontend
"""

import json
import requests
import time
import subprocess
import os
import sys
from datetime import datetime
from typing import Dict, List, Tuple

# Configuration
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
API_GATEWAY_URL = "http://127.0.0.1:8000"
GATEWAY_UI_URL = "http://127.0.0.1:8010"

# API Test Cases
TEST_CASES = [
    # Health Checks
    {"name": "Product Service Health", "method": "GET", "url": API_GATEWAY_URL + "/api/products/?limit=1"},
    
    # Register & Login
    {"name": "Customer Register", "method": "POST", "url": API_GATEWAY_URL + "/api/register/", 
     "data": {"username": f"testuser_{int(time.time())}", "password": "test123", "full_name": "Test User", "role": "CUSTOMER"}},
    
    {"name": "Customer Login", "method": "POST", "url": API_GATEWAY_URL + "/api/login/", 
     "data": {"username": "testcustomer", "password": "test123", "role": "CUSTOMER"}},
    
    # Products
    {"name": "Get Products", "method": "GET", "url": API_GATEWAY_URL + "/api/products/?limit=10"},
    
    {"name": "Get Categories", "method": "GET", "url": API_GATEWAY_URL + "/api/categories/"},
    
    # Cart
    {"name": "Create Cart", "method": "POST", "url": API_GATEWAY_URL + "/api/customer/carts/",
     "data": {"customer_id": 1}},
    
    {"name": "Get Cart", "method": "GET", "url": API_GATEWAY_URL + "/api/customer/carts/?customer_id=1"},
    
    # Add to Cart
    {"name": "Add to Cart", "method": "POST", "url": API_GATEWAY_URL + "/api/customer/cart-items/",
     "data": {"customer_id": 1, "product_id": 1, "quantity": 1, "item_type": "product"}},
]


class APITester:
    def __init__(self):
        self.results: List[Dict] = []
        self.session = requests.Session()
        self.session_id = None
        
    def log(self, msg: str, level: str = "INFO"):
        """Log message with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {msg}")
    
    def wait_for_service(self, url: str, timeout: int = 60) -> bool:
        """Wait for service to be ready"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                resp = requests.get(url, timeout=5)
                if resp.status_code < 500:
                    self.log(f"✅ Service ready: {url}", "SUCCESS")
                    return True
            except requests.RequestException:
                pass
            time.sleep(2)
        
        self.log(f"❌ Service timeout: {url}", "ERROR")
        return False
    
    def start_services(self) -> bool:
        """Start docker-compose services"""
        self.log("🚀 Starting docker-compose services...")
        try:
            # Check if docker is running
            subprocess.run(["docker", "--version"], capture_output=True, check=True)
        except Exception as e:
            self.log(f"⚠️  Docker not available: {e}", "WARNING")
            self.log("📌 Please ensure Docker is running and try again", "INFO")
            return False
        
        try:
            os.chdir(PROJECT_ROOT)
            
            # Stop existing containers
            self.log("Stopping existing containers...")
            subprocess.run(["docker-compose", "down"], capture_output=True, timeout=30)
            
            # Start new containers
            self.log("Starting new containers...")
            proc = subprocess.Popen(
                ["docker-compose", "up", "-d"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = proc.communicate(timeout=120)
            
            if proc.returncode != 0:
                self.log(f"Docker compose start failed: {stderr.decode()}", "ERROR")
                return False
            
            self.log("Waiting for services to be healthy...", "INFO")
            
            # Wait for API Gateway to be ready
            for i in range(60):
                try:
                    resp = requests.get(f"{API_GATEWAY_URL}/", timeout=5)
                    if resp.status_code < 500:
                        self.log("✅ API Gateway is ready!", "SUCCESS")
                        time.sleep(5)  # Extra buffer
                        return True
                except requests.RequestException:
                    pass
                
                time.sleep(2)
                if i % 10 == 0:
                    self.log(f"Still waiting... ({i}s)", "INFO")
            
            self.log("❌ Services failed to start in time", "ERROR")
            return False
            
        except Exception as e:
            self.log(f"❌ Error starting services: {e}", "ERROR")
            return False
    
    def test_api(self, test_case: Dict) -> Dict:
        """Test a single API endpoint"""
        name = test_case["name"]
        method = test_case["method"]
        url = test_case["url"]
        data = test_case.get("data")
        
        result = {
            "name": name,
            "method": method,
            "url": url,
            "status": "FAILED",
            "status_code": None,
            "response_time": None,
            "error": None,
            "response_preview": None,
        }
        
        try:
            start_time = time.time()
            
            headers = {"Content-Type": "application/json"}
            if method == "GET":
                resp = self.session.get(url, headers=headers, timeout=10)
            elif method == "POST":
                resp = self.session.post(url, json=data, headers=headers, timeout=10)
            elif method == "PUT":
                resp = self.session.put(url, json=data, headers=headers, timeout=10)
            elif method == "DELETE":
                resp = self.session.delete(url, headers=headers, timeout=10)
            else:
                raise ValueError(f"Unknown method: {method}")
            
            result["response_time"] = round((time.time() - start_time) * 1000, 2)
            result["status_code"] = resp.status_code
            
            # Try to parse response
            try:
                resp_json = resp.json()
                result["response_preview"] = json.dumps(resp_json, indent=2)[:200]
            except:
                result["response_preview"] = resp.text[:200]
            
            # Determine status
            if resp.status_code < 400:
                result["status"] = "PASSED"
            elif resp.status_code < 500:
                result["status"] = "FAILED"
            else:
                result["status"] = "ERROR"
            
        except requests.Timeout:
            result["error"] = "Request timeout"
            result["status"] = "TIMEOUT"
        except requests.ConnectionError as e:
            result["error"] = str(e)
            result["status"] = "CONNECTION_ERROR"
        except Exception as e:
            result["error"] = str(e)
            result["status"] = "ERROR"
        
        return result
    
    def run_all_tests(self):
        """Run all API tests"""
        self.log("=" * 70, "INFO")
        self.log("🧪 Starting API Integration Tests", "INFO")
        self.log("=" * 70, "INFO")
        
        for i, test_case in enumerate(TEST_CASES, 1):
            self.log(f"\n[{i}/{len(TEST_CASES)}] Testing: {test_case['name']}", "INFO")
            result = self.test_api(test_case)
            self.results.append(result)
            
            status_icon = "✅" if result["status"] == "PASSED" else "❌"
            self.log(f"{status_icon} {result['status']} | Status Code: {result['status_code']} | Time: {result['response_time']}ms", "INFO")
            
            if result["error"]:
                self.log(f"   Error: {result['error']}", "WARNING")
    
    def generate_report(self) -> str:
        """Generate test report"""
        report = []
        report.append("\n" + "=" * 70)
        report.append("📊 API INTEGRATION TEST REPORT")
        report.append("=" * 70)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Summary
        passed = sum(1 for r in self.results if r["status"] == "PASSED")
        failed = sum(1 for r in self.results if r["status"] in ["FAILED", "ERROR"])
        timeout = sum(1 for r in self.results if r["status"] == "TIMEOUT")
        
        report.append(f"📈 Summary:")
        report.append(f"   Total Tests: {len(self.results)}")
        report.append(f"   ✅ Passed: {passed}")
        report.append(f"   ❌ Failed: {failed}")
        report.append(f"   ⏱️  Timeout: {timeout}")
        report.append(f"   Success Rate: {(passed/len(self.results)*100):.1f}%\n")
        
        # Detailed Results
        report.append("📝 Detailed Results:")
        report.append("-" * 70)
        
        for result in self.results:
            status_icon = {
                "PASSED": "✅",
                "FAILED": "❌",
                "ERROR": "❌",
                "TIMEOUT": "⏱️",
                "CONNECTION_ERROR": "🔌",
            }.get(result["status"], "❓")
            
            report.append(f"\n{status_icon} {result['name']}")
            report.append(f"   Method: {result['method']} | URL: {result['url']}")
            report.append(f"   Status: {result['status_code']} | Time: {result['response_time']}ms")
            
            if result["error"]:
                report.append(f"   Error: {result['error']}")
            
            if result["response_preview"]:
                report.append(f"   Response: {result['response_preview']}...")
        
        report.append("\n" + "=" * 70)
        
        return "\n".join(report)
    
    def save_report(self, filename: str = "api_test_report.txt"):
        """Save report to file"""
        report = self.generate_report()
        filepath = os.path.join(PROJECT_ROOT, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report)
        
        self.log(f"\n📄 Report saved: {filepath}", "SUCCESS")
        return filepath
    
    def rebuild_frontend(self) -> bool:
        """Rebuild frontend (api-gateway-ui)"""
        self.log("\n" + "=" * 70, "INFO")
        self.log("🔨 Rebuilding Frontend", "INFO")
        self.log("=" * 70, "INFO")
        
        try:
            os.chdir(PROJECT_ROOT)
            
            # Build docker image for ui
            self.log("Building API Gateway UI image...", "INFO")
            result = subprocess.run(
                ["docker-compose", "build", "api-gateway-ui"],
                capture_output=True,
                timeout=300,
            )
            
            if result.returncode != 0:
                self.log(f"❌ Build failed: {result.stderr.decode()}", "ERROR")
                return False
            
            self.log("✅ Frontend build successful!", "SUCCESS")
            
            # Restart the ui service
            self.log("Restarting API Gateway UI service...", "INFO")
            result = subprocess.run(
                ["docker-compose", "up", "-d", "api-gateway-ui"],
                capture_output=True,
                timeout=60,
            )
            
            if result.returncode != 0:
                self.log(f"❌ Failed to restart: {result.stderr.decode()}", "ERROR")
                return False
            
            # Wait for UI to be ready
            self.log("Waiting for UI to be ready...", "INFO")
            for i in range(30):
                try:
                    resp = requests.get(f"{GATEWAY_UI_URL}/", timeout=5)
                    if resp.status_code < 500:
                        self.log(f"✅ UI is ready at {GATEWAY_UI_URL}", "SUCCESS")
                        return True
                except requests.RequestException:
                    pass
                
                time.sleep(2)
            
            self.log("⚠️  UI started but may not be fully ready", "WARNING")
            return True
            
        except Exception as e:
            self.log(f"❌ Error rebuilding frontend: {e}", "ERROR")
            return False


def main():
    """Main entry point"""
    tester = APITester()
    
    # Start services
    if not tester.start_services():
        tester.log("\n❌ Failed to start services. Exiting.", "ERROR")
        return 1
    
    # Run tests
    tester.run_all_tests()
    
    # Generate and save report
    print(tester.generate_report())
    tester.save_report("api_test_report.txt")
    
    # Summary
    passed = sum(1 for r in tester.results if r["status"] == "PASSED")
    total = len(tester.results)
    
    if passed == total:
        tester.log("\n✅ All tests passed!", "SUCCESS")
    else:
        tester.log(f"\n⚠️  {total - passed} test(s) failed", "WARNING")
    
    # Rebuild frontend
    if tester.rebuild_frontend():
        tester.log("\n✅ Frontend rebuild completed successfully!", "SUCCESS")
        print(f"\n🎉 Application is ready!")
        print(f"   - API Gateway: {API_GATEWAY_URL}")
        print(f"   - UI Gateway: {GATEWAY_UI_URL}")
    else:
        tester.log("\n❌ Frontend rebuild failed", "ERROR")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
