#!/usr/bin/env bash
# Ejecutar en AWS CloudShell de Learner Lab, us-east-1. Nunca imprime secretos.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
export AWS_DEFAULT_REGION=us-east-1 AWS_PAGER=''
STACK=shopfast-ep2-lab
EXPECTED_ACCOUNT=${SHOPFAST_EXPECTED_ACCOUNT_ID:-}
PHASE=${1:-preflight}
IMAGE=shopfast-ep2:lab
TAG=${2:-ep2-lab-v1}
mkdir -p evidencias
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
if [[ -z "$EXPECTED_ACCOUNT" || "$ACCOUNT" != "$EXPECTED_ACCOUNT" ]]; then
  printf 'Configure SHOPFAST_EXPECTED_ACCOUNT_ID con la cuenta del laboratorio autorizado. No se cambia ningun recurso.\n' >&2
  exit 1
fi
output() {
  aws cloudformation describe-stacks --stack-name "$STACK" --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue | [0]" --output text
}
deploy() {
  aws cloudformation deploy --stack-name "$STACK" --template-file infra/shopfast-learner-lab.json \
    --tags Project=ShopFastEP2 ManagedBy=CloudFormation Practice=true \
    --parameter-overrides "ImageTag=$1" "Mode=${2:-bundled}" "ModelKey=${3:-}" \
    --no-fail-on-empty-changeset
  aws cloudformation describe-stacks --stack-name "$STACK" > evidencias/stack-operativo.json
}
case "$PHASE" in
  preflight)
    aws iam get-role --role-name LabRole --query 'Role.{Name:RoleName,Trust:AssumeRolePolicyDocument}' > evidencias/labrole.json
    aws cloudformation validate-template --template-body file://infra/shopfast-learner-lab.json > evidencias/template-validation.json
    aws cloudformation list-stacks --query 'StackSummaries[?StackStatus!=`DELETE_COMPLETE`].{Name:StackName,Status:StackStatus}' > evidencias/stacks-previos.json
    aws ec2 describe-instances --query 'Reservations[].Instances[].{Id:InstanceId,State:State.Name}' > evidencias/ec2-previas.json
    docker info --format '{{.ServerVersion}}'
    printf 'PREFLIGHT_OK\n'
    ;;
  build)
    docker build --platform linux/amd64 -f Dockerfile.ep2 -t "$IMAGE" .
    TOKEN=$(python3 -c 'import secrets; print(secrets.token_urlsafe(36))')
    CONTAINER=$(docker run -d -p 127.0.0.1:18000:8000 -e EVENTS_BACKEND=sqlite -e RECO_API_TOKEN="$TOKEN" "$IMAGE")
    trap 'docker rm -f "$CONTAINER" >/dev/null' EXIT
    export RECO_API_TOKEN="$TOKEN"
    python3 - <<'PY'
import os,time,json,urllib.request,urllib.error
base='http://127.0.0.1:18000'
for attempt in range(60):
 try:
  with urllib.request.urlopen(base+'/health/ready',timeout=2) as r: health=json.load(r)
  assert health['modelo']=='v20260921-052859'
  break
 except Exception:
  if attempt==59: raise
  time.sleep(1)
try:
 urllib.request.urlopen(base+'/recomendaciones?user_id=1',timeout=5)
 raise AssertionError('La API dejo entrar sin token')
except urllib.error.HTTPError as e: assert e.code==401
req=urllib.request.Request(base+'/recomendaciones?user_id=999999999999',headers={'Authorization':'Bearer '+os.environ['RECO_API_TOKEN']})
with urllib.request.urlopen(req,timeout=5) as r: data=json.load(r)
assert data['source']=='fallback' and len(data['recommendations'])==10
result={'health':health,'without_token':401,'authenticated_fallback':True,'image':'linux/amd64'}
open('evidencias/docker-smoke.json','w').write(json.dumps(result,indent=2))
print('DOCKER_SMOKE_OK')
PY
    ;;
  bootstrap)
    if aws cloudformation describe-stacks --stack-name "$STACK" >/dev/null 2>&1; then
      printf 'El stack ya existe. Inspeccionarlo; no ejecutar bootstrap sobre un servicio activo.\n' >&2
      exit 1
    fi
    deploy ''
    printf 'BOOTSTRAP_OK\n'
    ;;
  service)
    REPO=$(output RepositoryUri)
    aws ecr get-login-password | docker login --username AWS --password-stdin "${REPO%%/*}"
    docker tag "$IMAGE" "$REPO:$TAG"
    docker push "$REPO:$TAG"
    deploy "$TAG"
    aws ecs wait services-stable --cluster "$(output ClusterName)" --services "$(output ServiceName)"
    output ApiUrl
    printf 'SERVICE_OK\n'
    ;;
  model-s3)
    python3 scripts/package_model.py
    aws s3 cp model.tar.gz "s3://$(output ModelBucket)/models/v20260921-052859.tar.gz"
    CURRENT_TAG=$(aws cloudformation describe-stacks --stack-name "$STACK" --query 'Stacks[0].Parameters[?ParameterKey==`ImageTag`].ParameterValue | [0]' --output text)
    deploy "$CURRENT_TAG" s3 models/v20260921-052859.tar.gz
    cp evidencias/stack-operativo.json evidencias/stack-model-s3.json
    aws ecs wait services-stable --cluster "$(output ClusterName)" --services "$(output ServiceName)"
    python3 scripts/verify_lab.py functional model-s3
    ;;
  rollback)
    CURRENT_TAG=$(aws cloudformation describe-stacks --stack-name "$STACK" --query 'Stacks[0].Parameters[?ParameterKey==`ImageTag`].ParameterValue | [0]' --output text)
    START=$(date +%s)
    deploy "$CURRENT_TAG" bundled
    cp evidencias/stack-operativo.json evidencias/stack-rollback.json
    aws ecs wait services-stable --cluster "$(output ClusterName)" --services "$(output ServiceName)"
    python3 scripts/verify_lab.py functional rollback
    python3 - "$START" <<'PY'
import sys,time,json
open('evidencias/rollback-tiempo.json','w').write(json.dumps({'seconds':int(time.time())-int(sys.argv[1]),'scope':'S3 al modelo incluido; misma version del modelo'},indent=2))
PY
    ;;
  verify) python3 scripts/verify_lab.py all ;;
  recovery) python3 scripts/verify_lab.py recovery ;;
  cleanup)
    # Solo el stack nuevo de esta practica. ECR/S3/DynamoDB y logs se conservan.
    python3 scripts/verify_lab.py inventory antes-del-cierre
    STACK_ID=$(aws cloudformation describe-stacks --stack-name "$STACK" --query 'Stacks[0].StackId' --output text)
    aws cloudformation delete-stack --stack-name "$STACK"
    aws cloudformation wait stack-delete-complete --stack-name "$STACK"
    aws cloudformation describe-stack-events --stack-name "$STACK_ID" > evidencias/cierre-eventos.json
    python3 scripts/verify_lab.py closed
    printf 'CLEANUP_OK\n'
    ;;
  *) printf 'Fase invalida\n' >&2; exit 2 ;;
esac
