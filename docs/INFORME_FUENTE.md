# Contexto completo de ShopFast para preparar el PPT

Fecha de corte: 30 de octubre de 2026. Fuente principal: informe actualizado y JSON de ejecución.

## Informe técnico actualizado

Implementación y validación de ShopFast en AWS

Evaluación Parcial 2 de ITY1102

Martín Peña y Benjamín Yantzen  ·  30 de octubre de 2026

1 Introducción y objetivos

Implementamos y validamos la evolución del recomendador ALS desde el prototipo EC2 con Docker hacia servicios administrados en AWS. La API FastAPI se ejecutó en dos tareas privadas de ECS Fargate, con balanceo y persistencia asíncrona de interacciones. Conservamos el modelo real y separamos inferencia, consumo de eventos y preparación de datos.

La primera ejecución incluyó carga, reposición de tareas, modelo desde S3, rollback y restauración PITR. Después de respaldar se retiró ese stack. Una segunda ejecución dejó disponible la demo solicitada y volvió a comprobar salud, autorización, topología, eventos y alertas. Se programó su cierre para conservar créditos.

| Metas del caso de estudio | Alcance de la validación |

| --- | --- |

| 100.000 usuarios/mes y 50.000 productos | Metas de dimensionamiento; el modelo incluido tiene 22.434 usuarios y 7.656 productos. |

| Pico de 10.000 usuarios concurrentes | No demostrado; se ensayaron 5 y 20 hilos con carga breve. |

| Latencia inferior a 200 ms y disponibilidad 99,5% | Objetivos; las ráfagas no constituyen una medición mensual ni una garantía por Internet. |

| Conversión de 1,5% a 3,5% y USD 3.000/mes | Objetivo comercial y límite del caso; no resultados de conversión ni gasto autorizado para el laboratorio. |

2 Restricciones y alcance

Se utilizó AWS Academy Learner Lab 186191 en us-east-1, con USD 50 de créditos totales y gasto de práctica acotado. Al no existir dominio propio, HTTPS se resolvió con API Gateway y un VPC Link hacia un ALB interno. Las restricciones IAM se atendieron con el LabRole existente; la propuesta con dominio y ACM se conserva como una plantilla distinta.

Demo administrada de ShopFast

Cierre programado de la segunda ejecución: 2026-10-30T03:55:00-03:00 (America/Santiago). El dashboard solicita el token del laboratorio; las credenciales no forman parte de los entregables.

3 Contexto e interfaces

Figura 1  Contexto C4 del recomendador y sus actores

El backend del comercio conserva la sesión del comprador y consulta recomendaciones para el usuario autorizado. El token de servicio autentica al backend o al administrador de la demo; no implementa el login del comprador. El panel técnico permite explorar el modelo y registrar interacciones de prueba.

| Interfaz | Contrato verificado |

| --- | --- |

| GET /recomendaciones | user_id como texto y k entre 1 y 50; devuelve modelo, caché o fallback. Bearer obligatorio. |

| POST /eventos | view, cart o purchase; Idempotency-Key UUID. HTTP 202 después de aceptación en SQS. |

| GET /health/ready | HTTP 200 con modelo listo; 503 si no puede servir. Acceso de salud sin token. |

| GET /metricas y /modelo | Datos protegidos con Bearer. Las métricas de aplicación corresponden a la réplica atendida. |

La integración con Shopify debe enviar el UUID idempotente y distinguir aceptación del evento de persistencia y entrenamiento. Los identificadores se transportan como texto para evitar pérdida de precisión en JavaScript.

4 Estrategia y vista de contenedores

Figura 2  API, consumidor, persistencia y preparación de datos

Servicios independientes y eventos

La API resuelve el camino interactivo con el modelo cargado en memoria. SQS desacopla las interacciones de la escritura durable. Lambda consume los mensajes y DynamoDB evita efectos duplicados mediante una condición sobre event_id. API y consumidor pueden desplegarse y escalar por separado.

