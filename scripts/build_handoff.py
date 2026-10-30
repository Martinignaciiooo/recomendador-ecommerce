"""Arma la entrega para Claude y evidencias publicables sin tokens ni cuentas."""
import csv,hashlib,json,re,shutil,zipfile
from pathlib import Path
from docx import Document

ROOT=Path(__file__).resolve().parents[1]; E=ROOT/'evidencias'; N=E/'segunda-ejecucion'
OUT=ROOT.parent/'Entrega_AWS_ShopFast_Claude'
load=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
live=load(N/'autocierre.json')
for d in ['01_Informe','02_Pricing_AWS','03_Para_Claude','04_Diagramas','05_Evidencias/primera_ejecucion','05_Evidencias/segunda_ejecucion','06_Codigo','07_Acceso_demo']:(OUT/d).mkdir(parents=True,exist_ok=True)
def write(relative,text):
 p=OUT/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')
raw_stack=(N/'stack-operativo.json').read_text(encoding='utf-8') if (N/'stack-operativo.json').exists() else ''
match=re.search(r'arn:aws:cloudformation:[^:]+:(\d{12}):stack/',raw_stack)
account=match.group(1) if match else ''
def redact(text):
 if not account:return text
 dashed='-'.join([account[:4],account[4:8],account[8:]])
 return text.replace(account,'CUENTA_AWS_OCULTA').replace(dashed,'CUENTA_AWS_OCULTA')

report=ROOT/'entregables/EP2_Informe_ShopFast_Actualizado.docx'
shutil.copy2(report,OUT/'01_Informe'/report.name)
pdf=ROOT/'qa/informe-actualizado/EP2_Informe_ShopFast_Actualizado.pdf'
if pdf.exists():shutil.copy2(pdf,OUT/'01_Informe'/pdf.name)
shutil.copy2(ROOT/'docs/COSTOS.md',OUT/'02_Pricing_AWS/COSTOS_AWS.md')
for p in E.glob('calculator-*'):
 if p.is_file():shutil.copy2(p,OUT/'02_Pricing_AWS'/p.name)
for p in (E/'capturas').glob('calculator-*'):shutil.copy2(p,OUT/'02_Pricing_AWS'/p.name)
for p in (ROOT/'diagrams').iterdir():
 if p.suffix in ['.png','.svg','.drawio','.json']:shutil.copy2(p,OUT/'04_Diagramas'/p.name)

first=['carga-5.json','carga-20.json','funcional.json','eventos-idempotencia.json','recuperacion.json','rollback-tiempo.json','rollback.json','model-s3.json','pitr.json','notificacion-sns-recibida.json','compatibilidad-entrenamiento.json','eventos-entrenamiento.manifest.json','cierre-verificado.json','pruebas-locales.json','validacion-desde-windows.json']
second=['carga-5.json','carga-20.json','carga-diagnostico-20.json','funcional.json','eventos-idempotencia.json','notificacion-sns-recibida.json','autocierre.json','cloudwatch-metricas.json']
public=ROOT/'docs/evidencias-aws'
for origin,group,names in [(E,'primera_ejecucion',first),(N,'segunda_ejecucion',second)]:
 for name in names:
  p=origin/name
  if p.exists():
   text=redact(p.read_text(encoding='utf-8-sig'));write('05_Evidencias/'+group+'/'+name,text)
   dst=public/group/name;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_text(text,encoding='utf-8')
for origin,group,name in [(E,'primera_ejecucion','captura.json'),(N,'segunda_ejecucion','infraestructura.json')]:
 x=load(origin/name)
 result={k:x[k] for k in ['stack_status','running','desired','assign_public_ip']}
 result['tasks']=[{k:t[k] for k in ['az','status','health']} for t in x['tasks']]
 result['healthy_targets']=sum(t['state']=='healthy' for t in x['targets'])
 result['note']='Resumen derivado del inventario real; se omiten identificadores de cuenta y red.'
 text=json.dumps(result,indent=2,ensure_ascii=False)
 write('05_Evidencias/'+group+'/infraestructura-resumen.json',text)
 (public/group/'infraestructura-resumen.json').write_text(text,encoding='utf-8')

