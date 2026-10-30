"""Deriva una plantilla para Learner Lab sin modificar la referencia de producción."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
template = json.loads((ROOT / 'infra/shopfast.json').read_text(encoding='utf-8'))
template['Description'] = 'ShopFast EP2 Learner Lab: LabRole existente, API Gateway HTTPS y ALB interno, dos AZ.'
for name in ['NotifyEmail', 'PracticeBudget', 'CertificateArn']:
    template['Parameters'].pop(name)
resources = template['Resources']
for name in ['WorkerRole', 'ExecutionRole', 'TaskRole', 'Budget']:
    resources.pop(name)
lab_role = {'Fn::Sub': 'arn:${AWS::Partition}:iam::${AWS::AccountId}:role/LabRole'}
resources['Consumer']['Properties']['Role'] = lab_role
resources['Task']['Properties']['ExecutionRoleArn'] = lab_role
resources['Task']['Properties']['TaskRoleArn'] = lab_role
resources['Topic']['Properties'] = {}
# Se verifica la notificación SNS en una cola, sin asumir un correo del usuario.
resources['AlertQueue'] = {'Type': 'AWS::SQS::Queue', 'Properties': {
    'SqsManagedSseEnabled': True, 'MessageRetentionPeriod': 86400}}
resources['AlertQueuePolicy'] = {'Type': 'AWS::SQS::QueuePolicy', 'Properties': {
    'Queues': [{'Ref': 'AlertQueue'}], 'PolicyDocument': {
        'Version': '2012-10-17', 'Statement': [{
            'Effect': 'Allow', 'Principal': {'Service': 'sns.amazonaws.com'},
            'Action': 'sqs:SendMessage', 'Resource': {'Fn::GetAtt': ['AlertQueue', 'Arn']},
            'Condition': {'ArnEquals': {'aws:SourceArn': {'Ref': 'Topic'}}}}]}}}
resources['AlertSubscription'] = {'Type': 'AWS::SNS::Subscription', 'Properties': {
    'TopicArn': {'Ref': 'Topic'}, 'Protocol': 'sqs',
    'Endpoint': {'Fn::GetAtt': ['AlertQueue', 'Arn']}}, 'DependsOn': 'AlertQueuePolicy'}

resources['VpcLinkSG'] = {'Type': 'AWS::EC2::SecurityGroup', 'Properties': {
    'GroupDescription': 'API Gateway VPC Link hacia ALB interno', 'VpcId': {'Ref': 'Vpc'},
    'SecurityGroupEgress': [{'IpProtocol': 'tcp', 'FromPort': 80, 'ToPort': 80,
                             'CidrIp': '10.42.0.0/16'}]}}
resources['AlbSG']['Properties']['GroupDescription'] = 'ALB privado solo desde API Gateway VPC Link'
resources['AlbSG']['Properties']['SecurityGroupIngress'] = [{
    'IpProtocol': 'tcp', 'FromPort': 80, 'ToPort': 80,
    'SourceSecurityGroupId': {'Ref': 'VpcLinkSG'}}]
resources['AlbSG']['Properties']['SecurityGroupEgress'] = [{
    'IpProtocol': 'tcp', 'FromPort': 8000, 'ToPort': 8000, 'CidrIp': '10.42.0.0/16'}]
resources['Alb']['Properties']['Scheme'] = 'internal'
resources['Alb']['Properties']['Subnets'] = [{'Ref': 'Private1'}, {'Ref': 'Private2'}]
listener = resources['Listener']['Properties']
listener['Port'] = 80
listener['Protocol'] = 'HTTP'
listener.pop('Certificates')
listener.pop('SslPolicy')

def service_resource(kind, properties, **extra):
    return {'Type': kind, 'Condition': 'DeployService', 'Properties': properties, **extra}

resources['HttpApi'] = service_resource('AWS::ApiGatewayV2::Api', {
    'Name': {'Fn::Sub': '${AWS::StackName}-https'}, 'ProtocolType': 'HTTP',
    'Description': 'HTTPS gestionado por AWS. Backend privado mediante VPC Link.'})
resources['VpcLink'] = service_resource('AWS::ApiGatewayV2::VpcLink', {
    'Name': {'Fn::Sub': '${AWS::StackName}-link'},
    'SubnetIds': [{'Ref': 'Private1'}, {'Ref': 'Private2'}],
    'SecurityGroupIds': [{'Ref': 'VpcLinkSG'}]})
resources['ApiIntegration'] = service_resource('AWS::ApiGatewayV2::Integration', {
    'ApiId': {'Ref': 'HttpApi'}, 'IntegrationType': 'HTTP_PROXY',
    'IntegrationMethod': 'ANY', 'IntegrationUri': {'Ref': 'Listener'},
    'ConnectionType': 'VPC_LINK', 'ConnectionId': {'Ref': 'VpcLink'},
    'PayloadFormatVersion': '1.0', 'TimeoutInMillis': 30000,
    'RequestParameters': {'overwrite:path': '$request.path'}})
for name, route in [('ApiRoute', 'ANY /{proxy+}'), ('ApiRootRoute', 'ANY /')]:
    resources[name] = service_resource('AWS::ApiGatewayV2::Route', {
        'ApiId': {'Ref': 'HttpApi'}, 'RouteKey': route,
        'Target': {'Fn::Join': ['/', ['integrations', {'Ref': 'ApiIntegration'}]]}})
resources['ApiStage'] = service_resource('AWS::ApiGatewayV2::Stage', {
    'ApiId': {'Ref': 'HttpApi'}, 'StageName': '$default', 'AutoDeploy': True,
    'DefaultRouteSettings': {'ThrottlingBurstLimit': 100, 'ThrottlingRateLimit': 200}})
for name in ['Logs', 'WorkerLogs']:
    resources[name]['DeletionPolicy'] = 'Retain'
    resources[name]['UpdateReplacePolicy'] = 'Retain'
# Un nombre generado permite volver a crear el stack conservando los logs anteriores.
resources['WorkerLogs']['Properties'].pop('LogGroupName', None)
resources['Consumer']['Properties']['LoggingConfig'] = {'LogGroup': {'Ref': 'WorkerLogs'}}
resources['Consumer'].pop('DependsOn', None)
# El bucket retenido debe conservar tambien la exigencia de transporte HTTPS.
resources['ModelPolicy']['DeletionPolicy'] = 'Retain'
resources['ModelPolicy']['UpdateReplacePolicy'] = 'Retain'

# Opcional: cierre de la demo sin depender de que CloudShell siga abierto.
template['Parameters']['DemoCloseAt'] = {'Type': 'String', 'Default': '',
    'Description': 'Fecha UTC ISO8601 del cierre; vacia deshabilita el cierre automatico.'}
template['Parameters']['DemoCloseCron'] = {'Type': 'String', 'Default': '',
    'Description': 'Cron UTC de EventBridge para una sola fecha, con anio explicito.'}
template['Conditions']['AutoCloseDemo'] = {'Fn::And': [
    {'Condition': 'DeployService'},
    {'Fn::Not': [{'Fn::Equals': [{'Ref': 'DemoCloseAt'}, '']}]},
    {'Fn::Not': [{'Fn::Equals': [{'Ref': 'DemoCloseCron'}, '']}]}]}
resources['AutoCloseLogs'] = {'Type': 'AWS::Logs::LogGroup', 'Condition': 'AutoCloseDemo',
    'DeletionPolicy': 'Retain', 'UpdateReplacePolicy': 'Retain',
    'Properties': {'RetentionInDays': 7}}
resources['AutoCloseFunction'] = {'Type': 'AWS::Lambda::Function', 'Condition': 'AutoCloseDemo',
    'Properties': {'Runtime': 'python3.12', 'Handler': 'index.handler', 'Role': lab_role,
        'Timeout': 30, 'MemorySize': 128,
        'LoggingConfig': {'LogGroup': {'Ref': 'AutoCloseLogs'}},
        'Environment': {'Variables': {'STACK_ID': {'Ref': 'AWS::StackId'}, 'CLOSE_AT': {'Ref': 'DemoCloseAt'}}},
        'Code': {'ZipFile': (ROOT / 'worker/autoclose.py').read_text(encoding='utf-8')}}}
resources['AutoCloseRule'] = {'Type': 'AWS::Events::Rule', 'Condition': 'AutoCloseDemo',
    'Properties': {'ScheduleExpression': {'Ref': 'DemoCloseCron'}, 'State': 'ENABLED',
        'Targets': [{'Arn': {'Fn::GetAtt': ['AutoCloseFunction', 'Arn']}, 'Id': 'CloseOnlyThisDemo',
                     'Input': '{}'}]}}
resources['AutoClosePermission'] = {'Type': 'AWS::Lambda::Permission', 'Condition': 'AutoCloseDemo',
    'Properties': {'Action': 'lambda:InvokeFunction', 'FunctionName': {'Ref': 'AutoCloseFunction'},
        'Principal': 'events.amazonaws.com', 'SourceArn': {'Fn::GetAtt': ['AutoCloseRule', 'Arn']}}}
template['Outputs']['DemoClosesAtUTC'] = {'Condition': 'AutoCloseDemo', 'Value': {'Ref': 'DemoCloseAt'}}
template['Outputs']['AutoCloseFunctionArn'] = {'Condition': 'AutoCloseDemo',
    'Value': {'Fn::GetAtt': ['AutoCloseFunction', 'Arn']}}
template['Outputs']['ApiUrl'] = {
    'Condition': 'DeployService', 'Value': {'Fn::GetAtt': ['HttpApi', 'ApiEndpoint']}}
template['Outputs']['AlertQueueUrl'] = {'Value': {'Ref': 'AlertQueue'}}
template['Outputs']['LabRoleUsed'] = {'Value': lab_role}
template['Outputs']['AlbDns']['Description'] = 'DNS interno; acceder desde Internet por ApiUrl HTTPS.'
(ROOT / 'infra/shopfast-learner-lab.json').write_text(
    json.dumps(template, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('infra/shopfast-learner-lab.json preparada')