ECS Fargate reduce la operación de servidores y evita gestionar Kubernetes para un equipo de dos integrantes. ALB distribuye tráfico entre tareas y ECR conserva una imagen inmutable. S3 almacena el mismo modelo como alternativa externa. EKS, GPU y SageMaker no fueron necesarios para servir los factores actuales.

Preparación de datos y límites del entrenamiento

El exportador conecta DynamoDB con el esquema SQLite que ya lee prepare_data.py. Se ejecutó una exportación de dos eventos y se comprobó su lectura con pandas, conservando IDs int64 y fechas UTC. El pipeline de entrenamiento y promoción queda separado: no se ejecutó un entrenamiento nuevo porque falta el histórico events.csv.

5 Componentes y dimensionamiento

Figura 3  Componentes de FastAPI y adaptadores de infraestructura

core.py calcula puntuaciones ALS y excluye artículos vistos usando la matriz dispersa. La caché LRU tiene bloqueo de acceso y permanece local a cada réplica. Un usuario desconocido activa el fallback de popularidad. Los eventos no cambian los factores en tiempo real ni invalidan globalmente la caché.

| Recurso | Configuración o resultado |

| --- | --- |

| API | 2 tareas, cada una de 0,5 vCPU y 1 GiB; escalado configurado de 2 a 4 a CPU 60%. |

| Modelo real | v20260921-052859; 32 factores; 22.434 usuarios, 7.656 productos y 70.142 interacciones. |

| Memoria de factores | 3.851.520 bytes float32; a 100.000 usuarios y 50.000 productos serían 19,2 MB solo de factores. |

| Artefactos | factors.npz y meta.json; carga NPZ sin pickle. S3 se consulta al arrancar, no por solicitud. |

| Entrenamiento estimado | Hipótesis de 2 vCPU, 4 GiB y 30 min semanales; duración no medida en esta práctica. |

La evaluación offline previa del repositorio usó 1.087 usuarios y un corte temporal de enero de 2021. ALS obtuvo Precision@10 0,0220, Recall@10 0,0818 y MAP@10 0,0368, frente a 0,0125, 0,0441 y 0,0239 de popularidad. No se recalcularon estas métricas ni se probó un aumento de conversión.

8 Seguridad y observabilidad

| Control | Implementación y comprobación |

| --- | --- |

| Autenticación | Token inyectado desde Secrets Manager. Sin token se comprobó 401; con token, modelo y fallback correctos. |

| Transporte | TLS termina en API Gateway. VPC Link-ALB-API usa HTTP privado, con SG que limita origen y puertos 80/8000. |

| Aislamiento | Dos tareas sin IP pública y en AZ distintas. ALB interno. NAT por AZ para salida a servicios AWS. |

| Identidad | LabRole existente para tareas y Lambda. Es una concesión del laboratorio, no una demostración de mínimo privilegio productivo. |

| Datos y secretos | Cifrado de servicios AWS, versionado de S3, PITR y TTL de eventos. El bucket retenido conserva bloqueo público y exigencia de HTTPS. |

| Throttling | HTTP API configurada con 200 solicitudes/s y ráfaga 100; límite de mejor esfuerzo, no capacidad demostrada de Fargate. |

| Logs | Logs de API y consumidor guardados en CloudWatch; retención 14 días. No se incluyen valores de secretos en las evidencias. |

| Métricas | CPU, memoria, p95 del backend ALB, errores y cola. La latencia ALB no incorpora el recorrido de red del cliente. |

| Alarmas y canal | 5 alarmas propias y 2 de escalado. Una transición ALARM controlada se recibió por SNS en una cola SQS cifrada. |

Controles que requieren evolución productiva

Faltan login y autorización por comprador, roles IAM separados, WAF, cifrado de los tramos internos y rotación automática con reemplazo de tareas. El token del dashboard no debe incrustarse en un frontend público. Las métricas y la caché por réplica requieren interpretarse por instancia.

La recepción SNS validó la integración del canal de alertas mediante una alarma forzada. No demuestra que la carga haya activado un umbral de producción ni se suscribió una dirección de correo. El despliegue automático por GitHub OIDC requiere un rol de confianza específico y no quedó habilitado en el laboratorio.

