import datetime as dt
import sqlite3
import pytest
from scripts.export_events_lab import export, instant, normalize

CUT = instant('2026-10-30T03:00:00Z')

def event(key='a', timestamp='2026-10-30T02:00:00Z'):
    return {'event_id': key, 'timestamp': timestamp, 'interaction_type': 'view',
            'user_id': '1515915625512345678', 'product_id': '3829355'}

def test_temporal_cut_deduplication_and_exact_ids():
    rows = normalize([event(), event(), event('future','2026-10-30T04:00:00Z')], CUT)
    assert len(rows) == 1
    assert rows[0][4] == 1515915625512345678

def test_conflicting_uuid_is_rejected():
    other = {**event(), 'interaction_type': 'purchase'}
    with pytest.raises(ValueError, match='incompatibles'):
        normalize([event(), other], CUT)

def test_pagination_and_training_schema(tmp_path):
    class Table:
        name = 'test-events'
        def scan(self, **params):
            assert params['ConsistentRead'] is True
            return {'Items': [event('b')]} if 'ExclusiveStartKey' in params else {'Items': [event()], 'LastEvaluatedKey': {'event_id': 'a'}}
    destination = tmp_path / 'events.db'
    manifest = export(Table(), CUT, destination)
    with sqlite3.connect(destination) as connection:
        rows = connection.execute('SELECT event_time, event_type, product_id, user_id FROM eventos').fetchall()
    assert len(rows) == manifest['exported'] == 2
    assert rows[0][3] == 1515915625512345678
    with pytest.raises(FileExistsError):
        export(Table(), CUT, destination)

def test_reads_are_bounded_before_writing(tmp_path):
    class Table:
        name = 'test-events'
        def scan(self, **params):
            return {'Items': [event('a'), event('b')]}
    destination = tmp_path / 'events.db'
    with pytest.raises(ValueError, match='Limite'):
        export(Table(), CUT, destination, max_items=1)
    assert not destination.exists()
