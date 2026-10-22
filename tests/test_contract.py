"""Mock-host protocol tests; these do not execute GenVM or live consensus."""
import unittest, types, sys, json, importlib.util, copy
from pathlib import Path
class TreeMap(dict):
    @classmethod
    def __class_getitem__(cls,x): return cls
class Return:
    def __init__(self,x): self.calldata=x
class Host:
    def render(self,url,mode):
        self.fetches+=1
        return self.changed if self.changed and self.fetches>1 else SOURCE
    def prompt(self,prompt,response_format): return self.answers.pop(0)
    def run(self,leader,validator):
        r=leader()
        if not validator(Return(r)): raise ValueError('Consensus rejected')
        return r
host=Host()
gl=types.SimpleNamespace(Contract=object,public=types.SimpleNamespace(write=lambda f:f,view=lambda f:f),message=types.SimpleNamespace(sender_address='0x'+'1'*40),nondet=types.SimpleNamespace(web=types.SimpleNamespace(render=host.render),exec_prompt=host.prompt),vm=types.SimpleNamespace(UserError=ValueError,Return=Return,run_nondet_unsafe=host.run))
m=types.ModuleType('genlayer');m.gl=gl;m.TreeMap=TreeMap;m.u256=int;sys.modules['genlayer']=m
spec=importlib.util.spec_from_file_location('stepspan',Path(__file__).parents[1]/'contracts/stepspan.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
INPUT={'venue':'Fictional museum','url':'https://example.org/access','nodes':[{'id':'a','label':'Entrance'},{'id':'b','label':'Lift'},{'id':'c','label':'Gallery'}],'edges':[{'id':'E1','from':'a','to':'b'},{'id':'E2','from':'b','to':'c'},{'id':'E3','from':'a','to':'c'}],'start':'a','end':'c'}
QUOTE='The entrance connects to the lift through a level corridor.'
SOURCE=QUOTE+' The lift has a level exit to the gallery. The direct route has stairs. '+'Additional published venue information. '*5

def findings(states=('PASS','UNKNOWN','BLOCKED')):
    return {'edges':[{'id':'E'+str(i+1),'state':s,'quote':QUOTE if s!='UNKNOWN' else ''} for i,s in enumerate(states)]}
def audit(supported=True):
    return {'checks':[{'id':'E'+str(i+1),'supported':supported} for i in range(3)]}

class Tests(unittest.TestCase):
    def setUp(self):
        self.x=c.StepSpan();self.x.plans=TreeMap();self.x.reviews=TreeMap();self.x.revisions=TreeMap();host.answers=[];host.fetches=0;host.changed=None;gl.message.sender_address='0x'+'1'*40
    def seal(self): return json.loads(self.x.seal('visit',json.dumps(INPUT)))
    def assess(self,states=('PASS','UNKNOWN','BLOCKED')):
        host.answers=[findings(states),findings(states),audit()]
        return json.loads(self.x.assess('visit',0))
    def test_seal_hash(self): self.assertEqual(self.seal()['input_sha256'],c.digest(c.canonical(INPUT)))
    def test_seal_immutable(self):
        self.seal()
        with self.assertRaises(ValueError): self.seal()
    def test_owner_namespace(self):
        self.seal();gl.message.sender_address='0x'+'2'*40
        with self.assertRaises(ValueError):self.x.assess('visit',0)
        self.seal();self.assertEqual(len(self.x.plans),2)
    def test_gap_not_accessible(self):
        self.seal();r=self.assess();self.assertEqual(r['route']['status'],'UNRESOLVED');self.assertEqual(r['route']['path'],[]);self.assertEqual(r['route']['candidate_path'],['E1','E2']);self.assertEqual(host.fetches,2)
    def test_complete_path(self):
        self.seal();r=self.assess(('PASS','PASS','BLOCKED'));self.assertEqual(r['route']['path'],['E1','E2'])
    def test_blocked(self):self.assertEqual(c.route_result(INPUT,findings(('PASS','BLOCKED','BLOCKED')))['status'],'BLOCKED')
    def test_unknown_alternative_prevents_blocked(self):self.assertEqual(c.route_result(INPUT,findings(('BLOCKED','BLOCKED','UNKNOWN')))['status'],'UNRESOLVED')
    def test_direct_route_shortest(self):self.assertEqual(c.route_result(INPUT,findings(('PASS','PASS','PASS')))['path'],['E3'])
    def test_direction_not_inferred(self):
        d=copy.deepcopy(INPUT);d['start']='c';d['end']='a';self.assertEqual(c.route_result(d,findings(('PASS','PASS','PASS')))['status'],'UNRESOLVED')
    def test_disagreement_no_state_change(self):
        self.seal();host.answers=[findings(),findings(('PASS','PASS','BLOCKED'))]
        with self.assertRaisesRegex(ValueError,'Consensus rejected'):self.x.assess('visit',0)
        self.assertEqual(self.x.get_revision(gl.message.sender_address,'visit'),0);self.assertFalse(self.x.reviews)
    def test_source_changed_no_state_change(self):
        self.seal();host.changed=SOURCE+' changed';host.answers=[findings()]
        with self.assertRaises(ValueError):self.x.assess('visit',0)
        self.assertFalse(self.x.reviews)
    def test_stale_revision_no_fetch(self):
        self.seal()
        with self.assertRaises(ValueError):self.x.assess('visit',1)
        self.assertEqual(host.fetches,0)
    def test_append_preserves_history(self):
        self.seal();r=self.assess();old=self.x.get_review(gl.message.sender_address,'visit',1);host.answers=[findings(('PASS','PASS','BLOCKED'))]*2+[audit()];self.x.assess('visit',1);self.assertEqual(self.x.get_review(gl.message.sender_address,'visit',1),old);self.assertEqual(self.x.get_revision(gl.message.sender_address,'visit'),2)
    def test_fabricated_quote_rejected(self):
        f=findings();f['edges'][0]['quote']='Invented accessible route quote'
        with self.assertRaises(ValueError):c.parse_findings(f,INPUT,SOURCE)
    def test_positive_requires_quote(self):
        f=findings();f['edges'][0]['quote']=''
        with self.assertRaises(ValueError):c.parse_findings(f,INPUT,SOURCE)
    def test_missing_edge_rejected(self):
        f=findings();f['edges'].pop()
        with self.assertRaises(ValueError):c.parse_findings(f,INPUT,SOURCE)
    def test_misbound_edge_rejected(self):
        f=findings();f['edges'][0]['id']='E2'
        with self.assertRaises(ValueError):c.parse_findings(f,INPUT,SOURCE)
    def test_unknown_state_rejected(self):
        f=findings();f['edges'][0]['state']='MAYBE'
        with self.assertRaises(ValueError):c.parse_findings(f,INPUT,SOURCE)
    def test_input_failures(self):
        variants=[]
        for field,value in [('url','http://example.org'),('url','https://127.0.0.1/x'),('url','https://user:pass@example.org'),('nodes',[]),('start','missing'),('end','a'),('edges',[])]:
            d=copy.deepcopy(INPUT);d[field]=value;variants.append(d)
        d=copy.deepcopy(INPUT);d['nodes'][1]['id']='a';variants.append(d)
        d=copy.deepcopy(INPUT);d['edges'][1]['from']='missing';variants.append(d)
        d=copy.deepcopy(INPUT);d['edges'][1]['id']='E7';variants.append(d)
        for d in variants:
            with self.subTest(d=d),self.assertRaises(ValueError):c.parse_input(json.dumps(d))
    def test_quote_audit_rejection_no_state_change(self):
        self.seal();host.answers=[findings(),findings(),audit(False)]
        with self.assertRaises(ValueError):self.x.assess('visit',0)
        self.assertFalse(self.x.reviews)
    def test_truthy_string_not_audit_success(self):
        self.seal();host.answers=[findings(),findings(),audit('true')]
        with self.assertRaises(ValueError):self.x.assess('visit',0)
        self.assertFalse(self.x.reviews)
    def test_valid_json_text_findings(self):self.assertEqual(c.parse_findings(json.dumps(findings()),INPUT,SOURCE),findings())
if __name__=='__main__':unittest.main()
