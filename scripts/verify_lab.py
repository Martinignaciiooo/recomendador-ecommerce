"""Evidencias reales de la cuenta de practica. Los secretos nunca se exportan."""
import concurrent.futures
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import boto3

REGION = 'us-east-1'
STACK = 'shopfast-ep2-lab'
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidencias'
OUT.mkdir(exist_ok=True)
session = boto3.Session(region_name=REGION)
cfn = session.client('cloudformation')
ecs = session.client('ecs')
elbv2 = session.client('elbv2')
ec2 = session.client('ec2')
cw = session.client('cloudwatch')

def save(name, data):
    (OUT / (name + '.json')).write_text(json.dumps(data, indent=2, default=str), encoding='utf-8')

def stack():
    return cfn.describe_stacks(StackName=STACK)['Stacks'][0]

def outputs():
    return {i['OutputKey']: i['OutputValue'] for i in stack()['Outputs']}

def http(path, token=None, payload=None, event_id=None):
    headers = {}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if event_id:
        headers['Idempotency-Key'] = event_id
    if payload is not None:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(config['ApiUrl'] + path, headers=headers,
        data=json.dumps(payload).encode() if payload is not None else None)
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.status, json.load(response), (time.perf_counter() - start) * 1000
    except urllib.error.HTTPError as error:
        return error.code, json.load(error), (time.perf_counter() - start) * 1000

def functional(suffix='funcional'):
    health_status, health, _ = http('/health/ready')
    assert health_status == 200 and health['modelo'] == 'v20260921-052859', health
    denied, _, _ = http('/recomendaciones?user_id=1')
    assert denied == 401, denied
    status, users, _ = http('/usuarios-ejemplo?n=1', token)
    assert status == 200 and users
    known, personalized, _ = http('/recomendaciones?user_id=' + urllib.parse.quote(users[0]), token)
    assert known == 200 and personalized['source'] in ['model', 'cache'], personalized
    cold, fallback, _ = http('/recomendaciones?user_id=999999999999', token)
    assert cold == 200 and fallback['source'] == 'fallback'
    result = {'utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'url': config['ApiUrl'],
              'health': health, 'without_token': denied,
              'known_user_source': personalized['source'], 'new_user_source': fallback['source']}
    result['model_source'] = {p['ParameterKey']: p['ParameterValue'] for p in stack()['Parameters']}['Mode']
    save(suffix, result)
    print(json.dumps(result))
    return users[0]

def inventory(suffix='infraestructura'):
    description = stack()
    service = ecs.describe_services(cluster=config['ClusterName'], services=[config['ServiceName']])['services'][0]
    arns = ecs.list_tasks(cluster=config['ClusterName'], serviceName=config['ServiceName'])['taskArns']
    tasks = ecs.describe_tasks(cluster=config['ClusterName'], tasks=arns)['tasks'] if arns else []
    health = elbv2.describe_target_health(TargetGroupArn=config['TargetArn'])['TargetHealthDescriptions']
    result = {'stack_status': description['StackStatus'], 'running': service['runningCount'],
              'desired': service['desiredCount'], 'assign_public_ip': service['networkConfiguration']['awsvpcConfiguration']['assignPublicIp'],
              'tasks': [{'id': t['taskArn'].split('/')[-1], 'az': t['availabilityZone'],
                         'status': t['lastStatus'], 'health': t.get('healthStatus'),
                         'private_ip': t['containers'][0].get('networkInterfaces', [])} for t in tasks],
              'targets': [{'id': t['Target']['Id'], 'state': t['TargetHealth']['State']} for t in health]}
    resources = cfn.describe_stack_resources(StackName=STACK)['StackResources']
    ids = {r['LogicalResourceId']: r['PhysicalResourceId'] for r in resources}
    result['security_groups'] = ec2.describe_security_groups(GroupIds=[ids[k] for k in ['TaskSG','AlbSG','VpcLinkSG']])['SecurityGroups']
    result['nat_gateways'] = ec2.describe_nat_gateways(NatGatewayIds=[ids['Nat1'],ids['Nat2']])['NatGateways']
    result['task_definition'] = ecs.describe_task_definition(taskDefinition=service['taskDefinition'])['taskDefinition']
    save(suffix, result)
    return result

def topology_assertions():
    data = inventory()
    assert data['running'] == 2 and data['assign_public_ip'] == 'DISABLED', data
    assert len({t['az'] for t in data['tasks'] if t['status'] == 'RUNNING'}) == 2, data
    assert len(data['targets']) == 2 and all(t['state'] == 'healthy' for t in data['targets']), data
    print('TOPOLOGY_OK: dos AZ, dos targets healthy, tareas privadas')

