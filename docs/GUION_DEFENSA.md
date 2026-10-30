# Guion de diez diapositivas

Tiempo total: 600 segundos. Martín: 285 s. Benjamín: 315 s.

Usar notas del presentador con explicación y límites; no leer tablas completas.

## 1 ShopFast implementado en AWS

**Martín · 45 s · Visual: Resultado y negocio**

Presentar el recomendador real y el paso de EC2 a servicios administrados. Separar metas del caso de lo medido. Mostrar modelo v20260921-052859 y la demo, sin token.

## 2 Contexto y objetivos del caso

**Martín · 55 s · Visual: 01_contexto**

Comprador, comercio externo, recomendador y equipo. Metas: 100.000 usuarios/mes, 50.000 productos, pico 10.000, p95 <200 ms, 99,5%, conversión 1,5→3,5%; todas como objetivos sin afirmar su cumplimiento.

## 3 Arquitectura de servicios

**Martín · 65 s · Visual: 02_contenedores**

API FastAPI/ECS, SQS, Lambda, DynamoDB, ECR y S3. Justificar Fargate frente a EC2 y EKS. Exportador SQLite implementado; entrenamiento separado y pendiente.

## 4 Inferencia ALS y componentes

**Martín · 60 s · Visual: 03_componentes**

32 factores, 22.434 usuarios y 7.656 productos. Caché por réplica y fallback. Precision/Recall/MAP offline previos; no convertirlos en conversión comercial.

## 5 Eventos e idempotencia

**Martín · 60 s · Visual: 04_eventos**

UUID por evento, 202 tras SQS, consumo asíncrono y PutItem condicional. Dos POST, un registro lógico. ReportBatchItemFailures, DLQ y exportador con corte temporal.

## 6 Despliegue real en dos AZ

**Benjamín · 70 s · Visual: 05_despliegue**

HTTPS API Gateway → VPC Link → ALB interno → ECS privado. 2 × 0,5 vCPU/1 GiB, NAT por AZ. Escalado 2–4 configurado, no provocado. Demo con cierre programado.

## 7 Seguridad y observabilidad

**Benjamín · 60 s · Visual: Tabla o diagrama breve**

401 sin token, Secrets Manager, SG, cifrado, logs y CloudWatch. 5 alarmas propias y 2 de escalado. Notificación ALARM controlada por SNS→SQS. LabRole amplio por Academy; no es mínimo privilegio productivo.

## 8 Costos oficiales de AWS

**Benjamín · 55 s · Visual: Dos barras y principales partidas**

2 tareas: USD 140,37/mes; 4: USD 176,41/mes. 730 h, mismo tráfico, dos NAT y dos EIP. Reserva dashboard +USD 3 y contingencia 20% →172,04/215,29. No son gasto de la práctica.

## 9 Pruebas y recuperación medidas

**Benjamín · 75 s · Visual: Tabla comparativa y evidencias**

Primera carga: p95 92,84/145,38 ms, cero errores. Segunda: 71,13/101,73 ms con 0/2 errores. Diagnóstico: 115,04 ms, 499×200 y 1×429. ECS 72,82 s; rollback 263 s, mismo modelo; PITR 251,13 s más espera hasta 552,08 s total. 46 tests locales.

## 10 Balance técnico y próximos pasos

**Benjamín · 55 s · Visual: Tres grupos Implementado Probado Pendiente**

Implementado: HA configurada, eventos, observabilidad, exportador. Probado: salud, carga breve, reposición, rollback de fuente y copia PITR. Pendiente: 10.000 usuarios, SLA mensual, login compradores, histórico/reentrenamiento y OIDC. Incluir declaración IA y fuentes APA.