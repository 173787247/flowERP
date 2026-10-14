
import json,tempfile,subprocess
from pathlib import Path
from unittest.mock import patch
from datetime import date as ActualDate
from flowerp.server import App
from flowerp import api as api_module
import shutil
NODE=shutil.which('node') or 'D:/Program Files/nodejs/node.exe'
class FixedDate:
    @classmethod
    def today(cls):return ActualDate(2026,10,14)
def backend_date():
    with tempfile.TemporaryDirectory(prefix='l16-day-') as folder:
        app=App(folder)
        with patch.object(api_module,'date',FixedDate,create=True):
            result=app.api.dispatch('GET','/api/v1/setup/status',{}, {},'127.0.0.1')
        assert result.status==200,result.status
        assert result.body.get('business_date')=='2026-10-14',f"business date missing/wrong: {result.body}"
        return 'Actual setup API returns backend business day; independent of UTC browser clock'
def browser_date():
    root=Path.cwd();helper=root/'web/business_date.js'
    assert helper.is_file(),'New business-day helper is absent; old UI UTC default was actually 2026-10-13'
    node=r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const RealDate=Date;
class UTCClock extends RealDate {constructor(...args){super(...(args.length?args:['2026-10-13T17:30:00Z']));}static now(){return new RealDate('2026-10-13T17:30:00Z').valueOf();}}
const context={Date:UTCClock};vm.createContext(context);vm.runInContext(fs.readFileSync('web/business_date.js','utf8'),context);
const api=context.FlowERPBusinessDate;assert(api&&typeof api.fromSetup==='function','public fromSetup contract missing');
assert.strictEqual(api.fromSetup({business_date:'2026-10-14'}),'2026-10-14');
assert.strictEqual(api.fromSetup({business_date:'2028-02-29'}),'2028-02-29');
for(const value of [undefined,null,'',0,true,'2026-02-29','2026-13-01','14/10/2026']){
 assert.strictEqual(api.fromSetup({business_date:value}),'','invalid/missing day must not fall back to current UTC');
}
console.log('UTC clock 2026-10-13; backend day 2026-10-14 preserved; invalid days remain empty');
"""
    result=subprocess.run([NODE,'-e',node],cwd=root,capture_output=True,text=True,encoding='utf8',timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
    html=(root/'web/index.html').read_text('utf8')
    assert 'business_date.js' in html and html.index('business_date.js')<html.rindex('app.js'),'helper must load before app'
    return result.stdout

import unittest
class BusinessDateContract(unittest.TestCase):
    def test_actual_backend_business_day(self):backend_date()
    def test_frontend_date_helper_calendar_and_missing_inputs(self):
        if not Path(NODE).is_file() and not __import__('shutil').which(NODE):self.skipTest('Node runtime unavailable; browser QA must be performed separately')
        browser_date()
