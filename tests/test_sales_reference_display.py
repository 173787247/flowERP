from test_production_erp import ProductionFixture


class SalesReferenceDisplayTests(ProductionFixture):
    def test_internal_placeholder_is_hidden_in_detail_and_list_without_changing_storage(self):
        order = self.sales.create_order(
            self.admin, self.customer["id"],
            [{"product_id": self.product["id"], "quantity": 1}],
        )
        stored = self.store.row("SELECT external_reference FROM sales_documents WHERE id=?", (order["id"],))
        self.assertEqual("__internal__:" + order["id"], stored["external_reference"])
        self.assertEqual("", order["external_reference"])
        self.assertEqual("", self.sales.order(self.admin, order["id"])["external_reference"])
        self.assertEqual("", self.sales.list_orders(self.admin)[0]["external_reference"])

    def test_real_and_placeholder_like_references_remain_visible(self):
        for reference in ("TM-001", "aainternalbb:customer-order"):
            with self.subTest(reference=reference):
                order = self.sales.create_order(
                    self.admin, self.customer["id"],
                    [{"product_id": self.product["id"], "quantity": 1}],
                    external_reference=reference,
                )
                self.assertEqual(reference, order["external_reference"])
                rows = {row["id"]: row for row in self.sales.list_orders(self.admin)}
                self.assertEqual(reference, rows[order["id"]]["external_reference"])