6 Ejecución e idempotencia de eventos

Figura 4  Flujo asíncrono e idempotencia con SQS y DynamoDB

El cliente conserva un UUID por evento lógico y lo reutiliza al reintentar. La API valida la estructura y devuelve 202 tras publicar en SQS. El consumidor realiza PutItem condicional por event_id. En la prueba se enviaron dos POST con el mismo UUID y se verificó un único registro lógico persistido.

SQS Standard ofrece entrega al menos una vez. El worker usa respuestas parciales ReportBatchItemFailures para reintentar únicamente los mensajes fallidos. La DLQ recibe mensajes que superan cinco recepciones. Esta configuración y los reintentos se cubrieron con pruebas locales; no se ejecutó una campaña de agotamiento de DLQ sobre la demo.

Exportación reproducible

export_events_lab.py exige un corte temporal con zona horaria, impone un máximo de lectura, deduplica por UUID, rechaza conflictos y produce un manifiesto con SHA256. No sobrescribe archivos existentes. La salida de dos eventos se abrió con load_api_events, con fechas UTC e identificadores enteros sin pérdida de precisión.

Scan no proporciona un snapshot entre páginas. Para una exportación estable debe usarse una tabla sin escrituras o una copia PITR. El exportador no entrena, evalúa ni promociona un modelo; esas operaciones necesitan el histórico y una comparación offline posterior.

Dimensionamiento económico en AWS

Las cotizaciones oficiales se guardaron el 30-10-2026 para us-east-1, Linux x86 On-Demand y 730 horas mensuales. El ALB es interno: se cotizan dos IPv4 para NAT y HTTP API para HTTPS. Los archivos PDF, CSV y JSON originales se entregan por separado.

| Componente y supuesto mensual | USD con 2 tareas |

| --- | --- |

| Fargate 2 × 0,5 vCPU / 1 GiB | 36,04 |

| Dos NAT zonales y procesamiento supuesto | 65,78 |

| Dos IPv4 de NAT | 7,30 |

| ALB y 1 LCU media supuesta | 22,27 |

| HTTP API con 2 millones de solicitudes | 2,00 |

| DynamoDB 1 GB, 1 M escrituras, 0,1 M lecturas y PITR | 1,09 |

| Lambda 1 M invocaciones, 256 MB, 100 ms | 0,62 |

| SQS 3,5 M operaciones | 1,40 |

| S3 5 GB y operaciones | 0,12 |

| ECR 1 GB | 0,10 |

| CloudWatch 1 GB logs, 7 alarmas y dashboard | 1,20 |

| Secrets Manager y SNS redondeado | 0,41 |

| Hipótesis de 4 entrenamientos mensuales | 0,20 |

| Transferencia 20 GB Internet y 2 GB inter-AZ | 1,84 |

| Total oficial de Calculator | 140,37 |

| Escenario | Calculator | Planeación con reserva y 20% |

| --- | --- | --- |

| 2 tareas todo el mes | USD 140,37 | USD 172,04 |

| 4 tareas todo el mes | USD 176,41 | USD 215,29 |

Para comparar cuatro tareas se mantiene fijo el resto del tráfico. Calculator aplica una cuota gratuita al dashboard: la planeación añade USD 3 antes de la contingencia. Los defaults regionales 5/3 que aparecen en Properties de NAT no son recursos desplegados ni cargos adicionales; la plantilla contiene dos NAT zonales.

Estos montos no son el gasto de la sesión. El saldo inicial de Academy mostraba USD 10,20 usados de USD 50, con retraso de actualización. El primer stack se retiró y la segunda demo tiene cierre programado. Datos, imágenes, tablas y logs retenidos conservan costo de almacenamiento. No se contrataron reservas ni Savings Plans.

7 Despliegue y alta disponibilidad

Figura 5  Despliegue real con HTTPS de API Gateway y ALB interno

