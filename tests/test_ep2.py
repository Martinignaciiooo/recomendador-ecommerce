import os,sys,uuid,json,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
os.environ['RECO_API_TOKEN']='test-'+'x'*40
os.environ['EVENTS_DB']=tempfile.mktemp(suffix='.db')
from fastapi.testclient import TestClient
from botocore.exceptions import ClientError
import api
from worker.handler import handle_record
import worker.handler as worker
import pytest
TOKEN='test-'+'x'*40
@pytest.fixture
def client(monkeypatch):
 monkeypatch.setattr(api,'API_TOKEN',TOKEN)
 monkeypatch.setenv('EVENTS_BACKEND','sqs')
 with TestClient(api.app) as c:yield c
HEAD={'Authorization':'Bearer '+TOKEN}
def test_auth_required(client):assert client.get('/recomendaciones?user_id=1').status_code==401
def test_metrics_protected(client):assert client.get('/metricas').status_code==401
def test_model_ready_real(client):assert client.get('/health/ready').json()['modelo']=='v20260921-052859'
def test_unknown_user_fallback(client):
 x=client.get('/recomendaciones?user_id=999999999999',headers=HEAD).json()
 assert x['source']=='fallback' and len(x['recommendations'])==10
def test_uuid_required(client):
 assert client.post('/eventos',json={'user_id':1,'product_id':1,'event_type':'view'},headers=HEAD).status_code==422
def test_publish_real_contract(client,monkeypatch):
 sent=[];monkeypatch.setattr(api,'send_event',lambda x:sent.append(x))
 key=str(uuid.uuid4());h={**HEAD,'Idempotency-Key':key}
 assert client.post('/eventos',json={'user_id':1,'product_id':2,'event_type':'cart'},headers=h).status_code==202
 assert sent[0]['event_id']==key and sent[0]['user_id']=='1'
def test_queue_error_not_accepted(client,monkeypatch):
 def fail(_):raise RuntimeError('down')
 monkeypatch.setattr(api,'send_event',fail)
 assert client.post('/eventos',json={'user_id':1,'product_id':2,'event_type':'cart'},headers={**HEAD,'Idempotency-Key':str(uuid.uuid4())}).status_code==503
def test_health_fails_when_model_missing(client,monkeypatch):
 monkeypatch.setattr(api.state,'rec',None)
 assert client.get('/health/ready').status_code==503
def test_empty_token_fails_closed(monkeypatch):
 monkeypatch.setattr(api,'API_TOKEN','');monkeypatch.delenv('RECO_ALLOW_ANONYMOUS',raising=False)
 with pytest.raises(RuntimeError):api.load_state()
class Table:
 def __init__(self):self.items={}
 def put_item(self,Item,ConditionExpression):
  if Item['event_id'] in self.items:raise ClientError({'Error':{'Code':'ConditionalCheckFailedException'}},'PutItem')
  self.items[Item['event_id']]=Item
def event():return {'event_id':str(uuid.uuid4()),'user_id':'1','product_id':'2','interaction_type':'view','timestamp':'2026-10-29T00:00:00Z'}
def test_deduplicate():
 t=Table();r={'body':json.dumps(event())};handle_record(r,t);handle_record(r,t);assert len(t.items)==1
def test_partial_failure(monkeypatch):
 t=Table();monkeypatch.setattr(worker,'table',lambda:t)
 assert worker.handler({'Records':[{'messageId':'ok','body':json.dumps(event())},{'messageId':'bad','body':'invalid'}]},None)=={'batchItemFailures':[{'itemIdentifier':'bad'}]}
