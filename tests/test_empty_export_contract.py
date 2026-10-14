
import csv,io,tempfile
from pathlib import Path
from flowerp.store import ERPStore
from flowerp.identity import IdentityService,SYSTEM_PRINCIPAL
from flowerp.master_data import MasterDataService
from flowerp.import_export import ImportExportService
FIELDS={
'products':['sku','name','barcode','tracking','sales_price_cents','standard_cost_cents','tax_rate_basis_points','min_stock','max_stock','active'],
'customers':['code','name','contact_name','phone','email','shipping_address','payment_terms_days','credit_limit_cents','status'],
'inventory':['sku','name','site','location','lot_id','on_hand','reserved','available']}
def check(kind,nonempty=False):
    with tempfile.TemporaryDirectory(prefix='l15-csv-') as folder:
        store=ERPStore(Path(folder)/'test.db');IdentityService(store).ensure_local_defaults()
        if nonempty:
            master=MasterDataService(store)
            if kind=='products':master.create_product(SYSTEM_PRINCIPAL,'QA-A','带逗号,中文商品',100,50)
            elif kind=='customers':master.create_customer(SYSTEM_PRINCIPAL,'QA-C','中文客户,测试')
        before={table:store.rows('SELECT * FROM '+table+' ORDER BY 1') for table in ('product_master','customer_master','stock_balance')}
        raw=ImportExportService(store).export_csv(SYSTEM_PRINCIPAL,kind)
        rows=list(csv.reader(io.StringIO(raw.lstrip('\ufeff'))))
        assert rows and rows[0]==FIELDS[kind],f'{kind}: required stable headers {FIELDS[kind]}, actual={rows}'
        assert len(rows)==(2 if nonempty else 1),rows
        if nonempty:assert rows[1][1]==('带逗号,中文商品' if kind=='products' else '中文客户,测试'),rows
        assert {table:store.rows('SELECT * FROM '+table+' ORDER BY 1') for table in before}==before
        return f'{kind}: fixed headers, {len(rows)-1} data rows, database unchanged'

import unittest
class EmptyExportContract(unittest.TestCase):
    def test_empty_and_nonempty_original_fields(self):
        for kind,nonempty in (('products',False),('products',True),('customers',False),('customers',True),('inventory',False)):
            with self.subTest(kind=kind,nonempty=nonempty):check(kind,nonempty)