def events(user):
    event_id = str(uuid.uuid4())
    payload = {'user_id': user, 'product_id': '3829355', 'event_type': 'view'}
    statuses = [http('/eventos', token, payload, event_id)[0] for _ in range(2)]
    assert statuses == [202, 202], statuses
    table = session.resource('dynamodb').Table(config['EventsTable'])
    start = time.monotonic()
    item = None
    while time.monotonic() - start < 90:
        item = table.get_item(Key={'event_id': event_id}, ConsistentRead=True).get('Item')
        if item:
            break
        time.sleep(2)
    assert item and item['event_id'] == event_id and item['user_id'] == user, item
    # Solo el consumidor condicional escribe en esta tabla de prueba.
    save('eventos-idempotencia', {'event_id': event_id, 'http_statuses': statuses,
        'persisted_event': item, 'observed_processing_s': time.monotonic() - start,
        'logical_records_for_primary_key': 1})
    print('EVENTS_OK: dos POST aceptados, un UUID persistido')

def load(user):
    os.environ['RECO_API_TOKEN'] = token
    os.environ['TEST_USER_ID'] = user
    import subprocess
    for requests, concurrency in [(100,5),(500,20)]:
        subprocess.run([sys.executable,str(ROOT/'scripts/load_test.py'),'--url',config['ApiUrl'],
                        '--requests',str(requests),'--concurrency',str(concurrency),
                        '--output',str(OUT/f'carga-{concurrency}.json')], check=True)

def monitoring():
    resources = cfn.describe_stack_resources(StackName=STACK)['StackResources']
    ids = {r['LogicalResourceId']: r['PhysicalResourceId'] for r in resources}
    alarms = cw.describe_alarms(AlarmNames=[ids[k] for k in ['LatencyAlarm','ErrorsAlarm','HealthyAlarm','AgeAlarm','DeadAlarm']])['MetricAlarms']
    save('alarmas', alarms)
    # Canal de alerta de laboratorio: CloudWatch -> SNS -> SQS, sin correo supuesto.
    sqs = session.client('sqs')
    alarm_name = ids['AgeAlarm']
    cw.set_alarm_state(AlarmName=alarm_name, StateValue='ALARM', StateReason='Prueba controlada ShopFast EP2')
    start = time.monotonic()
    received = None
    while time.monotonic() - start < 90:
        for message in sqs.receive_message(QueueUrl=config['AlertQueueUrl'],WaitTimeSeconds=10,MaxNumberOfMessages=10).get('Messages',[]):
            envelope = json.loads(message['Body'])
            notice = json.loads(envelope['Message'])
            if notice.get('AlarmName') == alarm_name and notice.get('NewStateValue') == 'ALARM':
                received = {'type':envelope['Type'],'alarm':notice['AlarmName'],
                            'state':notice['NewStateValue'],'reason':notice['NewStateReason'],
                            'timestamp':notice['StateChangeTime']}
            sqs.delete_message(QueueUrl=config['AlertQueueUrl'],ReceiptHandle=message['ReceiptHandle'])
        if received:
            break
    cw.set_alarm_state(AlarmName=alarm_name,StateValue='OK',StateReason='Fin de la prueba controlada EP2')
    assert received, 'SNS no entrego la notificacion a la cola de prueba'
    save('notificacion-sns-recibida', received)
    logs = session.client('logs')
    for key, filename in [('Logs','logs-api'),('WorkerLogs','logs-worker')]:
        streams = logs.describe_log_streams(logGroupName=ids[key],orderBy='LastEventTime',descending=True,limit=2)['logStreams']
        records=[]
        for stream in streams:
            records.extend(logs.get_log_events(logGroupName=ids[key],logStreamName=stream['logStreamName'],limit=30)['events'])
        save(filename,records)
    metrics = []
    alb_full = ids['Alb'].split(':loadbalancer/')[1]
    for namespace, name, dimensions, stats in [
        ('AWS/ApplicationELB','TargetResponseTime',[{'Name':'LoadBalancer','Value':alb_full}],{'ExtendedStatistics':['p95']}),
        ('AWS/ECS','CPUUtilization',[{'Name':'ClusterName','Value':config['ClusterName']},{'Name':'ServiceName','Value':config['ServiceName']}],{'Statistics':['Average','Maximum']}),
        ('AWS/ECS','MemoryUtilization',[{'Name':'ClusterName','Value':config['ClusterName']},{'Name':'ServiceName','Value':config['ServiceName']}],{'Statistics':['Average','Maximum']})]:
        now=dt.datetime.now(dt.timezone.utc)
        data=cw.get_metric_statistics(Namespace=namespace,MetricName=name,Dimensions=dimensions,
            StartTime=now-dt.timedelta(minutes=30),EndTime=now,Period=60,**stats)
        metrics.append({'metric':name,'datapoints':data['Datapoints']})
    save('cloudwatch-metricas', metrics)
    print('MONITORING_OK: alarma, SNS recibido y logs guardados')

