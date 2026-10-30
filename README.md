# Recomendador e-commerce EP2 en AWS

Continuación del repositorio real `Martinignaciiooo/recomendador-ecommerce`, base commit `1cc9149b7e7a0b0c2bc0f55e35e904c956e08067`, revisado el 29 de octubre de 2026. Se conserva el modelo ALS, núcleo de inferencia, endpoints en español, entrenamiento y dashboard. `README_ORIGINAL.md` conserva el estado anterior.

## AWS ejecutado en Learner Lab — 30 de octubre de 2026

**Demo reactivada:** [dashboard](https://s1a1vms9gh.execute-api.us-east-1.amazonaws.com/dashboard), [salud pública](https://s1a1vms9gh.execute-api.us-east-1.amazonaws.com/health/ready) y [Swagger](https://s1a1vms9gh.execute-api.us-east-1.amazonaws.com/docs). El panel administrativo necesita el token de Secrets Manager. La segunda demo tiene cierre programado el **30-10-2026 a las 03:55, hora de Santiago** (06:55 UTC). Después de esa hora el enlace puede dejar de responder.

El informe actualizado de diez páginas está en `entregables/EP2_Informe_ShopFast_Actualizado.docx`. Las evidencias publicables de ambas ejecuciones están en `docs/evidencias-aws/`; se oculta la cuenta AWS.

La segunda ejecución repitió funcionalidad, dos AZ, eventos y alertas. Carga 100/5: p95 71,13 ms, cero errores. Carga 500/20: p95 101,73 ms, dos fallos sin código registrado. Una repetición instrumentada registró p95 115,04 ms, 499 HTTP 200 y un HTTP 429. Se conservaron los resultados iniciales y no se atribuye retrospectivamente la causa de esos dos fallos. El throttling sigue configurado en 200 solicitudes/s y ráfaga 100.

Se desplegó y probó `shopfast-ep2-lab` en el curso 186191, región `us-east-1`. Como no había dominio, la variante `infra/shopfast-learner-lab.json` usa **HTTPS de API Gateway → VPC Link → ALB interno → dos tareas ECS privadas, en dos AZ**. Usa el `LabRole` existente por las restricciones de Academy. La plantilla original `infra/shopfast.json` conserva la propuesta con dominio, ACM y ALB TLS.

Los resultados medidos están en `evidencias/`; las capturas, en `evidencias/capturas/`. No contienen el token de la API ni credenciales AWS.

| Verificación real | Resultado | Evidencia |
|---|---|---|
| Docker Linux amd64, modelo real | Construcción y smoke correctos | `docker-smoke.json`, `build.log` |
| HTTPS, autorización y recomendación | Health 200, sin token 401, modelo y fallback correctos | `funcional.json`, `post-rollback.json` |
| ECS y ALB | 2 tareas saludables, IP pública deshabilitada, 2 AZ y 2 targets saludables | `captura.json` |
| Eventos idempotentes | Dos envíos con el mismo UUID, un registro lógico en DynamoDB | `eventos-idempotencia.json` |
| Carga breve desde CloudShell | 100 solicitudes/5 hilos: p95 92,84 ms; 500/20: p95 145,38 ms; cero errores | `carga-5.json`, `carga-20.json` |
| Reposición de una tarea | 72,82 s; 70 consultas observadas y cero errores | `recuperacion.json` |
| Modelo desde S3 y rollback | Mismo modelo cargado desde S3; regreso al modelo incluido en 263 s | `model-s3.json`, `rollback-tiempo.json` |
| Restauración DynamoDB PITR | Copia restaurada en 251,13 s, evento comprobado; 552,08 s incluyendo espera del punto recuperable | `pitr.json` |
| Logs, métricas y alertas | Logs de API/Lambda; alarma ALARM controlada recibida por SNS → SQS | `logs-api.json`, `logs-worker.json`, `cloudwatch-metricas.json`, `notificacion-sns-recibida.json` |
| Exportación para entrenamiento | 2 eventos reales exportados a SQLite; manifiesto con corte temporal y hash | `eventos-entrenamiento.manifest.json` |

El punto PITR observado tenía aproximadamente 300 segundos de retraso. La prueba restauró una **tabla nueva** y comprobó el dato; no redirigió tráfico ni midió la recuperación completa de la aplicación. El rollback cambió la fuente del artefacto de S3 a la imagen; utilizó los mismos pesos y versión, no dos modelos entrenados distintos.

Las cargas fueron ráfagas cortas dentro de `us-east-1`. No demuestran 10.000 usuarios concurrentes, disponibilidad mensual ni latencia p95 desde Chile. La comprobación HTTPS independiente desde Windows obtuvo health 200 y rechazos 401, con unos 532 ms para el health; incluye una conexión TLS nueva y no es un percentil de recomendaciones (`validacion-desde-windows.json`).

Para conservar créditos se retiró el primer stack tras las pruebas. La comprobación está en `cierre-verificado.json`: sin sus NAT, EIP, ALB ni clúster ECS activos. Su URL dejó de estar disponible. Después se recreó la demo con la nueva URL y el cierre programado indicados al principio. Se conservaron modelos S3, imagen ECR, tabla de eventos, copia PITR y logs del primer ensayo; tienen costo residual. La EC2 y los stacks anteriores quedaron fuera del despliegue.

Las cotizaciones oficiales mensuales son **USD 140,37 con dos réplicas** y **USD 176,41 con cuatro**; son escenarios de 730 horas, no el gasto de esta sesión. Ver `docs/COSTOS.md` y los PDF/CSV/JSON originales de Calculator. El saldo inicial de Academy indicaba USD 10,20 usados de USD 50; su actualización tiene retraso y no permite atribuir todavía el cobro final a esta práctica.

### Repetir la demostración

Subir `shopfast-aws-lab.zip` a CloudShell del curso 186191 y extraerlo. El script comprueba la cuenta antes de cambiar recursos. Trabajar desde el paquete recién extraído para conservar las evidencias de esta ejecución.

```bash
SHOPFAST_RUN_DIR="$HOME/shopfast-demo-$(date +%Y%m%d-%H%M%S)"
unzip ~/shopfast-aws-lab.zip -d "$SHOPFAST_RUN_DIR"
cd "$SHOPFAST_RUN_DIR/shopfast-aws-lab"
export SHOPFAST_EXPECTED_ACCOUNT_ID="REEMPLAZAR_CON_CUENTA_DEL_LABORATORIO"
bash scripts/lab.sh preflight
bash scripts/lab.sh build
bash scripts/lab.sh bootstrap
bash scripts/lab.sh service
bash scripts/lab.sh verify
bash scripts/lab.sh recovery
bash scripts/lab.sh model-s3
bash scripts/lab.sh rollback
python3 scripts/test_pitr_lab.py
# Respaldar evidencias antes de cerrar.
bash scripts/lab.sh cleanup
```

`bootstrap` inicia cobros de NAT; `cleanup` retira solamente el stack nuevo y conserva datos e imágenes. El nombre fijo de stack permite identificar su alcance. Las ejecuciones nuevas generan nombres físicos distintos para los recursos retenidos. No ejecutar otro despliegue y pruebas simultáneamente sobre el mismo stack. Para consultar la demo autenticada, usar el token solo desde Secrets Manager dentro de la sesión de laboratorio; no incluirlo en capturas, repositorio ni entregables.

## Qué quedó preparado

- Modelo real incluido: `v20260921-052859`, 32 factores, 22.434 usuarios y 7.656 productos.
- API original adaptada: token obligatorio fuera de desarrollo explícito, comparación segura, health check 503 si no está lista y métricas protegidas.
- `POST /eventos` ahora requiere `Idempotency-Key` UUID y retorna 202. Informa aceptación de evento, no procesamiento terminado.
- Backend de eventos SQS en AWS y SQLite local. Worker Lambda con escritura condicional idempotente en DynamoDB, DLQ y reintentos parciales.
- `Dockerfile.ep2`: imagen con el modelo real y solo dependencias de inferencia. El entrenamiento queda fuera de la API.
- CloudFormation con ECS Fargate, 2 réplicas privadas en dos AZ, ALB TLS, escalado 2-4, 2 NAT, ECR, S3, DynamoDB PITR, SQS/DLQ, Secrets Manager, alarmas y dashboard CloudWatch, SNS y presupuesto.
- Flujo CI con pruebas, validación CloudFormation y smoke Docker. Despliegue manual por GitHub Actions con OIDC, pendiente de configurar en su cuenta.
- 5 diagramas editables Draw.io, informe técnico de 10 páginas, presentación y guion.

**CI en GitHub aprobada:** [ejecución 41010837858](https://github.com/Martinignaciiooo/recomendador-ecommerce/actions/runs/41010837858) validó las pruebas, las dos plantillas, build y smoke Docker de la revisión 5314dc0. El job de deploy OIDC se omitió.

**Estado de validación local:** 27 pruebas originales adaptadas, 11 EP2, 4 del exportador y 4 del cierre seguro: **46 en total**. CloudFormation pasa cfn-lint. Docker y AWS se ejecutaron en CloudShell. La ejecución de CI se comprueba en GitHub Actions; el despliegue GitHub OIDC no está configurado ni se ejecutó. Las métricas offline son previas y no se reentrenó sin el histórico. La EC2 anterior no se modificó.

## Empieza aquí

Leer `docs/GUIA_AWS.md`, `docs/COSTOS.md` y `docs/EVIDENCIAS.md`. El bootstrap crea NAT con cobro continuo. El presupuesto solo alerta. No aplicar en producción existente.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
$env:PYTHONPATH='src'
$env:OPENBLAS_NUM_THREADS='1'
pytest src/tests_reco.py -q
$env:PYTHONPATH='src;.'
pytest tests/test_ep2.py -q
pytest tests/test_export_events_lab.py -q
pytest tests/test_autoclose.py -q
cfn-lint infra/shopfast.json
cfn-lint infra/shopfast-learner-lab.json
```

Las suites se ejecutan en procesos separados porque la original prueba modo anónimo local y la de EP2 prueba modo autenticado. No establecer `RECO_ALLOW_ANONYMOUS=1` en AWS.

## Ejecución local real

```powershell
$env:PYTHONPATH='src'
$env:RECO_API_TOKEN='REEMPLAZAR_CON_48_CARACTERES_ALEATORIOS'
$env:EVENTS_BACKEND='sqlite'
$env:EVENTS_DB="$PWD/eventos-local.db"
python -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Abrir `/dashboard` e ingresar el token solo en esta consola de administración para la demostración. No incrustarlo en Shopify ni en JavaScript distribuido a clientes. El backend de la tienda debe autenticar la sesión del comprador y limitar qué usuario consulta. Esa integración de identidad no está incluida en este repositorio.

## Despliegue y actualización del modelo

La ruta más simple es `Mode=bundled`: se incluye el modelo real del repositorio en la imagen ECR. Todas las réplicas de la misma revisión ejecutan ese artefacto. La versión S3 opcional utiliza un tar.gz con exactamente `factors.npz` y `meta.json`:

```powershell
python scripts/package_model.py
aws s3 cp model.tar.gz s3://BUCKET_REAL/models/v20260921-052859.tar.gz --region us-east-1
```

Reaplicar el servicio con `Mode=s3` y esa clave inmutable. El proceso descarga en `/tmp` al arrancar, no en cada request. Para rollback, restaurar ImageTag/ModelKey anteriores. No sobrescribir la clave activa. S3 y ECR conservan versiones.

`scripts/export_events_lab.py` conecta DynamoDB con el formato SQLite que lee `src/prepare_data.py::load_api_events`. Exige un corte temporal con zona horaria, limita el escaneo, conserva identificadores enteros y rechaza UUID duplicados con contenido distinto. DynamoDB Scan no proporciona un snapshot entre páginas: usar una copia PITR estable o detener escrituras durante la exportación. Ejemplo, con valores reales de otra ejecución:

```bash
python3 scripts/export_events_lab.py --table TABLA_PITR_ESTABLE \
  --before 2026-10-30T03:52:58+00:00 --output eventos-entrenamiento.db
```

El exportador no reemplaza archivos existentes ni entrena o promociona un modelo. Falta el dataset histórico `data/events.csv` para ejecutar entrenamiento y evaluación completos; los dos eventos sintéticos de esta práctica solo comprueban el enlace de datos.

## Seguridad y límites explícitos

En la variante Academy, TLS termina en API Gateway y los tramos VPC Link-ALB-API usan HTTP en la red privada, restringidos por security groups. La plantilla original termina TLS en ALB. El contenedor corre sin root y necesita `/tmp` escribible para S3. Cifrado de los tramos internos, WAF y restricción fina de egress quedan como endurecimiento de producción. El bucket retenido conserva la política que exige HTTPS.

El token autentica a un servicio backend o a un administrador de la demo, no a cada comprador. No existe login de clientes ni rotación automática. API Gateway tiene throttling de 200 solicitudes/s con ráfaga 100 como protección de práctica; es un límite de mejor esfuerzo. La caché y las métricas de la aplicación son por réplica; CloudWatch agrega infraestructura y balanceador. Los logs de aplicación no incluyen tokens, user_id, cuerpo ni query. `LabRole` tiene permisos amplios del laboratorio; una implantación productiva requiere roles separados y mínimos. La alerta se verificó mediante una cola SQS suscrita a SNS, sin suscribir un correo.

El escalado de 2 a 4 tareas por CPU es una configuración inicial de práctica. No demuestra capacidad para 10.000 usuarios concurrentes. Las interacciones no cambian los factores en caliente; la caché local se invalida, pero la personalización cambia al reentrenar. Falta confirmar el caso EP1 correcto y la plantilla arc42 extendida del AVA antes de entregar el informe.