measurements=[]
for group,origin in [('primera',E),('segunda',N)]:
 for name in ['carga-5.json','carga-20.json']+(['carga-diagnostico-20.json'] if group=='segunda' else []):
  value=load(origin/name);measurements.append(dict(ejecucion=group,archivo=name,**value))
facts={'demo':live,'tests_locales':{'originales':27,'ep2':11,'exportador':4,'autocierre':4,'total':46},
 'cargas':measurements,'recuperacion_ecs':load(E/'recuperacion.json'),
 'rollback_configuracion':load(E/'rollback-tiempo.json'),'restauracion_pitr':load(E/'pitr.json'),
 'pricing':load(E/'calculator-enlaces.json'),
 'limites':['Sin validacion de 10000 usuarios ni disponibilidad mensual','Percentiles solo de HTTP 200 y desde us-east-1',
 'Dos fallos iniciales de la segunda ejecucion sin codigo registrado; no se asume su causa',
 'Repeticion instrumentada: 499 HTTP 200 y 1 HTTP 429','Rollback del mismo modelo entre S3 y la imagen',
 'PITR sin redireccion de trafico','Sin reentrenamiento nuevo ni despliegue GitHub OIDC']}
write('03_Para_Claude/METRICAS_VERIFICADAS.json',redact(json.dumps(facts,indent=2,ensure_ascii=False)))
ci_path=ROOT/'docs/evidencias-aws/github-ci.json'
if ci_path.exists():
 facts['github_ci']=load(ci_path)
 write('03_Para_Claude/METRICAS_VERIFICADAS.json',redact(json.dumps(facts,indent=2,ensure_ascii=False)))
 (OUT/'08_GitHub').mkdir(exist_ok=True)
 shutil.copy2(ci_path,OUT/'08_GitHub/CI_GITHUB.json')
with (OUT/'03_Para_Claude/CARGAS_COMPARADAS.csv').open('w',encoding='utf-8-sig',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=['ejecucion','archivo','requests','concurrency','p95_ms','p99_ms','throughput_rps','errors','http_status_counts'],extrasaction='ignore');writer.writeheader();writer.writerows(measurements)

document=Document(report)
parts=['# Contexto completo de ShopFast para preparar el PPT','Fecha de corte: 30 de octubre de 2026. Fuente principal: informe actualizado y JSON de ejecución.','## Informe técnico actualizado']
for node in document.element.body:
 if node.tag.endswith('}p'):
  text=''.join(node.itertext())
  # itertext duplica texto de runs en algunas versiones; usar Paragraph.
  from docx.text.paragraph import Paragraph
  text=Paragraph(node,document).text
  if text.strip():parts.append(text)
 elif node.tag.endswith('}tbl'):
  from docx.table import Table
  t=Table(node,document)
  for i,row in enumerate(t.rows):
   parts.append('| '+' | '.join(c.text.replace('\n',' / ') for c in row.cells)+' |')
   if i==0:parts.append('| '+' | '.join('---' for _ in row.cells)+' |')
parts.extend(['''
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
'''])
write('03_Para_Claude/CONTEXTO_COMPLETO.md','\n\n'.join(parts))

