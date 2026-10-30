# Estimación y AWS Pricing Calculator

## Cotizaciones oficiales guardadas el 30-10-2026

Región `us-east-1`, Linux x86, On-Demand y 730 horas/mes. Las cotizaciones corresponden a la variante con API Gateway HTTPS, ALB interno y dos NAT zonales. Los PDF, CSV y JSON originales están en `evidencias/calculator-2-replicas.*` y `evidencias/calculator-4-replicas.*`, junto con las capturas y `calculator-enlaces.json`.

| Escenario mensual | Calculator USD/mes | Reserva dashboard sin asumir cuota gratuita | Total de planeación con 20% de contingencia |
|---|---:|---:|---:|
| 2 tareas, cada una de 0,5 vCPU / 1 GiB | 140,37 | 3,00 | 172,04 |
| 4 tareas, cada una de 0,5 vCPU / 1 GiB | 176,41 | 3,00 | 215,29 |

- [Estimación oficial de dos réplicas](https://calculator.aws/#/estimate?id=d074410aa269b21da99d9eafcd24f1cc0ed57403).
- [Estimación oficial de cuatro réplicas](https://calculator.aws/#/estimate?id=a2fb204d857b4367caabf1e3cf0d5c047a32e92b).

Solo se duplica el cómputo al comparar dos y cuatro tareas; se mantiene el resto de los supuestos. No representa el costo de duplicar todo el tráfico. La exportación de cada formato genera otra instantánea con otro enlace; sus costos coinciden con los enlaces anteriores. Los montos no incluyen impuestos y pueden cambiar con las tarifas o el uso real.

| Servicio | Supuesto de dos réplicas | USD/mes |
|---|---|---:|
| Fargate | 2 tareas de 0,5 vCPU / 1 GiB, 730 h | 36,04 |
| NAT | 2 gateways zonales, 730 h y procesamiento de datos estimado | 65,78 |
| IPv4 públicas | 2 EIP de NAT; ALB interno sin IPv4 pública | 7,30 |
| ALB | 730 h y 1 LCU media supuesta | 22,27 |
| HTTP API Gateway | 2 millones de solicitudes/mes de 1 KB | 2,00 |
| DynamoDB y PITR | 1 GB, 1 millón de escrituras, 0,1 millón de lecturas y PITR de 1 GB | 1,09 |
| Lambda | 1 millón de invocaciones, 256 MB, 100 ms, sin Free Tier | 0,62 |
| SQS | 3,5 millones de operaciones, incluidos envío, consumo, borrado y polling | 1,40 |
| S3 | 5 GB, 1.000 escrituras y 10.000 lecturas | 0,12 |
| ECR | 1 GB de imágenes privadas | 0,10 |
| CloudWatch | 1 GB de logs, 7 alarmas y 1 dashboard | 1,20 |
| Secrets Manager | 1 secreto y 1.000 llamadas | 0,41 |
| SNS | 1.000 publicaciones y entrega SQS; valor redondeado | 0,00 |
| Entrenamiento Fargate | Hipótesis: 4 trabajos/mes de 2 vCPU / 4 GiB, 30 min cada uno | 0,20 |
| Transferencia | 20 GB a Internet y 2 GB entre AZ | 1,84 |
| **Total cotizado** | | **140,37** |

Calculator aplica automáticamente la cuota gratuita al dashboard en esta configuración. Para planear sin depender de ella se añaden USD 3 al total antes de aplicar 20% de contingencia. No se modificaron los archivos oficiales para hacer ese ajuste.

El exportador de Calculator muestra valores por defecto de NAT regional (5 y 3 AZ) en `Properties`, aunque ese tipo no se seleccionó. La cotización de NAT de USD 65,78 corresponde a **dos NAT zonales** y la plantilla ejecutada contiene exactamente dos `AWS::EC2::NatGateway`. Esos campos por defecto no representan recursos desplegados ni cinco NAT adicionales facturados.

El entrenamiento de USD 0,20 es únicamente una hipótesis para cotizar. No se ejecutó entrenamiento nuevo: falta el dataset histórico. Las duraciones de Lambda, LCU y volumen mensual son supuestos que deben revisarse con tráfico sostenido; las cargas breves de esta práctica no los demuestran.

## Créditos y estado de las dos ejecuciones

La primera ejecución se retiró y verificó. La segunda demo está activa temporalmente en https://s1a1vms9gh.execute-api.us-east-1.amazonaws.com/dashboard con cierre programado el 30-10-2026 a las 03:55 de Santiago (06:55 UTC). La regla temporal EventBridge/Lambda no representa un servicio mensual permanente; las cotizaciones comparan la aplicación encendida 730 horas sin ese cierre. Sus JSON están separados en docs/evidencias-aws.

Academy mostraba inicialmente USD 10,20 usados de un total de USD 50, con actualización diferida de 8–12 horas. Se adoptó un margen operativo de USD 5 para ejecutar y cerrar esta sesión; no es un límite técnico impuesto por AWS ni una cifra ya facturada. Las cotizaciones mensuales anteriores no son el gasto real de la práctica.

Después de probar y respaldar, se eliminó solamente `shopfast-ep2-lab` y se comprobó que no quedaron sus NAT, EIP, ALB ni ECS activos (`evidencias/cierre-verificado.json`). Se conservaron S3, ECR, DynamoDB, la copia de prueba PITR y logs con costo de almacenamiento residual. Los recursos de proyectos anteriores quedaron fuera del cierre. El costo final atribuible debe contrastarse cuando se actualice la facturación de Academy; no se deduce del saldo inicial ni de una estimación mensual.

## Referencia anterior: propuesta con ALB público y dominio

La siguiente estimación manual se preparó el 29-10-2026, antes del despliegue, para la plantilla original `infra/shopfast.json`. Incluye cuatro IPv4 públicas y una reserva genérica. Se conserva como referencia histórica y no corresponde al diseño Academy ni a las exportaciones oficiales anteriores.

| Partida | Supuesto | USD/mes |
|---|---|---:|
| ECS Fargate | 2 tareas × (0,5 vCPU × 0,04048 + 1 GB × 0,004445) × 730 h | 36,04 |
| ALB fijo | 0,0225 USD/h × 730 h | 16,43 |
| ALB uso | Supuesto 1 LCU medio × 0,008 USD/h × 730 h | 5,84 |
| NAT Gateway | 2 × 0,045 USD/h × 730 h | 65,70 |
| IPv4 públicas | 2 del ALB + 2 EIP NAT, 4 × 0,005 USD/h × 730 h | 14,60 |
| Subtotal de cómputo y red | Suma anterior sin redondear | 138,61 |
| Reserva de planeación | S3, ECR, DynamoDB, PITR, Lambda, SQS, CloudWatch, SNS, Secrets Manager, transferencia, procesamiento NAT y entrenamiento | 30,00 |
| Estimación preliminar base | Subtotal + reserva, no cotización cerrada | 168,61 |
| Contingencia 20% | Sobre estimación base | 33,72 |
| Presupuesto de planeación | Base + contingencia | 202,33 |

La reserva de USD 30 es un supuesto, NO el precio de servicios ya cotizados. Dos réplicas adicionales todo el mes añadirían aproximadamente USD 36,04 de Fargate, sin el aumento variable de otros servicios. Una prueba de 6 h con 2 réplicas supone unos USD 1,14 de los mismos componentes base, más consumo, secretos y recursos retenidos; no es un tope de cobro. El bootstrap ya crea los 2 NAT (USD 0,09/h más 2 IPv4 y datos) aunque aún no exista servicio.

Para Calculator, ingresar y exportar al menos:

- ECS Fargate Linux x86, 2 tareas de 0,5 vCPU y 1 GB, 730 h. Añadir escenario 4 tareas.
- ALB 730 h y estimación de LCU basada en conexiones, bytes, reglas y conexiones activas. No asumir que 1 LCU soporta el pico del caso.
- Dos NAT Gateway, 730 h, y GB procesados medidos o asumidos.
- Cuatro IPv4 públicas. No contabilizarlas dos veces si la calculadora las incorpora en otro servicio.
- S3 5 GB iniciales de modelos/versiones, peticiones; ECR 1 GB de imagen.
- DynamoDB On-Demand: escenario 1 millón escrituras de eventos de <=1 KB/mes, 1 GB almacenado, PITR. Ajustar al tráfico del equipo.
- Lambda: 1 millón eventos/mes agrupados hasta 10, 256 MB, duración asumida 100 ms por invocación; validar duración y lote real.
- SQS: enviar, recibir y borrar mensajes, long polling del servicio Lambda, reintentos y DLQ. No igualar mensajes a requests facturadas sin considerar batching.
- CloudWatch 1 GB de logs ingeridos/mes, retención 14 días, 5 alarmas y dashboard. Confirmar cargos y cuotas gratuitas.
- Secrets Manager 1 secreto, SNS email, transferencia de salida e inter-AZ y procesamiento NAT.
- Entrenamiento: escenario inicial 4 trabajos/mes, 2 vCPU/4 GB y 30 min/trabajo. Es una hipótesis de planeación; el entrenamiento completo requiere events.csv ausente y medición antes de cotizar un tipo concreto.

Guardar el link compartible, PDF/CSV de la estimación y captura con región y fecha en `evidencias/`. Actualizar el informe con el resultado real. No contratar Savings Plans ni instancias reservadas para esta práctica.

## Fuentes oficiales

- AWS Fargate: https://aws.amazon.com/fargate/pricing/
- Comparación oficial de cómputo: https://aws.amazon.com/blogs/aws-cloud-financial-management/a-finops-guide-to-comparing-containers-and-serverless-functions-for-compute/
- Elastic Load Balancing: https://aws.amazon.com/elasticloadbalancing/pricing/
- VPC, NAT e IPv4: https://aws.amazon.com/vpc/pricing/
- AWS Pricing Calculator: https://calculator.aws/
