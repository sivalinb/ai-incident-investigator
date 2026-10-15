"""Start and supervise the isolated native stack; Ctrl+C stops owned processes."""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from runtime import native_binaries,wait_for

ROOT=Path(__file__).resolve().parent.parent


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--grafana-home',type=Path)
    parser.add_argument('--prometheus-bin',type=Path)
    parser.add_argument('--runtime',type=Path,default=ROOT/'.runtime')
    args=parser.parse_args()
    for port in (3015,9095,9115,7868,6008,4319):
        with socket.socket() as s:
            if s.connect_ex(('127.0.0.1',port))==0:
                raise SystemExit(f'Port {port} is occupied. Stop the previous demo before starting another; no service was replaced.')
    runtime=args.runtime.resolve();runtime.mkdir(parents=True,exist_ok=True)
    home,prometheus=(args.grafana_home.resolve(),args.prometheus_bin.resolve()) if args.grafana_home and args.prometheus_bin else native_binaries(runtime)
    logs=runtime/'logs';logs.mkdir(exist_ok=True)
    for name in ['grafana/data','grafana/plugins','grafana/provisioning','prometheus','investigator','phoenix']:(runtime/name).mkdir(parents=True,exist_ok=True)
    grafana_config=runtime/'grafana.ini'
    grafana_config.write_text('\n'.join(['[server]','http_addr = 127.0.0.1','http_port = 3015','[paths]','data = '+str(runtime/'grafana/data'),'logs = '+str(logs),'plugins = '+str(runtime/'grafana/plugins'),'provisioning = '+str(runtime/'grafana/provisioning'),'[security]','admin_user = admin','admin_password = local-demo-only','[auth.anonymous]','enabled = true','org_role = Viewer','[analytics]','reporting_enabled = false','check_for_updates = false','[log]','mode = console','level = warn','[plugins]','preinstall_disabled = true','']))
    prom_config=runtime/'prometheus.yml'
    prom_config.write_text("global:\n  scrape_interval: 2s\n  evaluation_interval: 2s\nscrape_configs:\n  - job_name: checkout\n    static_configs:\n      - targets: ['127.0.0.1:9115']\n  - job_name: investigator\n    static_configs:\n      - targets: ['127.0.0.1:7868']\n")
    config=json.loads((ROOT/'demo/config.json').read_text());config['data_dir']=str(runtime/'investigator')
    config_path=runtime/'config.json';config_path.write_text(json.dumps(config,indent=2))
    env=dict(os.environ,GRADIO_ANALYTICS_ENABLED='False',PHOENIX_WORKING_DIR=str(runtime/'phoenix'),PHOENIX_PORT='6008',PHOENIX_HOST='127.0.0.1',PHOENIX_GRPC_PORT='4319',
             OTEL_EXPORTER_OTLP_TRACES_ENDPOINT='http://127.0.0.1:6008/v1/traces')
    processes=[];handles=[]
    def launch(name,cmd):
        handle=open(logs/(name+'.log'),'w');handles.append(handle)
        process=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=handle,stderr=subprocess.STDOUT);processes.append(process)
        return process
    def stop(signum=None,frame=None):raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,stop)
    try:
        launch('exporter',[sys.executable,'demo/exporter.py','--port','9115'])
        launch('prometheus',[str(prometheus),'--config.file='+str(prom_config),'--storage.tsdb.path='+str(runtime/'prometheus'),'--web.listen-address=127.0.0.1:9095'])
        launch('grafana',[str(home/'bin/grafana'),'server','--homepath='+str(home),'--config='+str(grafana_config)])
        launch('phoenix',[sys.executable,'-m','phoenix.server.main','serve'])
        wait_for('http://127.0.0.1:3015/api/health',processes)
        wait_for('http://127.0.0.1:9095/-/ready',processes)
        wait_for('http://127.0.0.1:6008',processes)
        subprocess.run([sys.executable,'scripts/bootstrap.py','--config',str(config_path)],cwd=ROOT,env=env,check=True)
        time.sleep(4)
        launch('gradio',[sys.executable,'-m','investigator.app','--config',str(config_path)])
        wait_for('http://127.0.0.1:7868/healthz',processes,timeout=90)
        print('READY · Gradio http://127.0.0.1:7868 · Grafana http://127.0.0.1:3015/d/incident-investigator · Phoenix http://127.0.0.1:6008',flush=True)
        print('Synthetic checkout; advisor mode '+env.get('OI_ADVISOR_MODE','fixture')+'. Ctrl+C stops this stack.',flush=True)
        (runtime/'owned-processes.json').write_text(json.dumps({'supervisor':os.getpid(),'children':[p.pid for p in processes]},indent=2))
        while all(p.poll() is None for p in processes):time.sleep(1)
        raise RuntimeError('A service exited; inspect .runtime/logs')
    except KeyboardInterrupt:print('Stopping owned demo services',flush=True)
    finally:
        for p in reversed(processes):
            if p.poll() is None:p.terminate()
        for p in processes:
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:p.kill()
        for h in handles:h.close()


if __name__=='__main__':main()
