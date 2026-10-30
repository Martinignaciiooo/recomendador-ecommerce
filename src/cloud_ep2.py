"""Adaptadores AWS. Conserva Recommender, endpoints y artefactos del repositorio."""
import os, json, io, tarfile
from pathlib import Path
import boto3
from botocore.config import Config
CFG=Config(connect_timeout=2,read_timeout=5,retries={'max_attempts':2,'mode':'standard'})
_sqs=None

def send_event(event):
    global _sqs
    if _sqs is None:_sqs=boto3.client('sqs',config=CFG)
    _sqs.send_message(QueueUrl=os.environ['QUEUE_URL'],MessageBody=json.dumps(event))

def download_model():
    if os.environ.get('MODEL_SOURCE','bundled')!='s3':return
    bucket,key=os.environ['MODEL_BUCKET'],os.environ['MODEL_KEY']
    if not key.startswith('models/'):raise ValueError('Clave del modelo debe comenzar con models/')
    blob=boto3.client('s3',config=CFG).get_object(Bucket=bucket,Key=key)['Body'].read(30*1024*1024+1)
    if len(blob)>30*1024*1024:raise ValueError('Archivo comprimido excede 30 MiB')
    dest=Path('/tmp/ep2-models/active');dest.mkdir(parents=True,exist_ok=True)
    # Solo dos ficheros conocidos. No extractall, enlaces ni rutas del tar.
    with tarfile.open(fileobj=io.BytesIO(blob),mode='r:gz') as archive:
        for name in ['factors.npz','meta.json']:
            member=archive.getmember(name)
            if not member.isfile() or member.size>50*1024*1024:raise ValueError('Miembro invalido')
            (dest/name).write_bytes(archive.extractfile(member).read())
    (dest.parent/'current').write_text('active')
    os.environ['MODEL_ROOT']=str(dest.parent)
