param(
 [Parameter(Mandatory=$true)][string]$Email,
 [string]$Region='us-east-1',
 [string]$Stack='shopfast-ep2',
 [string]$CertificateArn='',
 [ValidateSet('bootstrap','service')][string]$Phase='bootstrap',
 [string]$ImageTag='',
 [ValidateSet('bundled','s3')][string]$Mode='bundled',
 [string]$ModelKey=''
)
$ErrorActionPreference='Stop'
Set-Location (Join-Path $PSScriptRoot '..')
function Check-Exit {if ($LASTEXITCODE -ne 0) {throw 'El comando fallo. Revisa el error antes de continuar.'}}
aws sts get-caller-identity --region $Region; Check-Exit
aws cloudformation validate-template --template-body file://infra/shopfast.json --region $Region | Out-Null; Check-Exit
if ($Phase -eq 'bootstrap') {
 Write-Host 'AVISO: bootstrap crea 2 NAT Gateway con cobro por hora. El presupuesto NO detiene cobros.'
 $parameters=@("NotifyEmail=$Email","PracticeBudget=30")
} else {
 if (!$CertificateArn -or !$ImageTag) {throw 'service requiere CertificateArn emitido en esta region e ImageTag nuevo.'}
 if ($Mode -eq 's3' -and !$ModelKey.StartsWith('models/')) {throw 'Mode s3 requiere ModelKey bajo models/.'}
 $repo=aws cloudformation describe-stacks --stack-name $Stack --region $Region --query "Stacks[0].Outputs[?OutputKey=='RepositoryUri'].OutputValue | [0]" --output text; Check-Exit
 $registry=$repo.Split('/')[0]
 aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin $registry; Check-Exit
 docker build -f Dockerfile.ep2 --platform linux/amd64 -t "${repo}:$ImageTag" .; Check-Exit
 docker push "${repo}:$ImageTag"; Check-Exit
 $parameters=@("NotifyEmail=$Email","PracticeBudget=30","ImageTag=$ImageTag","CertificateArn=$CertificateArn","Mode=$Mode","ModelKey=$ModelKey")
}
aws cloudformation deploy --stack-name $Stack --template-file infra/shopfast.json --capabilities CAPABILITY_IAM --parameter-overrides $parameters --region $Region --no-fail-on-empty-changeset; Check-Exit
aws cloudformation describe-stacks --stack-name $Stack --region $Region --query 'Stacks[0].Outputs' --output table; Check-Exit