CloudFormation creó la red y los servicios; Docker se construyó y probó en CloudShell, y la imagen se publicó en ECR. Se comprobaron dos tareas RUNNING y HEALTHY, dos destinos saludables y ubicación en us-east-1a y us-east-1b, sin IP pública en las tareas.

El servicio mantiene dos réplicas y tiene escalado configurado hasta cuatro por CPU. La reposición de una tarea se ensayó; no se simuló una caída completa de AZ ni se observó un escalado por carga. El modelo se cargó también desde S3 y después se volvió al incluido en la imagen.

La demo nueva se cierra mediante EventBridge y una Lambda vinculada al ARN exacto del stack. Verifica etiquetas de práctica y plazo UTC antes de solicitar DeleteStack. Su invocación de prueba no borra recursos. El cierre conserva los recursos con Retain y la EC2 anterior queda fuera del alcance.

9 Decisiones y 10 Validación de calidad

| Ejecución y ensayo | p95 o tiempo | Fallos observados |

| --- | --- | --- |

| Primera: 100 solicitudes, 5 hilos | 92,84 ms | 0 |

| Primera: 500 solicitudes, 20 hilos | 145,38 ms | 0 |

| Segunda: 100 solicitudes, 5 hilos | 71,13 ms | 0 |

| Segunda: 500 solicitudes, 20 hilos | 101,73 ms | 2 |

| Repetición instrumentada: 500, 20 hilos | 115,04 ms | 1 |

| Reposición ECS, primera ejecución | 72,82 s | 0 en 70 consultas |

| Rollback S3 a imagen, mismo modelo | 263 s | Salud comprobada |

| Restauración de tabla PITR | 251,13 s | Evento recuperado |

Las ráfagas se midieron desde CloudShell en us-east-1 y los percentiles incluyen solo respuestas HTTP 200. En la segunda ejecución inicial hubo dos fallos de 500 intentos; la herramienta aún no registraba sus códigos. Se añadió el desglose de estados y se conservó la medición original. La repetición registró {"200": 499, "429": 1}. No se atribuyen retrospectivamente los dos fallos a una causa que no quedó registrada.

La reposición de 72,82 s satisfizo el objetivo de 120 s en ese ensayo. El rollback de 263 s cambió la fuente del mismo artefacto, no los pesos del modelo. PITR tardó 552,08 s incluyendo espera del punto recuperable, cuyo retraso observado fue aproximadamente 300 s. Se restauró una tabla nueva y se verificó el evento, sin redirigir el tráfico ni medir recuperación completa de la aplicación.

Desde Windows se verificaron TLS estricto, health 200 y rechazos 401. El health tardó unos 532 ms con una conexión TLS nueva; no es un percentil de recomendaciones ni demuestra el objetivo desde Chile. La disponibilidad mensual 99,5% y 10.000 usuarios concurrentes siguen sin validación.

Pruebas locales: 27 originales adaptadas, 11 EP2, 4 del exportador y 4 del cierre seguro, 46 aprobadas. CloudFormation pasó cfn-lint. La imagen Linux amd64 pasó build y smoke en CloudShell. El estado de GitHub Actions debe comprobarse en la ejecución de CI; el despliegue OIDC no se ejecutó.

11 Riesgos y decisiones pendientes

Se eligió API Gateway con VPC Link por ausencia de dominio y se mantuvo un ALB privado. En producción deben revisarse cuotas, throttling, roles mínimos y costo fijo de NAT frente al tráfico real. Para 10.000 usuarios se necesita diseñar comportamiento, generadores distribuidos, carga sostenida y margen ante pérdida de una AZ.

El histórico events.csv es necesario para reentrenar y comparar nuevas métricas. La integración de eventos ya entrega SQLite compatible, pero no constituye una automatización completa de entrenamiento. El cambio de versión debe incluir evaluación, promoción y una prueba de rollback entre modelos distintos.

Antes de la entrega académica corresponde confirmar el número de equipo, las cifras definitivas del caso EP1 y el formato arc42 del AVA. La defensa de hasta diez minutos debe distinguir objetivos, configuración y medición; el material para Claude incluye un guion y las evidencias originales.

