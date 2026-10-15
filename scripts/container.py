"""Container bootstrap. All published ports are loopback-only in compose.yaml."""
import json
from pathlib import Path
import subprocess
import sys
from runtime import wait_for

root=Path(__file__).resolve().parent.parent
config=json.loads((root/'demo/config.json').read_text())
config.update(grafana_url='http://grafana:3015',grafana_public_url='http://127.0.0.1:3015',exporter_url='http://exporter:9115',changes_url='http://exporter:9115/changes',data_dir='/app/.runtime/investigator')
path=root/'.runtime/config.json';path.write_text(json.dumps(config))
wait_for('http://grafana:3015/api/health',[],timeout=120)
wait_for('http://prometheus:9095/-/ready',[],timeout=120)
wait_for('http://phoenix:6008',[],timeout=120)
subprocess.run([sys.executable,'scripts/bootstrap.py','--config',str(path),'--prometheus-url','http://prometheus:9095'],check=True,cwd=root)
import os
os.execv(sys.executable,[sys.executable,'-m','investigator.app','--config',str(path),'--host','0.0.0.0','--port','7868'])