def recovery():
    before = inventory('recuperacion-antes')
    assert before['running']==2 and len(before['targets'])==2
    task = ecs.list_tasks(cluster=config['ClusterName'],serviceName=config['ServiceName'])['taskArns'][0]
    start=time.monotonic()
    ecs.stop_task(cluster=config['ClusterName'],task=task,reason='Prueba controlada de reposicion EP2')
    statuses=[]
    replacement=None
    while time.monotonic()-start<360:
        try:
            status,_,latency=http('/recomendaciones?user_id=999999999999',token)
            statuses.append({'seconds':round(time.monotonic()-start,2),'status':status,'latency_ms':latency})
        except Exception:
            statuses.append({'seconds':round(time.monotonic()-start,2),'status':0})
        time.sleep(1)
        if len(statuses)%5==0:
            task_arns=ecs.list_tasks(cluster=config['ClusterName'],serviceName=config['ServiceName'])['taskArns']
            targets=elbv2.describe_target_health(TargetGroupArn=config['TargetArn'])['TargetHealthDescriptions']
            if task not in task_arns and len(task_arns)==2 and len(targets)==2 and all(t['TargetHealth']['State']=='healthy' for t in targets):
                replacement=round(time.monotonic()-start,2)
                break
    save('recuperacion',{'replacement_seconds':replacement,'request_count':len(statuses),
                        'errors':sum(r['status']!=200 for r in statuses),'requests':statuses,
                        'target_seconds':120,'target_met':replacement is not None and replacement<=120})
    inventory('recuperacion-despues')
    assert replacement is not None, 'No se observo reposicion completa dentro de 360s'
    print('RECOVERY_OK',replacement)

def closed():
    previous=json.loads((OUT/'antes-del-cierre.json').read_text())
    vpc=previous['security_groups'][0]['VpcId']
    nat=session.client('ec2').describe_nat_gateways(Filters=[{'Name':'vpc-id','Values':[vpc]}])['NatGateways']
    albs=elbv2.describe_load_balancers()['LoadBalancers']
    clusters=ecs.list_clusters()['clusterArns']
    old_allocations={a['AllocationId'] for n in previous['nat_gateways'] for a in n['NatGatewayAddresses']}
    remaining_allocations=[a['AllocationId'] for a in ec2.describe_addresses()['Addresses'] if a.get('AllocationId') in old_allocations]
    original=json.loads((OUT/'stack-operativo.json').read_text())['Stacks'][0]
    old={i['OutputKey']:i['OutputValue'] for i in original['Outputs']}
    result={'nat_remaining':[n['NatGatewayId'] for n in nat if n['State'] not in ['deleted','failed']],
            'load_balancers_in_practice_vpc':[a['LoadBalancerArn'] for a in albs if a['VpcId']==vpc],
            'practice_cluster_remaining':any(a.endswith('/'+old['ClusterName']) for a in clusters),
            'practice_eip_allocations_remaining':remaining_allocations,
            'retained':{'S3':old['ModelBucket'],'DynamoDB':old['EventsTable'],'ECR':old['RepositoryUri']},
            'note':'Datos, imagen y logs retenidos tienen costo residual; no hay NAT, ALB ni ECS activos de esta practica.'}
    save('cierre-verificado',result)
    assert not result['nat_remaining'] and not result['load_balancers_in_practice_vpc'] and not result['practice_cluster_remaining'] and not remaining_allocations,result
    print('CLOSED_OK: no NAT, ALB ni ECS de practica activos')

if __name__=='__main__':
    mode=sys.argv[1] if len(sys.argv)>1 else 'all'
    if mode=='closed':
        closed()
        raise SystemExit
    config=outputs()
    if mode=='inventory':
        inventory(sys.argv[2] if len(sys.argv)>2 else 'infraestructura')
        raise SystemExit
    token=json.loads(session.client('secretsmanager').get_secret_value(SecretId=config['SecretArn'])['SecretString'])['token']
    if mode=='functional':
        functional(sys.argv[2] if len(sys.argv)>2 else 'funcional')
    elif mode=='recovery':
        recovery()
    else:
        user=functional()
        topology_assertions()
        events(user)
        load(user)
        monitoring()
        print('VERIFY_ALL_OK')
