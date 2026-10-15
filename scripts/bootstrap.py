import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from guardian.config import Config
from guardian.grafana import Grafana,GrafanaError
from dashboard import build


def bootstrap(config_path,prometheus_url):
    config=Config.load(config_path)
    client=Grafana(config)
    ds={"name":"Investigator Prometheus","uid":"guardian-prometheus","type":"prometheus","url":prometheus_url,"access":"proxy","isDefault":True,"jsonData":{"httpMethod":"POST","timeInterval":"2s"}}
    try:client.datasource("guardian-prometheus")
    except GrafanaError as exc:
        if exc.status!=404:raise
        client.request('/api/datasources',ds)
    root=Path(__file__).resolve().parent.parent
    for dashboard in [json.loads((root/'demo/dashboard.json').read_text()),build()]:
        try:
            live=client.get(dashboard['uid'])
            if dashboard['uid']=='incident-investigator':
                dashboard.update(id=live['dashboard'].get('id'),version=live['dashboard']['version'])
                client.save(dashboard,'','Refresh generated investigator metrics dashboard')
        except GrafanaError as exc:
            if exc.status!=404:raise
            client.save(dashboard,'','Install AI Incident Investigator demo')
    print('Two Grafana dashboards ready',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',default='demo/config.json');parser.add_argument('--prometheus-url',default='http://127.0.0.1:9095')
    args=parser.parse_args();bootstrap(args.config,args.prometheus_url)
