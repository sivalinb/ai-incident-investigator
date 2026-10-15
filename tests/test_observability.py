import json
import os
from pathlib import Path
from unittest.mock import patch

from openinference.instrumentation import OITracer,TraceConfig
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from investigator.telemetry import JsonlExporter,read_spans,metrics
from investigator.benchmark import classify,run_benchmark
from guardian.config import Config
from guardian.model import advise


def test_real_openinference_spans_have_parentage_and_masked_payloads(tmp_path):
    path=tmp_path/'spans.jsonl'
    provider=TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(JsonlExporter(path)))
    tracer=OITracer(provider.get_tracer('qa'),config=TraceConfig(hide_inputs=True,hide_outputs=True))
    with tracer.start_as_current_span('investigation',attributes={'openinference.span.kind':'AGENT'}) as parent:
        with tracer.start_as_current_span('local_model',attributes={'openinference.span.kind':'LLM','input.value':'private-test-payload'}) as child:
            child.set_attribute('output.value','private-test-result')
            child.set_attribute('llm.token_count.prompt',21)
    rows=read_spans(path)
    assert len(rows)==2
    assert rows[1]['parent_id']==rows[0]['span_id']
    assert rows[1]['trace_id']==rows[0]['trace_id']
    assert 'private-test' not in path.read_text()
    assert rows[1]['attributes']['llm.token_count.prompt']==21
    assert rows[1]['attributes']['input.value']=='__REDACTED__'
    provider.shutdown()


def test_unsafe_filter_broadening_is_not_a_repair():
    evidence={'target_up':True,'same_metric_new_label_has_data':True,'service_filter_preserved':True,'environment_filter_preserved':False}
    assert classify(evidence)=='insufficient_evidence'


def test_intentionally_empty_panel_is_not_an_incident():
    assert classify({'allow_empty':True,'original_has_data':False,'target_up':True})=='expected_empty'


def test_fixture_reports_never_claim_model_tokens_or_dollars(tmp_path):
    report=run_benchmark(tmp_path)
    assert report['provenance']=='authored_fixture'
    assert all(r['tokens'] is None and r['cost_usd'] is None for r in report['rows'])
    assert any(not r['correct'] for r in report['rows'] if r['strategy']=='naive_nonempty')
    assert (tmp_path/'benchmark.json').is_file()


def test_authored_advisor_is_explicitly_labeled(tmp_path):
    config=Config(grafana_url='http://localhost:3015',data_dir=tmp_path)
    with patch.dict(os.environ,{'OI_ADVISOR_MODE':'fixture'}):
        result=advise(config,{'items':[{'id':'e1','title':'Query','data':{}}],'rule_diagnosis':{'cause':'Insufficient evidence','confidence':'uncertain'}})
    assert result['mode']=='fixture'
    assert result['usage'] is None
    assert result['estimated_cost_usd'] is None


def test_ollama_usage_comes_from_provider_not_text_length():
    from investigator.ollama import chat
    class Reply:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,*args):return json.dumps({'done':True,'done_reason':'stop','message':{'content':'{"ok":true}'},'prompt_eval_count':37,'eval_count':9}).encode()
    with patch.dict(os.environ,{'OLLAMA_URL':'http://127.0.0.1:11434','OLLAMA_MODEL':'fixture-transport-only'}),patch('investigator.ollama.urlopen',return_value=Reply()):
        result=chat([{'role':'user','content':'hello'}],{'type':'object'})
    assert result['usage']=={'input_tokens':37,'output_tokens':9}
    assert result['estimated_cost_usd'] is None


def test_ollama_does_not_send_evidence_to_remote_endpoint():
    import pytest
    from investigator.ollama import chat
    with patch.dict(os.environ,{'OLLAMA_URL':'https://remote.invalid','OLLAMA_MODEL':'x'}),patch('investigator.ollama.urlopen') as request:
        with pytest.raises(ValueError):chat([],{'type':'object'})
        request.assert_not_called()


def test_missing_live_configuration_never_substitutes_a_fixture(tmp_path):
    config=Config(grafana_url='http://localhost:3015',data_dir=tmp_path)
    with patch.dict(os.environ,{'OI_ADVISOR_MODE':'live'}):
        result=advise(config,{'items':[]})
    assert result['mode']=='live' and result.get('error')
    assert 'advice' not in result


def test_metrics_do_not_use_incident_or_trace_ids_as_labels():
    text=metrics().decode()
    assert 'incident_id=' not in text and 'trace_id=' not in text