12 Glosario

AZ: zona de disponibilidad. RPO: pérdida temporal de datos tolerable. RTO: tiempo objetivo de recuperación. DLQ: cola de mensajes que agotaron reintentos. Idempotencia: repetir un evento no duplica su efecto. LCU: unidad de capacidad del ALB. VPC Link: conexión privada de API Gateway al balanceador.

Referencias técnicas en formato APA

Amazon Web Services. (s. f.). Amazon ECS services.

Amazon Web Services. (s. f.). Handling errors for an SQS event source in Lambda.

Amazon Web Services. (s. f.). Setting a schedule pattern for scheduled rules in Amazon EventBridge.

Amazon Web Services. (2026). ShopFast EP2 2 réplicas y 4 réplicas [Estimaciones de AWS Pricing Calculator].

Peña, M., y Yantzen, B. (2026). Recomendador e-commerce [Repositorio de software, base 1cc9149].

Documentación técnica consultada el 30 de octubre de 2026. Los JSON y los archivos de Calculator permiten rastrear cifras, fechas y alcance de cada ensayo.

Declaración de uso de inteligencia artificial

Se utilizó ChatGPT/Codex para revisar y adaptar código, preparar y ejecutar pruebas y despliegues en el laboratorio autorizado, generar diagramas y actualizar documentación. El equipo debe revisar los entregables y asumir la responsabilidad técnica de su defensa. Claude se utilizará para componer la presentación a partir del contexto y de las evidencias suministradas.


## Guía de lectura y reglas para la presentación

La implementación es un recomendador backend con un dashboard de administración. No se publicó una tienda Shopify ni un login de compradores. El comercio externo conserva su sesión y usa la API desde un backend autorizado.

El dashboard exige un Bearer token de Secrets Manager. La salud es pública; usuarios, recomendaciones, modelo y métricas están protegidos. No poner el token en enlaces, diapositivas, capturas, archivos para Claude ni GitHub. Sin token el panel puede indicar falta de conexión por los 401; esa indicación no implica que la API de salud esté caída.

Hay dos ejecuciones y sus métricas no deben mezclarse. La primera terminó con retirada comprobada de NAT/EIP/ALB/ECS; dejó S3, ECR, DynamoDB y logs retenidos. La segunda recreó el stack y está programada para retirarse en la fecha que figura en autocierre.json. Las URLs caducan con el cierre.

El rollback cambió Mode=s3 a Mode=bundled manteniendo v20260921-052859. No demuestra dos modelos entrenados distintos ni una promoción de precisión. PITR restauró una tabla nueva y verificó un evento; no cambió el consumidor ni midió recuperación global de la aplicación. Su retraso observado fue 300,002493 s, aproximadamente cinco minutos, no una garantía estricta de RPO.

La prueba inicial de la segunda ejecución contó dos fallos de 500 sin conservar códigos. La repetición instrumentada sí registró 499 estados 200 y un 429, consistente con la protección de tasa configurada. No adjudicar esos dos fallos anteriores automáticamente a throttling. Conservar las mediciones originales.

El throughput de la herramienta cuenta intentos por segundo; con fallos no equivale a throughput de éxito. El p95 excluye fallos. Una ráfaga de 1–2 s desde CloudShell no valida capacidad sostenida, latencia de usuarios en Chile, pérdida de una AZ ni 99,5% de disponibilidad mensual. Desde Windows el health tardó unos 532 ms con TLS nuevo.

Los resultados offline de ALS proceden del modelo entrenado previamente, con 1.087 usuarios evaluados y corte temporal de enero de 2021. No son nuevos resultados de entrenamiento en AWS. No hay experimento A/B ni aumento de conversión medido.

El exportador DynamoDB→SQLite está implementado y ejecutado con dos eventos. Hace falta el histórico events.csv para entrenar y evaluar de nuevo. No inventar un job semanal ejecutado: los USD 0,20 mensuales de entrenamiento son una hipótesis de cotización.

