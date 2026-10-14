"""Independent L11 purchase-request checks against the public service API."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from flowerp.models import Conflict, NotFound, PurchaseStatus, ValidationError
from flowerp.service import ERPService
from flowerp.store import ERPStore


class NativePurchaseRequestTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="l11-purchase-native-")
        self.addCleanup(temporary.cleanup)
        self.service = ERPService(ERPStore(Path(temporary.name) / "test.db"))
        self.service.add_product("L11-SKU", "L11 test product", 1200)
        self.service.receive_stock("L11-SKU", 7, "l11-initial-stock")
        self.initial_inventory = self.service.inventory()
        self.initial_events = self.service.inventory_events()

    def assert_inventory_unchanged(self):
        self.assertEqual(self.service.inventory(), self.initial_inventory)
        self.assertEqual(self.service.inventory_events(), self.initial_events)

    def test_normal_request_is_proposed_without_approval_or_receipt(self):
        request = self.service.propose_purchase(
            "l11-sku", 3, "  Restock for the next order  ", request_id="PR-L11-OK"
        )

        self.assertEqual(request["id"], "PR-L11-OK")
        self.assertEqual(request["sku"], "L11-SKU")
        self.assertEqual(request["quantity"], 3)
        self.assertEqual(request["reason"], "Restock for the next order")
        self.assertEqual(request["status"], PurchaseStatus.PROPOSED)
        self.assertIsNone(request["approved_by"])
        self.assertEqual(self.service.purchase("PR-L11-OK"), request)
        self.assertEqual(self.service.list_purchases(), [request])
        self.assert_inventory_unchanged()

    def test_non_positive_quantity_is_rejected_without_writes(self):
        for index, quantity in enumerate((0, -1)):
            with self.subTest(quantity=quantity):
                with self.assertRaises((ValueError, ValidationError)):
                    self.service.propose_purchase(
                        "L11-SKU", quantity, "Restock", request_id=f"PR-L11-NONPOS-{index}"
                    )
                self.assertEqual(self.service.list_purchases(), [])
                self.assert_inventory_unchanged()

    def test_non_integer_quantity_is_rejected_without_writes(self):
        for index, quantity in enumerate((True, False, 1.5, 1.0, "2", None)):
            with self.subTest(quantity=quantity, value_type=type(quantity).__name__):
                with self.assertRaises((ValueError, ValidationError)):
                    self.service.propose_purchase(
                        "L11-SKU", quantity, "Restock", request_id=f"PR-L11-TYPE-{index}"
                    )
                self.assertEqual(self.service.list_purchases(), [])
                self.assert_inventory_unchanged()

    def test_blank_reason_is_rejected_without_writes(self):
        for index, reason in enumerate(("", "   ", "\t\r\n")):
            with self.subTest(reason=repr(reason)):
                with self.assertRaises((ValueError, ValidationError)):
                    self.service.propose_purchase(
                        "L11-SKU", 2, reason, request_id=f"PR-L11-BLANK-{index}"
                    )
                self.assertEqual(self.service.list_purchases(), [])
                self.assert_inventory_unchanged()

    def test_unknown_sku_is_rejected_without_writes(self):
        with self.assertRaises(NotFound):
            self.service.propose_purchase(
                "L11-UNKNOWN", 2, "Restock", request_id="PR-L11-UNKNOWN"
            )

        self.assertEqual(self.service.list_purchases(), [])
        self.assert_inventory_unchanged()

    def test_duplicate_request_id_preserves_original_request(self):
        original = self.service.propose_purchase(
            "L11-SKU", 2, "First request", request_id="PR-L11-DUPLICATE"
        )

        with self.assertRaises((sqlite3.IntegrityError, Conflict, ValueError)):
            self.service.propose_purchase(
                "L11-SKU", 9, "Replacement attempt", request_id="PR-L11-DUPLICATE"
            )

        self.assertEqual(self.service.purchase("PR-L11-DUPLICATE"), original)
        self.assertEqual(self.service.list_purchases(), [original])
        self.assert_inventory_unchanged()


if __name__ == "__main__":
    unittest.main()
