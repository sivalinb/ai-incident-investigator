"""Exercise the public Gradio API against real demo services; produces proof, not screenshots."""
import argparse
import json
from pathlib import Path
import time
import httpx


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:7868');parser.add_argument('--wait',type=int,default=60);parser.add_argument('--output',default='reports/verification.local.json')
    args=parser.parse_args();url=args.url.rstrip('/')
    deadline=time.time()+args.wait
    while True:
        try:
            if httpx.get(url+'/healthz',timeout=2).status_code==200:break
        except httpx.HTTPError:pass
        if time.time()>deadline:raise RuntimeError('Demo failed to become ready')
        time.sleep(1)
    client=httpx.Client(base_url=url,headers={'X-Investigator-Demo':'synthetic-local-only'},timeout=240)
    assert httpx.post(url+'/api/lab/demo/scan',timeout=5).status_code==403,'Demo mutation requires its explicit local-only header'
    client.post('/api/lab/demo/reset').raise_for_status()
    baseline=httpx.get(url+'/api/lab/state').json()
    assert all(c['state'] in ('healthy','expected_empty') for c in baseline['checks']),baseline
    client.post('/api/lab/demo/migrate').raise_for_status()
    failed=httpx.get(url+'/api/lab/state').json()
    item=next(i for i in failed['incidents'] if i['status']=='awaiting_review')
    assert item['proposal']['label_before']=='app' and item['proposal']['label_after']=='service'
    assert item['screenshot_before']['available'],item['screenshot_before']
    assert 'environment=' in item['proposal']['after']
    client.post('/api/lab/incidents/'+item['id']+'/approve',json={'reviewer':'local-integration-reviewer','proposal_hash':item['proposal']['hash']}).raise_for_status()
    recovered=httpx.get(url+'/api/lab/state').json()
    resolved=next(i for i in recovered['incidents'] if i['id']==item['id'])
    assert resolved['status']=='resolved',resolved['status']
    assert resolved['screenshot_after']['available']
    spans=httpx.get(url+'/api/lab/spans').json()
    assert any(s['name']=='investigate' and s['trace_id']==item['trace_id'] for s in spans)
    assert any(s['name']=='approve' and any(l['trace_id']==item['trace_id'] for l in s['links']) for s in spans),'Review trace was not linked'
    report={'status':'passed','provenance':'real_grafana_prometheus_and_openinference_with_synthetic_workload','incident_id':item['id'],'trace_id':item['trace_id'],
            'advisor_mode':resolved['advisor'].get('mode'),'screenshots':{'before':resolved['screenshot_before']['available'],'after':resolved['screenshot_after']['available']},
            'checks':len(recovered['checks']),'scope_preserved':True,'review_trace_linked':True}
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
