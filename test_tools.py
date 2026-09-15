"""
Standalone tests for tools.py — no Claude/API involvement.
Run directly: python3 test_tools.py
"""

import json
from tools import get_order_status, get_stock_level

PASS = "PASS"
FAIL = "FAIL"

results = []


def check(label, condition):
    results.append((label, PASS if condition else FAIL))


print("=" * 70)
print("get_order_status tests")
print("=" * 70)

# 1. Known order, CR-HOLD status
r = get_order_status("SO10002")
print(json.dumps(r, indent=2))
check("SO10002 found", r["found"] is True)
check("SO10002 status is CR-HOLD", r["status"] == "CR-HOLD")
check("SO10002 status_meaning populated", r["status_meaning"] == "On credit hold")
check("SO10002 customer name correct", r["customer_name"] == "Sydney Hospitality Group")
check("SO10002 has 1 line", len(r["lines"]) == 1)
check("SO10002 line item correct", r["lines"][0]["item_id"] == "FG1001")

# 2. Order with multiple lines
r = get_order_status("SO10001")
print(json.dumps(r, indent=2))
check("SO10001 found", r["found"] is True)
check("SO10001 has 2 lines", len(r["lines"]) == 2)

# 3. Invalid order ID
r = get_order_status("SO99999")
print(json.dumps(r, indent=2))
check("SO99999 not found", r["found"] is False)
check("SO99999 has message", "message" in r)

print()
print("=" * 70)
print("get_stock_level tests")
print("=" * 70)

# 4. Multi-warehouse item
r = get_stock_level("FG1001")
print(json.dumps(r, indent=2))
check("FG1001 found", r["found"] is True)
check("FG1001 spans 2 warehouses", len(r["by_warehouse"]) == 2)
check("FG1001 total_available = 4000", r["total_available"] == 4000)

# 5. Single-warehouse item
r = get_stock_level("FG2001")
print(json.dumps(r, indent=2))
check("FG2001 found", r["found"] is True)
check("FG2001 spans 1 warehouse", len(r["by_warehouse"]) == 1)

# 6. Item with no inventory records at all
r = get_stock_level("PK1001")
print(json.dumps(r, indent=2))
check("PK1001 found (item exists)", r["found"] is True)
check("PK1001 total_available = 0", r["total_available"] == 0)
check("PK1001 has no-inventory message", "message" in r)

# 7. Item with ONLY quarantined stock
r = get_stock_level("FG1003")
print(json.dumps(r, indent=2))
check("FG1003 found", r["found"] is True)
check("FG1003 total_available = 0 (quarantined excluded)", r["total_available"] == 0)
check("FG1003 flags quarantined_stock_exists", r.get("quarantined_stock_exists") is True)

# 8. Invalid item ID
r = get_stock_level("FG9999-DOES-NOT-EXIST")
print(json.dumps(r, indent=2))
check("Invalid item not found", r["found"] is False)

print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)
passed = sum(1 for _, s in results if s == PASS)
for label, status in results:
    print(f"[{status}] {label}")
print(f"\n{passed}/{len(results)} checks passed")