slides=[
 ('ShopFast implementado en AWS',45,'Martín','Resultado y negocio','Presentar el recomendador real y el paso de EC2 a servicios administrados. Separar metas del caso de lo medido. Mostrar modelo v20260921-052859 y la demo, sin token.'),
 ('Contexto y objetivos del caso',55,'Martín','01_contexto','Comprador, comercio externo, recomendador y equipo. Metas: 100.000 usuarios/mes, 50.000 productos, pico 10.000, p95 <200 ms, 99,5%, conversión 1,5→3,5%; todas como objetivos sin afirmar su cumplimiento.'),
 ('Arquitectura de servicios',65,'Martín','02_contenedores','API FastAPI/ECS, SQS, Lambda, DynamoDB, ECR y S3. Justificar Fargate frente a EC2 y EKS. Exportador SQLite implementado; entrenamiento separado y pendiente.'),
 ('Inferencia ALS y componentes',60,'Martín','03_componentes','32 factores, 22.434 usuarios y 7.656 productos. Caché por réplica y fallback. Precision/Recall/MAP offline previos; no convertirlos en conversión comercial.'),
 ('Eventos e idempotencia',60,'Martín','04_eventos','UUID por evento, 202 tras SQS, consumo asíncrono y PutItem condicional. Dos POST, un registro lógico. ReportBatchItemFailures, DLQ y exportador con corte temporal.'),
 ('Despliegue real en dos AZ',70,'Benjamín','05_despliegue','HTTPS API Gateway → VPC Link → ALB interno → ECS privado. 2 × 0,5 vCPU/1 GiB, NAT por AZ. Escalado 2–4 configurado, no provocado. Demo con cierre programado.'),
 ('Seguridad y observabilidad',60,'Benjamín','Tabla o diagrama breve','401 sin token, Secrets Manager, SG, cifrado, logs y CloudWatch. 5 alarmas propias y 2 de escalado. Notificación ALARM controlada por SNS→SQS. LabRole amplio por Academy; no es mínimo privilegio productivo.'),
 ('Costos oficiales de AWS',55,'Benjamín','Dos barras y principales partidas','2 tareas: USD 140,37/mes; 4: USD 176,41/mes. 730 h, mismo tráfico, dos NAT y dos EIP. Reserva dashboard +USD 3 y contingencia 20% →172,04/215,29. No son gasto de la práctica.'),
 ('Pruebas y recuperación medidas',75,'Benjamín','Tabla comparativa y evidencias','Primera carga: p95 92,84/145,38 ms, cero errores. Segunda: 71,13/101,73 ms con 0/2 errores. Diagnóstico: 115,04 ms, 499×200 y 1×429. ECS 72,82 s; rollback 263 s, mismo modelo; PITR 251,13 s más espera hasta 552,08 s total. 46 tests locales.'),
 ('Balance técnico y próximos pasos',55,'Benjamín','Tres grupos Implementado Probado Pendiente','Implementado: HA configurada, eventos, observabilidad, exportador. Probado: salud, carga breve, reposición, rollback de fuente y copia PITR. Pendiente: 10.000 usuarios, SLA mensual, login compradores, histórico/reentrenamiento y OIDC. Incluir declaración IA y fuentes APA.')]
lines=['# Guion de diez diapositivas','Tiempo total: 600 segundos. Martín: 285 s. Benjamín: 315 s.','Usar notas del presentador con explicación y límites; no leer tablas completas.']
for i,(title,seconds,person,visual,notes) in enumerate(slides,1):
 lines += [f'## {i} {title}',f'**{person} · {seconds} s · Visual: {visual}**',notes]
