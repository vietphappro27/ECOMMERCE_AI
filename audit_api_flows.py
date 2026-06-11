#!/usr/bin/env python3
"""
Comprehensive API Flow Audit
- Analyze all API endpoints
- Detect data flow issues
- Validate field mappings
- Generate detailed audit report
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple

PROJECT_ROOT = Path(r"C:\Users\admin\Desktop\SAAD\kiemtra01_04.07_Nguyễn Tiến Thực")


class APIAudit:
    def __init__(self):
        self.findings = []
        self.endpoints = {}
        self.issues = {
            "critical": [],
            "warning": [],
            "info": []
        }
        
    def add_issue(self, level: str, title: str, description: str, file: str, line: int = 0):
        """Add an issue to report"""
        self.issues[level].append({
            "title": title,
            "description": description,
            "file": file,
            "line": line,
        })
    
    def analyze_gateway_views(self):
        """Analyze API Gateway views for data flow issues"""
        views_file = PROJECT_ROOT / "api-gateway" / "app" / "views.py"
        
        if not views_file.exists():
            self.add_issue("critical", "File Not Found", f"Gateway views file not found", str(views_file))
            return
        
        with open(views_file, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
        
        # Issue 1: CustomerCartItemProxyView - Missing item_type
        if "class CustomerCartItemProxyView" in content:
            for i, line in enumerate(lines):
                if "def post(self, request):" in line and i > 800 and i < 900:
                    # Check if item_type is extracted
                    section = '\n'.join(lines[i:i+50])
                    
                    if 'body.get(\'product_id\')' in section and 'body.get(\'item_type\')' not in section:
                        self.add_issue(
                            "critical",
                            "Missing item_type Extraction",
                            "Gateway receives item_type from frontend but DOES NOT extract it from request body. "
                            "Frontend sends item_type but gateway ignores it.",
                            "api-gateway/app/views.py",
                            i + 857
                        )
                    
                    # Check if item_type is sent to cart service
                    section = '\n'.join(lines[i:i+60])
                    if '_request_json' in section and 'payload={' in section:
                        payload_match = re.search(r'payload=\{([^}]+)\}', section, re.DOTALL)
                        if payload_match:
                            payload_str = payload_match.group(1)
                            if 'product_id' in payload_str and 'item_type' not in payload_str:
                                self.add_issue(
                                    "critical",
                                    "item_type Not Forwarded to Cart Service",
                                    "Gateway should send item_type to cart-service, but payload only includes: "
                                    "cart, product_id, quantity. item_type is missing.",
                                    "api-gateway/app/views.py",
                                    i + 877
                                )
        
        # Issue 2: Typo in PRODUCT_CATEGORY_SCHEMAS
        if "dimesions" in content:
            for i, line in enumerate(lines):
                if "dimesions" in line:
                    self.add_issue(
                        "warning",
                        "Typo in Category Schema",
                        "Schema key 'dimesions' should be 'dimensions'. This will cause field mapping failures.",
                        "api-gateway/app/views.py",
                        i + 1
                    )
        
        # Issue 3: _build_cart_response performance issue
        if "_build_cart_response" in content:
            for i, line in enumerate(lines):
                if "def _build_cart_response" in line:
                    section = '\n'.join(lines[i:i+40])
                    if '_product_index_by_id()' in section:
                        self.add_issue(
                            "warning",
                            "Performance Issue: Loading All Products",
                            "Every time cart is built, it loads ALL products from product service. "
                            "Should only load products that are in the cart.",
                            "api-gateway/app/views.py",
                            i + 1
                        )
    
    def analyze_cart_service(self):
        """Analyze cart service for data storage issues"""
        views_file = PROJECT_ROOT / "cart-service" / "app" / "views.py"
        models_file = PROJECT_ROOT / "cart-service" / "app" / "models.py"
        
        if not views_file.exists():
            return
        
        with open(views_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if not models_file.exists():
            self.add_issue(
                "critical",
                "CartItem Model Missing item_type Field",
                "Database model CartItem does not have item_type field. "
                "Item type data cannot be persisted.",
                "cart-service/app/models.py"
            )
        else:
            with open(models_file, 'r', encoding='utf-8') as f:
                model_content = f.read()
                if 'class CartItem' in model_content and 'item_type' not in model_content:
                    self.add_issue(
                        "critical",
                        "CartItem Model Missing item_type Field",
                        "Database model CartItem does not have item_type field. "
                        "Item type data cannot be persisted.",
                        "cart-service/app/models.py"
                    )
    
    def analyze_frontend(self):
        """Analyze frontend for correct API calls"""
        dashboard_file = PROJECT_ROOT / "api-gateway" / "app" / "templates" / "app" / "customer_dashboard.html"
        cart_file = PROJECT_ROOT / "api-gateway" / "app" / "templates" / "app" / "customer_cart.html"
        
        if dashboard_file.exists():
            with open(dashboard_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check addToCart function
            if 'addToCart' in content:
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if 'async function addToCart' in line:
                        section = '\n'.join(lines[i:i+20])
                        
                        if 'item_type' in section and 'product_id' in section:
                            self.add_issue(
                                "info",
                                "Frontend Correctly Sends item_type",
                                "✅ Frontend correctly sends item_type in addToCart request",
                                "api-gateway/app/templates/app/customer_dashboard.html",
                                i + 1
                            )
    
    def generate_html_report(self) -> str:
        """Generate detailed HTML report"""
        html = []
        
        html.append("<!DOCTYPE html>")
        html.append("<html>")
        html.append("<head>")
        html.append("<meta charset='utf-8'>")
        html.append("<meta name='viewport' content='width=device-width, initial-scale=1.0'>")
        html.append("<title>API Integration Audit Report</title>")
        html.append("""<style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f5f5; line-height: 1.6; }
            .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
            header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px; margin-bottom: 30px; }
            h1 { font-size: 32px; margin-bottom: 10px; }
            .timestamp { opacity: 0.9; font-size: 14px; }
            
            .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
            .summary-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .summary-card.critical { border-left: 4px solid #e74c3c; }
            .summary-card.warning { border-left: 4px solid #f39c12; }
            .summary-card.info { border-left: 4px solid #3498db; }
            .summary-card h3 { font-size: 24px; color: #333; margin-bottom: 5px; }
            .summary-card p { color: #666; font-size: 14px; }
            
            .section { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .section h2 { color: #333; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #667eea; }
            
            .issue { padding: 15px; margin-bottom: 15px; border-radius: 4px; border-left: 4px solid; }
            .issue.critical { background: #fadbd8; border-left-color: #e74c3c; }
            .issue.warning { background: #fef5e7; border-left-color: #f39c12; }
            .issue.info { background: #d6eaf8; border-left-color: #3498db; }
            
            .issue-title { font-weight: 600; font-size: 15px; margin-bottom: 8px; }
            .issue-desc { font-size: 14px; margin-bottom: 8px; }
            .issue-location { font-size: 12px; color: #666; font-family: monospace; }
            
            .status-icon { display: inline-block; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; margin-right: 8px; }
            .critical-icon { background: #e74c3c; }
            .warning-icon { background: #f39c12; }
            .info-icon { background: #3498db; }
            
            .recommendation { background: #ecf0f1; padding: 15px; border-radius: 4px; margin-top: 15px; font-size: 14px; }
            .recommendation strong { display: block; margin-bottom: 8px; color: #333; }
            
            footer { text-align: center; padding: 20px; color: #666; font-size: 12px; margin-top: 40px; }
        </style>""")
        html.append("</head>")
        html.append("<body>")
        
        # Header
        html.append("<header>")
        html.append("<h1>🔍 API Integration Audit Report</h1>")
        html.append(f"<p class='timestamp'>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>")
        html.append("</header>")
        
        # Container
        html.append("<div class='container'>")
        
        # Summary
        critical_count = len(self.issues['critical'])
        warning_count = len(self.issues['warning'])
        info_count = len(self.issues['info'])
        
        html.append("<div class='summary'>")
        html.append(f"<div class='summary-card critical'><h3>{critical_count}</h3><p>🔴 Critical Issues</p></div>")
        html.append(f"<div class='summary-card warning'><h3>{warning_count}</h3><p>🟠 Warnings</p></div>")
        html.append(f"<div class='summary-card info'><h3>{info_count}</h3><p>ℹ️ Information</p></div>")
        html.append("</div>")
        
        # Issues by level
        for level in ['critical', 'warning', 'info']:
            if self.issues[level]:
                level_name = {"critical": "🔴 Critical Issues", "warning": "🟠 Warnings", "info": "ℹ️ Information"}[level]
                html.append(f"<div class='section'>")
                html.append(f"<h2>{level_name}</h2>")
                
                for issue in self.issues[level]:
                    icon_class = f"{level}-icon"
                    html.append(f"<div class='issue {level}'>")
                    html.append(f"<div class='issue-title'><span class='status-icon {icon_class}'></span>{issue['title']}</div>")
                    html.append(f"<div class='issue-desc'>{issue['description']}</div>")
                    html.append(f"<div class='issue-location'>📄 {issue['file']}{':' + str(issue['line']) if issue['line'] else ''}</div>")
                    html.append("</div>")
                
                html.append("</div>")
        
        # API Flow Diagram
        html.append("""
        <div class='section'>
            <h2>📊 Data Flow Analysis</h2>
            <div style='background: #f9f9f9; padding: 20px; border-radius: 4px; font-family: monospace; font-size: 12px;'>
                <div style='color: #e74c3c; font-weight: bold; margin-bottom: 10px;'>❌ CURRENT (BROKEN):</div>
                <div style='margin-left: 20px;'>
                    Frontend → {customer_id, <span style='background: yellow;'>item_type</span>, product_id, quantity}
                    <br>↓
                    <br>Gateway → {customer_id, <span style='background: #ffcccc; color: red;'>✗ SKIPPED item_type</span>, product_id, quantity}
                    <br>↓
                    <br>Cart Service DB → {cart_id, product_id, quantity}
                    <br>↓
                    <br>Frontend receives → {product_id, quantity, <span style='background: #ffcccc; color: red;'>item_type from product service (unreliable)</span>}
                </div>
                
                <div style='color: #27ae60; font-weight: bold; margin-top: 20px; margin-bottom: 10px;'>✅ EXPECTED (FIXED):</div>
                <div style='margin-left: 20px;'>
                    Frontend → {customer_id, <span style='background: lightgreen;'>item_type</span>, product_id, quantity}
                    <br>↓
                    <br>Gateway → {customer_id, <span style='background: lightgreen;'>item_type</span>, product_id, quantity}
                    <br>↓
                    <br>Cart Service DB → {cart_id, product_id, quantity, <span style='background: lightgreen;'>item_type</span>}
                    <br>↓
                    <br>Frontend receives → {product_id, quantity, <span style='background: lightgreen;'>item_type (from DB - reliable)</span>}
                </div>
            </div>
        </div>
        """)
        
        # Recommendations
        html.append("""
        <div class='section'>
            <h2>💡 Fix Checklist</h2>
            <div class='recommendation'>
                <strong>1️⃣ Fix Gateway Views (api-gateway/app/views.py, Line 857-882)</strong>
                <ul style='margin-left: 20px;'>
                    <li>Extract item_type from request body in CustomerCartItemProxyView.post()</li>
                    <li>Add item_type to payload when calling cart-service</li>
                </ul>
            </div>
            <div class='recommendation'>
                <strong>2️⃣ Update Cart Service Model (cart-service/app/models.py)</strong>
                <ul style='margin-left: 20px;'>
                    <li>Add item_type field to CartItem model</li>
                    <li>Create database migration</li>
                </ul>
            </div>
            <div class='recommendation'>
                <strong>3️⃣ Update Cart Service Views (cart-service/app/views.py)</strong>
                <ul style='margin-left: 20px;'>
                    <li>Extract item_type from request payload</li>
                    <li>Save item_type when creating CartItem</li>
                </ul>
            </div>
            <div class='recommendation'>
                <strong>4️⃣ Fix Typo (api-gateway/app/views.py, Line 287)</strong>
                <ul style='margin-left: 20px;'>
                    <li>Change "dimesions" → "dimensions" in PRODUCT_CATEGORY_SCHEMAS</li>
                </ul>
            </div>
        </div>
        """)
        
        html.append("</div>")
        
        # Footer
        html.append(f"""<footer>
            API Integration Audit Report | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            <br>Total Issues: {critical_count + warning_count + info_count}
        </footer>""")
        
        html.append("</body>")
        html.append("</html>")
        
        return "\n".join(html)
    
    def run_audit(self):
        """Run complete audit"""
        print("🔍 Starting API Integration Audit...\n")
        
        print("  📝 Analyzing Gateway Views...", end="", flush=True)
        self.analyze_gateway_views()
        print(" ✓")
        
        print("  📝 Analyzing Cart Service...", end="", flush=True)
        self.analyze_cart_service()
        print(" ✓")
        
        print("  📝 Analyzing Frontend...", end="", flush=True)
        self.analyze_frontend()
        print(" ✓")
        
        print("\n✅ Audit completed!\n")
        
        # Generate report
        report = self.generate_html_report()
        
        # Save to file
        output_file = PROJECT_ROOT / "API_AUDIT_REPORT.html"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"📄 Report saved: {output_file}\n")
        
        # Print summary
        print("=" * 70)
        print("📊 AUDIT SUMMARY")
        print("=" * 70)
        print(f"🔴 Critical Issues: {len(self.issues['critical'])}")
        print(f"🟠 Warnings: {len(self.issues['warning'])}")
        print(f"ℹ️  Information: {len(self.issues['info'])}")
        print("=" * 70)


if __name__ == "__main__":
    audit = APIAudit()
    audit.run_audit()
