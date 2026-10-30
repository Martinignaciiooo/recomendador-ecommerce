import pytest
from worker import autoclose


@pytest.fixture
def target(monkeypatch):
    class CF:
        def __init__(self):
            self.deleted = []
            self.stack = {'StackId': 'arn:aws:cloudformation:us-east-1:123456789012:stack/shopfast-test/own-id',
                          'StackName': 'shopfast-test', 'StackStatus': 'UPDATE_COMPLETE',
                          'Tags': [{'Key': 'Project', 'Value': 'ShopFastEP2'}, {'Key': 'Practice', 'Value': 'true'}]}
        def describe_stacks(self, **kwargs):
            return {'Stacks': [self.stack]}
        def delete_stack(self, **kwargs):
            self.deleted.append(kwargs['StackName'])
    cf = CF()
    monkeypatch.setenv('STACK_ID', cf.stack['StackId'])
    monkeypatch.setenv('CLOSE_AT', '2000-01-01T00:00:00+00:00')
    monkeypatch.setattr(autoclose.boto3, 'client', lambda service: cf)
    return cf


def test_dry_run_does_not_delete(target):
    assert autoclose.handler({'dry_run': True}, None)['dry_run']
    assert target.deleted == []


def test_refuses_other_project(target):
    target.stack['Tags'][0]['Value'] = 'AnotherProject'
    with pytest.raises(ValueError):
        autoclose.handler({}, None)
    assert target.deleted == []


def test_refuses_before_deadline(target, monkeypatch):
    monkeypatch.setenv('CLOSE_AT', '2999-01-01T00:00:00+00:00')
    with pytest.raises(ValueError):
        autoclose.handler({}, None)
    assert target.deleted == []


def test_deletes_only_bound_stack_ignoring_event_override(target):
    assert autoclose.handler({'StackName': 'other-project'}, None)['deletion_requested']
    assert target.deleted == [target.stack['StackId']]
