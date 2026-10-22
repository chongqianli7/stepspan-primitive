"""SDK-backed local storage and validator checks; web and LLM responses are mocked."""
import os
import sys
import subprocess
import json
import unittest
from pathlib import Path
from gltest.direct import VMContext, deploy_contract, create_address
import gltest.direct.sdk_loader as sdk

if os.environ.get('STEPSPAN_SDK_CACHE'):
    sdk.CACHE_DIR = Path(os.environ['STEPSPAN_SDK_CACHE'])
CONTRACT = Path(__file__).parents[1] / 'contracts/stepspan.py'
INPUT = {'venue':'Fictional museum','url':'https://example.org/access','nodes':[{'id':'a','label':'Entrance'},{'id':'b','label':'Gallery'}],'edges':[{'id':'E1','from':'a','to':'b'}],'start':'a','end':'b'}
QUOTE = 'The Fictional museum entrance has a level step-free route to the Gallery.'
SOURCE = QUOTE + ' Published venue access notes.' * 6

def finding(state='PASS'):
    return json.dumps({'edges':[{'id':'E1','state':state,'quote':QUOTE if state!='UNKNOWN' else ''}]})

class SDKTests(unittest.TestCase):
    def setUp(self):
        self.vm = VMContext()
        self.owner = create_address('stepspan-owner')
        self.owner_text = "0x"+self.owner.hex() if isinstance(self.owner,bytes) else str(self.owner)
        self.vm.sender = self.owner
        self.active = self.vm.activate()
        self.active.__enter__()
        self.addCleanup(self.active.__exit__,None,None,None)
        self.contract = deploy_contract(CONTRACT,self.vm,sdk_version='v0.3.0-rc7')
    def mocks(self,state='PASS',supported=True,source=SOURCE):
        self.vm.clear_mocks()
        self.vm.mock_web(r'example.org/access',{'status':200,'body':source})
        # Specific audit pattern must precede the classification pattern.
        self.vm.mock_llm('Independently check',json.dumps({'checks':[{'id':'E1','supported':supported}]}))
        self.vm.mock_llm('Interpret venue accessibility',finding(state))
    def seal(self): self.contract.seal('visit',json.dumps(INPUT))
    def test_schema_and_storage(self):
        self.assertEqual(self.contract.get_protocol(),'stepspan-1');self.seal()
        p=json.loads(self.contract.get_plan(self.owner_text,'visit'))
        self.assertEqual(p['input'],INPUT);self.assertEqual(self.contract.get_revision(self.owner_text,'visit'),0)
    def test_assessment_serializes_and_reads(self):
        self.seal();self.mocks();r=json.loads(self.contract.assess('visit',0))
        self.assertEqual(r['route']['status'],'SUPPORTED');self.assertEqual(self.contract.get_revision(self.owner_text,'visit'),1)
        self.assertEqual(json.loads(self.contract.get_review(self.owner_text,'visit',1)),r)
    def test_independent_validator_accepts(self):
        self.seal();self.mocks();self.contract.assess('visit',0)
        self.assertTrue(self.vm.run_validator())
    def test_independent_validator_disagrees(self):
        self.seal();self.mocks();self.contract.assess('visit',0);self.mocks('UNKNOWN')
        self.assertFalse(self.vm.run_validator())
    def test_quote_audit_rejects(self):
        self.seal();self.mocks();self.contract.assess('visit',0);self.mocks(supported=False)
        self.assertFalse(self.vm.run_validator())
    def test_changed_snapshot_rejects(self):
        self.seal();self.mocks();self.contract.assess('visit',0);self.mocks(source=SOURCE+' changed')
        self.assertFalse(self.vm.run_validator())
    def test_other_sender_cannot_assess(self):
        self.seal()
        with self.vm.prank(create_address('other-owner')):
            with self.vm.expect_revert('Seal plan first'):self.contract.assess('visit',0)
    def test_revision_guard(self):
        self.seal()
        with self.vm.expect_revert('Stale revision'):self.contract.assess('visit',1)
    def test_immutable_plan(self):
        self.seal()
        with self.vm.expect_revert('Plan already sealed'):self.seal()
    def test_historical_snapshot_preserved(self):
        self.seal();self.mocks();self.contract.assess('visit',0)
        first=self.contract.get_review(self.owner_text,'visit',1)
        self.mocks('UNKNOWN');self.contract.assess('visit',1)
        self.assertEqual(self.contract.get_revision(self.owner_text,'visit'),2)
        self.assertEqual(self.contract.get_review(self.owner_text,'visit',1),first)

if __name__=='__main__':
    if len(sys.argv)>1:
        unittest.main()
    else:
        # The SDK keeps one contract class per interpreter; isolate deployments.
        names=unittest.defaultTestLoader.getTestCaseNames(SDKTests)
        results=[subprocess.run([sys.executable,__file__,'SDKTests.'+name]).returncode for name in names]
        print(f'SDK checks: {len(names)-sum(bool(x) for x in results)}/{len(names)} passed')
        raise SystemExit(any(results))
