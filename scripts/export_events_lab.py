"""Exportacion acotada y reproducible de eventos DynamoDB al esquema del entrenamiento.

Ejecutar sobre una tabla sin escrituras durante la exportacion, o una copia PITR.
Un Scan consistente no equivale a una instantanea transaccional entre paginas.
No sobrescribe una base existente ni ejecuta entrenamiento/promocion de modelos.
"""
import argparse
import datetime as dt
import hashlib
import json
import sqlite3
from pathlib import Path

import boto3


def instant(value):
    value = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo is None:
        raise ValueError('El corte y las fechas deben incluir zona horaria')
    return value.astimezone(dt.timezone.utc)


def normalize(items, before):
    result = {}
    for item in items:
        moment = instant(item['timestamp'])
        if moment > before:
            continue
        event_id = item['event_id']
        if not isinstance(event_id, str) or not event_id:
            raise ValueError('event_id vacio')
        if item['interaction_type'] not in ['view', 'cart', 'purchase']:
            raise ValueError('Tipo de evento no soportado')
        product, user = int(item['product_id']), int(item['user_id'])
        if not all(-(2**63) <= n < 2**63 for n in [product, user]):
            raise ValueError('ID fuera del rango entero de SQLite')
        row = (event_id, moment.isoformat(), item['interaction_type'], product, user)
        if event_id in result and result[event_id] != row:
            raise ValueError('Un UUID tiene contenidos incompatibles')
        result[event_id] = row
    return sorted(result.values(), key=lambda r: (r[1], r[0]))


def export(table, before, destination, max_items=10000):
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError('Elegir otra ruta: no se sobrescribe una base existente')
    collected = []
    key = None
    while True:
        params = {'ConsistentRead': True, 'Limit': min(200, max_items + 1 - len(collected))}
        if key:
            params['ExclusiveStartKey'] = key
        response = table.scan(**params)
        collected.extend(response.get('Items', []))
        if len(collected) > max_items:
            raise ValueError('Limite de lectura de la practica excedido; usar exportacion S3/PITR para grandes tablas')
        key = response.get('LastEvaluatedKey')
        if not key:
            break
    rows = normalize(collected, before)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(destination) as connection:
        connection.execute('CREATE TABLE eventos (event_id TEXT PRIMARY KEY, event_time TEXT NOT NULL, event_type TEXT NOT NULL, product_id INTEGER NOT NULL, user_id INTEGER NOT NULL)')
        connection.executemany('INSERT INTO eventos VALUES (?,?,?,?,?)', rows)
    manifest = {'table': table.name, 'before_utc': before.isoformat(),
                'scanned': len(collected), 'exported': len(rows),
                'canonical_rows_sha256': hashlib.sha256(json.dumps(rows, separators=(',', ':')).encode()).hexdigest(),
                'output': str(destination), 'training_executed': False,
                'snapshot_requirement': 'Tabla sin escrituras o copia PITR estable; Scan no ofrece snapshot entre paginas'}
    destination.with_suffix('.manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--table', required=True)
    parser.add_argument('--before', required=True, help='Corte inclusivo con zona horaria ISO8601')
    parser.add_argument('--output', required=True)
    parser.add_argument('--region', default='us-east-1')
    parser.add_argument('--max-items', type=int, default=10000)
    args = parser.parse_args()
    if not 1 <= args.max_items <= 10000:
        parser.error('max-items debe estar entre 1 y 10000 para esta practica')
    target = boto3.resource('dynamodb', region_name=args.region).Table(args.table)
    print(json.dumps(export(target, instant(args.before), args.output, args.max_items), indent=2))
