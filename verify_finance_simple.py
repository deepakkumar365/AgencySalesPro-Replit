"""
Simple verification script for Finance Module
Checks the models.py and routes.py files for correct class names
"""

import re

def check_file_content(filepath, checks):
    """Check if file contains expected patterns"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        results = []
        for check_name, pattern, should_exist in checks:
            matches = re.findall(pattern, content)
            if should_exist:
                status = "✓" if matches else "✗"
                message = f"{status} {check_name}: {'Found' if matches else 'NOT FOUND'}"
                if matches:
                    message += f" ({len(matches)} occurrence(s))"
            else:
                status = "✓" if not matches else "✗"
                message = f"{status} {check_name}: {'Correctly absent' if not matches else 'STILL EXISTS'}"
                if matches:
                    message += f" ({len(matches)} occurrence(s))"
            
            results.append((status == "✓", message))
        
        return results
    except Exception as e:
        return [(False, f"Error reading {filepath}: {e}")]

print("=" * 70)
print("Finance Module - Simple Verification")
print("=" * 70)

# Check models.py
print("\n1. Checking models.py...")
models_checks = [
    ("FinancePayment class exists", r"class FinancePayment\(db\.Model\):", True),
    ("FinancePayment table name", r"__tablename__ = 'ASP_finance_payments'", True),
    ("Receipt class exists", r"class Receipt\(db\.Model\):", True),
    ("Receipt table name", r"__tablename__ = 'ASP_receipts'", True),
    ("PaymentPurchaseOrder table name", r"__tablename__ = 'ASP_finance_payment_purchase_orders'", True),
    ("No duplicate Payment class at line 760", r"# Finance Module Models\s+class Payment\(", False),
]

models_results = check_file_content(
    r"d:\Project\Workouts\GitHub\AgencySalesPro-Replit\models.py",
    models_checks
)

for success, message in models_results:
    print(f"   {message}")

# Check finance/routes.py
print("\n2. Checking finance/routes.py...")
routes_checks = [
    ("FinancePayment imported", r"\bFinancePayment\b", True),
    ("FinancePayment.query used", r"FinancePayment\.query", True),
    ("FinancePayment constructor used", r"payment = FinancePayment\(", True),
    ("Receipt imported", r"\bReceipt\b", True),
]

routes_results = check_file_content(
    r"d:\Project\Workouts\GitHub\AgencySalesPro-Replit\finance\routes.py",
    routes_checks
)

for success, message in routes_results:
    print(f"   {message}")

# Summary
print("\n" + "=" * 70)
all_success = all(s for s, _ in models_results + routes_results)
if all_success:
    print("✓ ALL CHECKS PASSED!")
    print("\nThe Finance module has been correctly updated.")
    print("\nNext steps:")
    print("1. Restart any running Python/Flask processes")
    print("2. Run database migrations:")
    print("   python -m flask db migrate -m 'Add Finance module tables'")
    print("   python -m flask db upgrade")
    print("3. Start the application:")
    print("   python main.py")
else:
    print("✗ SOME CHECKS FAILED!")
    print("\nPlease review the failed checks above.")
print("=" * 70)