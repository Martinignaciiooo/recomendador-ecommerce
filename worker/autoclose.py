"""Cierre acotado a este stack de demostracion; no elimina datos retenidos."""
import datetime as dt
import os

import boto3


def handler(event, context):
    stack_id = os.environ['STACK_ID']
    cf = boto3.client('cloudformation')
    stack = cf.describe_stacks(StackName=stack_id)['Stacks'][0]
    tags = {item['Key']: item['Value'] for item in stack.get('Tags', [])}
    if stack['StackId'] != stack_id or tags.get('Project') != 'ShopFastEP2' or tags.get('Practice') != 'true':
        raise ValueError('El destino no es el stack autorizado de esta practica')
    if event.get('dry_run'):
        return {'dry_run': True, 'target': stack['StackName'], 'status': stack['StackStatus']}
    deadline = dt.datetime.fromisoformat(os.environ['CLOSE_AT'])
    if deadline.tzinfo is None or dt.datetime.now(dt.timezone.utc) < deadline:
        raise ValueError('Todavia no corresponde cerrar la demostracion')
    if stack['StackStatus'].startswith('DELETE_'):
        return {'already_closing': True}
    cf.delete_stack(StackName=stack_id)
    return {'deletion_requested': True, 'target': stack['StackName']}