write('03_Para_Claude/GUION_10_DIAPOSITIVAS.md','\n\n'.join(lines))
write('03_Para_Claude/PROMPT_PARA_CLAUDE.md','''# Prompt para crear la presentación completa

Actúa como diseñador de presentaciones técnicas y prepara el PPTX final y su PDF para la Evaluación Parcial 2 de ITY1102. Usa los archivos adjuntos de ShopFast; el informe actualizado y los JSON tienen prioridad sobre cualquier propuesta histórica. Los autores son Martín Peña y Benjamín Yantzen. No inventes número de equipo, datos, capturas, entrenamiento o pruebas no ejecutadas.

Genera diez diapositivas 16:9 y notas del presentador para una defensa de exactamente diez minutos, siguiendo GUION_10_DIAPOSITIVAS.md. Distribuye las primeras cinco entre Martín y las últimas cinco en Benjamín. Mantén las fuentes, los matices y las cifras del contexto completo.

Incluye cinco diagramas: contexto, contenedores, componentes, eventos y despliegue. Recréales con formas nativas editables o SVG legible a partir de 04_Diagramas. Usa títulos de 30–36 pt, cuerpo 22–26 pt y etiquetas de diagramas al menos 18 pt. Si una imagen queda demasiado pequeña, simplifica su representación sin cambiar servicios ni flujos. No pegues páginas enteras del Word como diapositivas.

Usa diseño sobrio con fondo claro, azul oscuro y acentos AWS discretos. Cada lámina debe tener una conclusión concreta, pocas líneas y un visual útil. Incluye una comparación gráfica del pricing de 2/4 réplicas y una tabla breve de pruebas. Deja el detalle técnico en las notas.

Obligatorio: diferenciar primera ejecución cerrada de segunda demo temporal; HTTPS termina en API Gateway y el ALB es interno; LabRole es una restricción del lab; la alerta SNS se forzó para probar el canal; los percentiles son desde CloudShell y solo de respuestas 200; las dos solicitudes fallidas de la segunda carga original no tienen código conservado; la repetición sí mostró 499 HTTP 200 y un 429; rollback usó el mismo modelo; PITR restauró una tabla nueva sin cambiar tráfico; no hubo reentrenamiento nuevo, A/B, prueba de 10.000 usuarios ni SLA mensual validado. El exportador DynamoDB→SQLite sí está implementado y probado.

Los USD 140,37/176,41 son escenarios mensuales de 730 h y tráfico constante. No son el consumo real del laboratorio. Los USD 172,04/215,29 de planeación incluyen USD 3 de reserva de dashboard y 20% de contingencia. Conserva los exports originales y explica los defaults no seleccionados de NAT regional si se pregunta.

Incluye al menos dos fuentes técnicas oficiales en APA y una declaración breve de uso de IA. La última lámina debe distinguir implementado, probado y pendiente. Añade enlaces de referencia en notas y un vínculo a la demo con su expiración; nunca incluyas tokens, claves AWS ni valores de Secrets Manager.

Antes de finalizar, verifica que todos los números coincidan con METRICAS_VERIFICADAS.json, que la duración sume 600 s y que ningún diagrama muestre ALB público con ACM como si fuera el despliegue real. Entrega PPTX editable y PDF listos para presentar.
''')
write('07_Acceso_demo/ACCESO_Y_CIERRE.md',f'''# Acceso a la demo

- Dashboard: {live['dashboard_url']}
- Salud pública: {live['api_url']}/health/ready
- Swagger: {live['api_url']}/docs
- Cierre programado: {live['close_santiago']} (America/Santiago); {live['close_utc']} UTC.

El dashboard es administrativo y requiere el token del proyecto. Entra por AWS Academy → curso 186191 → Learner Lab → AWS → Secrets Manager. Identifica el secreto del stack shopfast-ep2-lab mediante su Output SecretArn y copia solo su campo token al panel. No pegues el valor en Claude, GitHub, capturas ni diapositivas. Esta entrega no contiene credenciales.

La ruta de salud permite comprobar el modelo sin token. El mensaje del panel sin autenticación no sustituye esa comprobación. Al vencer el plazo, la Lambda de cierre solicita eliminar exclusivamente el ARN de este stack. Conserva S3, ECR, tablas y logs con costo residual. La EC2 anterior queda fuera de ese cierre.

Para detener antes, usar scripts/lab.sh cleanup en la sesión del laboratorio, con SHOPFAST_EXPECTED_ACCOUNT_ID configurada. Para repetir, usar el README del código y un directorio nuevo. No ejecutar bootstrap sobre un servicio que ya existe.
''')
write('00_LEEME.md',f'''# Entrega de ShopFast para revisar y preparar el PPT

1. Abre 01_Informe: Word actualizado de diez páginas y copia PDF.
2. Revisa 02_Pricing_AWS: exports originales PDF/CSV/JSON y explicación de supuestos.
3. En Claude adjunta el Word, 03_Para_Claude, 04_Diagramas y las evidencias que necesites. Pega el contenido de PROMPT_PARA_CLAUDE.md. CONTEXTO_COMPLETO.md y GUION_10_DIAPOSITIVAS.md permiten preparar la defensa completa.
4. 05_Evidencias separa las dos ejecuciones y oculta la cuenta AWS en los JSON compartibles. Los originales privados permanecen en el computador.
5. 06_Codigo contiene el ZIP de fuentes para CloudShell. 07_Acceso_demo explica la autenticación y el cierre; no contiene tokens.

Demo: {live['dashboard_url']}

Cierre programado: {live['close_santiago']} (hora de Santiago). La URL deja de responder tras retirar el stack.

El objetivo de esta entrega es permitir a Claude construir el PPT sin adivinar arquitectura, resultados ni limitaciones. Los 46 tests son locales. CI y publicación se verifican en el estado de GitHub; OIDC y reentrenamiento completo permanecen pendientes.
''')
manifest={str(p.relative_to(OUT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.rglob('*') if p.is_file() and p.name!='MANIFEST_SHA256.json'}
write('MANIFEST_SHA256.json',json.dumps(manifest,indent=2,ensure_ascii=False))
print(OUT)
