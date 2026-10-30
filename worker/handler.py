"""Consumidor SQS idempotente con fallos parciales. Sin datos personales en logs."""
import json, os, time, logging
import boto3
from botocore.exceptions import ClientError
log=logging.getLogger();log.setLevel(logging.INFO)
_table=None

def table():
    global _table
    if _table is None: _table=boto3.resource('dynamodb').Table(os.environ['EVENTS_TABLE'])
    return _table

def handle_record(record, target):
    data=json.loads(record['body'])
    required=['event_id','user_id','product_id','interaction_type','timestamp']
    if not all(isinstance(data.get(k),str) and data[k] for k in required):
        raise ValueError('Evento incompleto')
    if data['interaction_type'] not in ['view','cart','purchase']: raise ValueError('Tipo invalido')
    item={k:data[k] for k in required}
    item['expires_at']=int(time.time())+90*86400
    try:
        target.put_item(Item=item,ConditionExpression='attribute_not_exists(event_id)')
    except ClientError as e:
        if e.response['Error']['Code']!='ConditionalCheckFailedException': raise

def handler(event, context):
    failures=[]
    for record in event.get('Records',[]):
        try: handle_record(record, table())
        except Exception:
            log.error(json.dumps({'event':'record_failed','message_id':record['messageId']}))
            failures.append({'itemIdentifier':record['messageId']})
    return {'batchItemFailures':failures}
