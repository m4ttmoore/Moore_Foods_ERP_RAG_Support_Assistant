"""
Phase 2a live-data tool functions for the Moore Foods ERP RAG Assistant.

Each function opens its own short-lived connection, runs a single
parameterised read-only query, and returns a plain dict — no Claude
or LangChain dependency here, so these can be tested and used on
their own.
"""

import sqlite3
import os

# PHASE 3 FIX: absolute path anchored to this file's own location, same
# reasoning as the equivalent fix in ask.py's Chroma path. A relative or
# manually-typed path (e.g. "Database/Moore_Foods_ERP.db") depends on the
# working directory at runtime, which differs between a local terminal
# and a cloud deployment, causing sqlite3.connect to either fail or open
# a nonexistent path silently depending on the OS.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "Database", "Moore_Foods_ERP.db")

STATUS_MEANINGS = {
    "SO-OPEN": "Order created, not yet allocated",
    "ALLOCATED": "Stock reserved against the order",
    "PICKING": "Being picked in the warehouse",
    "CR-HOLD": "On credit hold",
    "INV-HOLD": "On inventory hold (stock issue)",
    "PRICE-HOLD": "On price/approval hold",
    "SHIPPED": "Shipped to customer",
    "INVOICED": "Invoiced — order complete",
}


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_order_status(order_id: str) -> dict:
    """Look up status, customer, and line items for a sales order."""
    try:
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT so.OrderID, so.Status, so.OrderDate, cm.CustomerName,
                   so.WarehouseID, sol.LineNo, sol.ItemID, im.Description,
                   sol.Quantity, sol.UnitPrice
            FROM Sales_Orders so
            JOIN Customer_Master cm ON so.CustomerID = cm.CustomerID
            JOIN Sales_Order_Lines sol ON so.OrderID = sol.OrderID
            JOIN Item_Master im ON sol.ItemID = im.ItemID
            WHERE so.OrderID = ?
            ORDER BY sol.LineNo
            """,
            (order_id,),
        )
        rows = cur.fetchall()
        conn.close()

        if not rows:
            return {
                "found": False,
                "order_id": order_id,
                "message": "No order found with this ID.",
            }

        first = rows[0]
        status = first["Status"]
        return {
            "found": True,
            "order_id": first["OrderID"],
            "status": status,
            "status_meaning": STATUS_MEANINGS.get(status, "Unknown status"),
            "order_date": first["OrderDate"],
            "customer_name": first["CustomerName"],
            "warehouse_id": first["WarehouseID"],
            "lines": [
                {
                    "line_no": r["LineNo"],
                    "item_id": r["ItemID"],
                    "description": r["Description"],
                    "quantity": r["Quantity"],
                    "unit_price": r["UnitPrice"],
                }
                for r in rows
            ],
        }
    except sqlite3.Error:
        return {
            "found": False,
            "error": True,
            "message": "Unable to retrieve order data.",
        }


def get_stock_level(item_id: str) -> dict:
    """Look up available stock for an item, broken down by warehouse."""
    try:
        conn = _connect()
        cur = conn.cursor()

        # Confirm the item exists and get its description
        cur.execute(
            "SELECT ItemID, Description FROM Item_Master WHERE ItemID = ?",
            (item_id,),
        )
        item = cur.fetchone()
        if item is None:
            conn.close()
            return {
                "found": False,
                "item_id": item_id,
                "message": "No item found with this ID.",
            }

        # Available stock only
        cur.execute(
            """
            SELECT WarehouseID, BinID, OnHandQty, AllocatedQty,
                   (OnHandQty - AllocatedQty) AS AvailableQty,
                   LotNumber, ExpiryDate
            FROM Inventory
            WHERE ItemID = ? AND Status = 'AVAILABLE'
            """,
            (item_id,),
        )
        available_rows = cur.fetchall()

        # Check separately whether any quarantined stock exists, for the note
        cur.execute(
            "SELECT COUNT(*) AS c FROM Inventory WHERE ItemID = ? AND Status = 'QUARANTINED'",
            (item_id,),
        )
        quarantined_count = cur.fetchone()["c"]
        conn.close()

        by_warehouse = [
            {
                "warehouse_id": r["WarehouseID"],
                "bin_id": r["BinID"],
                "on_hand_qty": r["OnHandQty"],
                "allocated_qty": r["AllocatedQty"],
                "available_qty": r["AvailableQty"],
                "lot_number": r["LotNumber"],
                "expiry_date": r["ExpiryDate"],
            }
            for r in available_rows
        ]
        total_available = sum(r["available_qty"] for r in by_warehouse)

        result = {
            "found": True,
            "item_id": item["ItemID"],
            "description": item["Description"],
            "total_available": total_available,
            "by_warehouse": by_warehouse,
        }

        if not by_warehouse:
            result["message"] = "No available inventory records found for this item."
        if quarantined_count > 0:
            result["quarantined_stock_exists"] = True

        return result
    except sqlite3.Error:
        return {
            "found": False,
            "error": True,
            "message": "Unable to retrieve stock data.",
        }
