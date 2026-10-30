"""Restaura SOLO la tabla de la practica a otra tabla; nunca redirige la API."""
import datetime as dt
import json
import sys
import time
from pathlib import Path

import boto3

root = Path(__file__).resolve().parents[1]
out = root / 'evidencias'
session = boto3.Session(region_name='us-east-1')
cfn = session.client('cloudformation')
ddb = session.client('dynamodb')
stack = cfn.describe_stacks(StackName='shopfast-ep2-lab')['Stacks'][0]
outputs = {x['OutputKey']: x['OutputValue'] for x in stack['Outputs']}
source = outputs['EventsTable']
proof = json.loads((out / 'eventos-idempotencia.json').read_text())
event = proof['persisted_event']
timestamp = dt.datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
target = 'shopfast-ep2-lab-pitr-' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d%H%M%S')
started = time.monotonic()
result = {'source': source, 'target': target, 'event_id': event['event_id'],
          'source_unchanged': True, 'traffic_redirected': False}

def save():
    (out / 'pitr.json').write_text(json.dumps(result, indent=2, default=str), encoding='utf-8')

try:
    for _ in range(90):
        description = ddb.describe_continuous_backups(TableName=source)['ContinuousBackupsDescription']['PointInTimeRecoveryDescription']
        latest = description.get('LatestRestorableDateTime')
        result['pitr_status'] = description['PointInTimeRecoveryStatus']
        if latest and latest >= timestamp:
            result['latest_restorable_utc'] = latest.isoformat()
            result['observed_recovery_point_lag_s'] = (dt.datetime.now(dt.timezone.utc) - latest).total_seconds()
            break
        time.sleep(5)
    else:
        raise RuntimeError('PITR no alcanzo el evento dentro de 450 s; no se afirma recuperacion')
    restore_started = time.monotonic()
    ddb.restore_table_to_point_in_time(SourceTableName=source, TargetTableName=target, UseLatestRestorableTime=True)
    ddb.get_waiter('table_exists').wait(TableName=target, WaiterConfig={'Delay': 10, 'MaxAttempts': 120})
    recovered = session.resource('dynamodb').Table(target).get_item(Key={'event_id': event['event_id']}, ConsistentRead=True).get('Item')
    assert recovered and all(recovered[k] == event[k] for k in ['event_id', 'user_id', 'product_id', 'interaction_type', 'timestamp'])
    result.update({'status': 'passed', 'restored_event_verified': True,
                   'restore_seconds': round(time.monotonic() - restore_started, 2),
                   'including_wait_seconds': round(time.monotonic() - started, 2),
                   'retained_test_copy': True})
    save()
    print('PITR_OK', json.dumps(result))
except Exception as error:
    result.update({'status': 'failed', 'error': str(error), 'elapsed_seconds': round(time.monotonic() - started, 2)})
    save()
    raise
