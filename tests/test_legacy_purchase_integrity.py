import json,sqlite3,tempfile
from pathlib import Path
from flowerp.service import ERPService
from flowerp.store import ERPStore
from flowerp.models import ApprovalRequired,InvalidTransition,OrderLine

def check(mode, states_path=None):
    with tempfile.TemporaryDirectory(prefix="l12-approval-") as folder:
        store=ERPStore(Path(folder)/'purchase.db')
        service=ERPService(store)
        service.add_product("A","商品 A",100)
        service.receive_stock("A",10,"opening")
        service.create_order("其他客户",[OrderLine("A",2,100)],"OTHER")
        service.reserve_order("OTHER")
        service.propose_purchase("A",3,"另一项需求","PR-OTHER")
        service.propose_purchase("A",7,"补货","PR-TARGET")
        tables=("purchase_requests","stock","inventory_events","sales_orders","sales_order_lines")
        def snapshot():
            return {t:store.rows(f"SELECT * FROM {t} ORDER BY 1") for t in tables}
        phases=[]
        def record(phase):
            phases.append({"phase":phase,"tables":snapshot()})
        try:
            before=snapshot()
            record("before_approval")
            if mode=="blank-reviewer":
                try: service.approve_purchase("PR-TARGET","  ")
                except ValueError: pass
                else: raise AssertionError("blank reviewer accepted")
                assert snapshot()==before
                return "blank-reviewer: rejected; five tables unchanged"
            if mode=="rejected":
                service.reject_purchase("PR-TARGET","TEACHING business reviewer")
            elif mode!="unapproved":
                approved=service.approve_purchase("PR-TARGET","TEACHING business reviewer")
                assert approved["approved_by"]=="TEACHING business reviewer" and approved["status"]=="approved"
                assert all(snapshot()[t]==before[t] for t in tables if t!="purchase_requests")
            before_receive=snapshot()
            record("before_receive")
            if mode in {"unapproved","rejected"}:
                try: service.receive_purchase("PR-TARGET","receipt:target")
                except ApprovalRequired: pass
                else: raise AssertionError("receipt without approval accepted")
                assert snapshot()==before_receive
                return f"{mode}: ApprovalRequired; five tables unchanged"
            if mode in {"status-write-failure","recovery-same-key"}:
                with store.connect() as conn:
                    conn.execute("CREATE TRIGGER fail_target_status BEFORE UPDATE OF status ON purchase_requests WHEN NEW.id='PR-TARGET' AND NEW.status='received' BEGIN SELECT RAISE(ABORT,'TEACHING receipt status failure'); END")
                try: service.receive_purchase("PR-TARGET","receipt:target")
                except sqlite3.IntegrityError: pass
                else: raise AssertionError("injected status failure did not occur")
                record("after_status_write_failure")
                current=service.product("A")
                if mode=="status-write-failure":
                    assert snapshot()==before_receive,(f"receipt partially committed: status={service.purchase('PR-TARGET')['status']}; on_hand={current['on_hand']}; expected unchanged 10")
                    return "status write failed atomically"
                assert snapshot()==before_receive, "failed receipt must roll back all five tables before retry"
                with store.connect() as conn:
                    conn.execute("DROP TRIGGER fail_target_status")
            key="opening" if mode=="key-collision" else "receipt:target"
            if mode=="key-collision":
                try: service.receive_purchase("PR-TARGET",key)
                except (ValueError,InvalidTransition): pass
                else: raise AssertionError("receipt key belonging to another business event was accepted")
                assert snapshot()==before_receive
                return "key-collision: rejected; five tables unchanged"
            result=service.receive_purchase("PR-TARGET",key)
            record("after_receive")
            if mode=="replay":
                after_first=snapshot()
                replay=service.receive_purchase("PR-TARGET",key)
                assert snapshot()==after_first and replay["stock"]["idempotent_replay"]
            if mode=="different-key":
                after_first=snapshot()
                try: service.receive_purchase("PR-TARGET","receipt:another")
                except InvalidTransition: pass
                else: raise AssertionError("second receipt with another key accepted")
                assert snapshot()==after_first
            item=service.product("A")
            assert result["purchase"]["status"]=="received"
            assert (item["on_hand"],item["reserved"],item["available"])==(17,2,15),f"receipt state mismatch: {item['on_hand']}/{item['reserved']}/{item['available']}"
            events=store.rows("SELECT * FROM inventory_events WHERE reference='PR-TARGET' AND event_type='receive'")
            assert len(events)==1 and events[0]["quantity"]==7
            final=snapshot()
            assert final["sales_orders"]==before["sales_orders"]
            assert final["sales_order_lines"]==before["sales_order_lines"]
            assert service.purchase("PR-OTHER")==next(p for p in before["purchase_requests"] if p["id"]=="PR-OTHER")
            return f"{mode}: received; 17/2/15; one +7 receipt; OTHER and PR-OTHER preserved; teaching reviewer input is not authentication"
        finally:
            record("final")
            if states_path:
                states_path=Path(states_path)
                states_path.parent.mkdir(parents=True,exist_ok=True)
                payload={"mode":mode,"boundary":"Real service with temporary database; teaching reviewer and injected fault; no authenticated approval.","phases":phases}
                with states_path.open("x",encoding="utf-8") as stream:
                    json.dump(payload,stream,ensure_ascii=False,indent=2)

import unittest
class LegacyPurchaseIntegrity(unittest.TestCase):
    def test_original_nine_business_paths(self):
        for mode in ('approved','unapproved','blank-reviewer','rejected','replay','different-key','status-write-failure','recovery-same-key','key-collision'):
            with self.subTest(mode=mode):check(mode)