## Razonamiento que debe explicarse en la defensa

- Fargate reduce la administración de servidores respecto a EC2 y la complejidad de EKS para un equipo pequeño. Docker empaqueta; ECS y el ALB mantienen réplicas y balanceo.
- La API conserva inferencia síncrona; SQS y Lambda desacoplan la persistencia, aceptando consistencia eventual.
- SQS entrega al menos una vez. El UUID y PutItem condicional aseguran un efecto lógico idempotente. ReportBatchItemFailures evita reintentar los mensajes que sí se procesaron.
- API Gateway resuelve HTTPS sin un dominio del equipo. TLS termina allí; los saltos de VPC Link y ALB a la API son HTTP dentro de la red privada con security groups.
- Cada AZ tiene NAT para salida. El ALB es interno, las tareas no tienen IP pública. Dos AZ configuradas y observadas no equivalen a un ensayo de caída completa de AZ.
- LabRole es una adaptación a permisos de Academy. La propuesta productiva usa roles separados; no presentar el rol amplio del lab como mínimo privilegio demostrado.
- El caché y las métricas de aplicación son por réplica; la invalidez de un usuario no se distribuye automáticamente. Los eventos no cambian los factores ALS en línea.
- ECR y las claves S3 preservan artefactos inmutables. El entrenamiento se separa de la API y la carga de modelos ocurre al arrancar.
- Calculator cotiza 730 h/mes. USD 140,37 y 176,41 no son el consumo de la sesión. El dashboard incluye una cuota gratuita en Calculator; la planeación suma USD 3 y luego 20%.
- La exportación oficial de VPC incluye defaults de NAT regional 5/3 aunque no se seleccionaron: la plantilla y el costo corresponden a dos NAT zonales. No modificar los exports para ocultarlo.

## Preguntas probables y respuestas breves

¿Por qué no GPU? Los factores de 32 dimensiones se sirven con álgebra en CPU; no se midió una necesidad de acelerador. ¿Por qué no EKS? La carga y el equipo no justifican operar Kubernetes en esta práctica.

¿Se alcanzaron 10.000 usuarios? No. Se midieron ráfagas de 5/20 hilos; falta definir frecuencia de consultas y carga sostenida. 10.000 conectados no implican 10.000 requests simultáneos.

¿Qué protege el token? El servicio backend o la consola de administración. No sustituye la sesión de compradores ni controla por sí solo qué usuario puede consultar cada cliente.

¿Qué significa 202? SQS aceptó el mensaje; la persistencia y cualquier entrenamiento ocurren después. El mismo UUID reintentado no duplica el efecto en DynamoDB.

¿Se restauró todo el sistema? No. Se restauró una copia de la tabla, se verificó el evento y no se redirigió tráfico. La reposición ECS y el rollback se midieron por separado.

¿Por qué cierra la demo? Para evitar cargos horarios de NAT, ALB y ECS dentro de créditos limitados. Retener datos e imágenes no equivale a costo cero.

¿Dónde quedó CI/CD? El código contiene pruebas y build/smoke de CI. La ejecución concreta se consulta en GitHub y en el archivo de estado de publicación; el despliegue OIDC a AWS no está configurado ni ejecutado.

## Fuentes y archivos que tienen prioridad

1. Informe actualizado, METRICAS_VERIFICADAS.json y JSON de 05_Evidencias.
2. Exports originales de Calculator, conservados sin alterar, y COSTOS_AWS.md para sus supuestos.
3. Cinco diagramas actualizados en PNG, SVG y Draw.io.
4. Código y README actualizado. README_ORIGINAL.md y la propuesta con ALB público son historia o alternativa, no el despliegue de Academy.

Referencias oficiales: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs_services.html ; https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-errorhandling.html ; https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-scheduled-rule-pattern.html

Repositorio base: https://github.com/Martinignaciiooo/recomendador-ecommerce (1cc9149). El número de equipo y la plantilla extendida del AVA requieren confirmación del equipo; no inventarlos.
