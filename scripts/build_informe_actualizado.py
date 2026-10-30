"""Informe EP2 de diez paginas a partir de evidencias reales, sin credenciales."""
import json
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'evidencias'
N=E/'segunda-ejecucion'
if not (N/'autocierre.json').exists():
 E=ROOT/'docs/evidencias-aws/primera_ejecucion'
 N=ROOT/'docs/evidencias-aws/segunda_ejecucion'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
live=read(N/'autocierre.json')
old5,old20=read(E/'carga-5.json'),read(E/'carga-20.json')
new5,new20=read(N/'carga-5.json'),read(N/'carga-20.json')
diag=read(N/'carga-diagnostico-20.json')
pitr=read(E/'pitr.json'); recovery=read(E/'recuperacion.json')
metrics=read(ROOT/'out/metricas.json')
meta=read(ROOT/'out/models/v20260921-052859/meta.json')

doc=Document()
sec=doc.sections[0]
sec.page_width=Cm(21);sec.page_height=Cm(29.7)
sec.top_margin=Cm(1.7);sec.bottom_margin=Cm(1.7)
sec.left_margin=Cm(1.9);sec.right_margin=Cm(1.9)
for name in ['Normal','Title','Subtitle','Heading 1','Heading 2','Caption']:
 st=doc.styles[name];st.font.name='Calibri';st.font.color.rgb=RGBColor(0,0,0)
 st.paragraph_format.space_after=Pt(6)
doc.styles['Normal'].font.size=Pt(10.5)
doc.styles['Normal'].paragraph_format.line_spacing=1.08
doc.styles['Title'].font.size=Pt(25)
doc.styles['Subtitle'].font.size=Pt(12)
doc.styles['Heading 1'].font.size=Pt(15)
doc.styles['Heading 1'].paragraph_format.space_before=Pt(8)
doc.styles['Heading 2'].font.size=Pt(11.5)
doc.styles['Heading 2'].paragraph_format.space_before=Pt(5)
doc.styles['Caption'].font.size=Pt(9)
# El estilo Title de Word puede heredar un borde azul del tema.
for border in list(doc.styles.element.xpath('.//w:pBdr')):
 border.getparent().remove(border)
doc.core_properties.title='Implementación y validación de ShopFast en AWS'
doc.core_properties.author='Martín Peña y Benjamín Yantzen'
doc.core_properties.subject='Evaluación Parcial 2 ITY1102'

def p(text,style=None):return doc.add_paragraph(text,style)
def h(text,level=1):doc.add_heading(text,level)
def page():doc.add_page_break()
def money(v):return f'{v:,.2f}'.replace(',','_').replace('.',',').replace('_','.')
def table(headers,rows,widths=None):
 t=doc.add_table(rows=1,cols=len(headers));t.alignment=WD_TABLE_ALIGNMENT.CENTER
 t.autofit=False
 if widths is None:widths=[17.2/len(headers)]*len(headers)
 for col,w in zip(t.columns,widths):col.width=Cm(w)
 for i,text in enumerate(headers):t.rows[0].cells[i].text=str(text)
 for row in rows:
  cells=t.add_row().cells
  for cell,text in zip(cells,row):cell.text=str(text)
 for ri,row in enumerate(t.rows):
  trPr=row._tr.get_or_add_trPr()
  if ri==0:
   repeat=OxmlElement('w:tblHeader');trPr.append(repeat)
  cant=OxmlElement('w:cantSplit');trPr.append(cant)
  for ci,cell in enumerate(row.cells):
   cell.width=Cm(widths[ci]);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
   tcPr=cell._tc.get_or_add_tcPr()
   sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'243E56' if ri==0 else ('F1F5F8' if ri%2 else 'FFFFFF'));tcPr.append(sh)
   borders=OxmlElement('w:tcBorders')
   for edge in ['top','left','bottom','right']:
    b=OxmlElement('w:'+edge);b.set(qn('w:val'),'single');b.set(qn('w:sz'),'4');b.set(qn('w:color'),'D9D9D9');borders.append(b)
   tcPr.append(borders)
   margins=OxmlElement('w:tcMar')
   for side,value in [('top','65'),('bottom','65'),('left','85'),('right','85')]:
    m=OxmlElement('w:'+side);m.set(qn('w:w'),value);m.set(qn('w:type'),'dxa');margins.append(m)
   tcPr.append(margins)
   for para in cell.paragraphs:
    para.paragraph_format.space_after=Pt(2);para.paragraph_format.space_before=Pt(1);para.paragraph_format.line_spacing=1.02
    if ci>0 and len(str(cell.text))<28:para.alignment=WD_ALIGN_PARAGRAPH.CENTER
    for run in para.runs:
     run.font.size=Pt(9.3);run.bold=ri==0;run.font.color.rgb=RGBColor.from_string('FFFFFF' if ri==0 else '000000')
 p('')
 return t
def figure(slug,caption,width=6.55):
 para=doc.add_paragraph();para.alignment=WD_ALIGN_PARAGRAPH.CENTER
 para.paragraph_format.keep_with_next=True
 pic=para.add_run().add_picture(str(ROOT/'diagrams'/f'{slug}.png'),width=Inches(width))
 pic._inline.docPr.set('descr',caption)
 p(caption,'Caption')
def link(text,url):
 para=doc.add_paragraph()
 rel=para.part.relate_to(url,'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink',is_external=True)
 el=OxmlElement('w:hyperlink');el.set(qn('r:id'),rel)
 run=OxmlElement('w:r');txt=OxmlElement('w:t');txt.text=text;run.append(txt);el.append(run);para._p.append(el)
 return para

# Numeracion de paginas para comprobar el limite de la pauta.
foot=sec.footer.paragraphs[0];foot.alignment=WD_ALIGN_PARAGRAPH.RIGHT
foot.add_run('ShopFast  |  ITY1102  |  ')
field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');foot._p.append(field)
for r in foot.runs:r.font.size=Pt(8)

p('Implementación y validación de ShopFast en AWS','Title')
p('Evaluación Parcial 2 de ITY1102','Subtitle')
p('Martín Peña y Benjamín Yantzen  ·  30 de octubre de 2026')
h('1 Introducción y objetivos')
p('Implementamos y validamos la evolución del recomendador ALS desde el prototipo EC2 con Docker hacia servicios administrados en AWS. La API FastAPI se ejecutó en dos tareas privadas de ECS Fargate, con balanceo y persistencia asíncrona de interacciones. Conservamos el modelo real y separamos inferencia, consumo de eventos y preparación de datos.')
p('La primera ejecución incluyó carga, reposición de tareas, modelo desde S3, rollback y restauración PITR. Después de respaldar se retiró ese stack. Una segunda ejecución dejó disponible la demo solicitada y volvió a comprobar salud, autorización, topología, eventos y alertas. Se programó su cierre para conservar créditos.')
table(['Metas del caso de estudio','Alcance de la validación'],[
 ('100.000 usuarios/mes y 50.000 productos','Metas de dimensionamiento; el modelo incluido tiene 22.434 usuarios y 7.656 productos.'),
 ('Pico de 10.000 usuarios concurrentes','No demostrado; se ensayaron 5 y 20 hilos con carga breve.'),
 ('Latencia inferior a 200 ms y disponibilidad 99,5%','Objetivos; las ráfagas no constituyen una medición mensual ni una garantía por Internet.'),
 ('Conversión de 1,5% a 3,5% y USD 3.000/mes','Objetivo comercial y límite del caso; no resultados de conversión ni gasto autorizado para el laboratorio.')],[6,11.2])
h('2 Restricciones y alcance')
p('Se utilizó AWS Academy Learner Lab 186191 en us-east-1, con USD 50 de créditos totales y gasto de práctica acotado. Al no existir dominio propio, HTTPS se resolvió con API Gateway y un VPC Link hacia un ALB interno. Las restricciones IAM se atendieron con el LabRole existente; la propuesta con dominio y ACM se conserva como una plantilla distinta.')
link('Demo administrada de ShopFast',live['dashboard_url'])
p('Cierre programado de la segunda ejecución: '+live['close_santiago']+' (America/Santiago). El dashboard solicita el token del laboratorio; las credenciales no forman parte de los entregables.')

page();h('3 Contexto e interfaces')
figure('01_contexto','Figura 1  Contexto C4 del recomendador y sus actores')
p('El backend del comercio conserva la sesión del comprador y consulta recomendaciones para el usuario autorizado. El token de servicio autentica al backend o al administrador de la demo; no implementa el login del comprador. El panel técnico permite explorar el modelo y registrar interacciones de prueba.')
table(['Interfaz','Contrato verificado'],[
 ('GET /recomendaciones','user_id como texto y k entre 1 y 50; devuelve modelo, caché o fallback. Bearer obligatorio.'),
 ('POST /eventos','view, cart o purchase; Idempotency-Key UUID. HTTP 202 después de aceptación en SQS.'),
 ('GET /health/ready','HTTP 200 con modelo listo; 503 si no puede servir. Acceso de salud sin token.'),
 ('GET /metricas y /modelo','Datos protegidos con Bearer. Las métricas de aplicación corresponden a la réplica atendida.')],[5.5,11.7])
p('La integración con Shopify debe enviar el UUID idempotente y distinguir aceptación del evento de persistencia y entrenamiento. Los identificadores se transportan como texto para evitar pérdida de precisión en JavaScript.')

page();h('4 Estrategia y vista de contenedores')
figure('02_contenedores','Figura 2  API, consumidor, persistencia y preparación de datos')
h('Servicios independientes y eventos',2)
p('La API resuelve el camino interactivo con el modelo cargado en memoria. SQS desacopla las interacciones de la escritura durable. Lambda consume los mensajes y DynamoDB evita efectos duplicados mediante una condición sobre event_id. API y consumidor pueden desplegarse y escalar por separado.')
p('ECS Fargate reduce la operación de servidores y evita gestionar Kubernetes para un equipo de dos integrantes. ALB distribuye tráfico entre tareas y ECR conserva una imagen inmutable. S3 almacena el mismo modelo como alternativa externa. EKS, GPU y SageMaker no fueron necesarios para servir los factores actuales.')
h('Preparación de datos y límites del entrenamiento',2)
p('El exportador conecta DynamoDB con el esquema SQLite que ya lee prepare_data.py. Se ejecutó una exportación de dos eventos y se comprobó su lectura con pandas, conservando IDs int64 y fechas UTC. El pipeline de entrenamiento y promoción queda separado: no se ejecutó un entrenamiento nuevo porque falta el histórico events.csv.')

page();h('5 Componentes y dimensionamiento')
figure('03_componentes','Figura 3  Componentes de FastAPI y adaptadores de infraestructura')
p('core.py calcula puntuaciones ALS y excluye artículos vistos usando la matriz dispersa. La caché LRU tiene bloqueo de acceso y permanece local a cada réplica. Un usuario desconocido activa el fallback de popularidad. Los eventos no cambian los factores en tiempo real ni invalidan globalmente la caché.')
table(['Recurso','Configuración o resultado'],[
 ('API','2 tareas, cada una de 0,5 vCPU y 1 GiB; escalado configurado de 2 a 4 a CPU 60%.'),
 ('Modelo real','v20260921-052859; 32 factores; 22.434 usuarios, 7.656 productos y 70.142 interacciones.'),
 ('Memoria de factores','3.851.520 bytes float32; a 100.000 usuarios y 50.000 productos serían 19,2 MB solo de factores.'),
 ('Artefactos','factors.npz y meta.json; carga NPZ sin pickle. S3 se consulta al arrancar, no por solicitud.'),
 ('Entrenamiento estimado','Hipótesis de 2 vCPU, 4 GiB y 30 min semanales; duración no medida en esta práctica.')],[4.5,12.7])
p('La evaluación offline previa del repositorio usó 1.087 usuarios y un corte temporal de enero de 2021. ALS obtuvo Precision@10 0,0220, Recall@10 0,0818 y MAP@10 0,0368, frente a 0,0125, 0,0441 y 0,0239 de popularidad. No se recalcularon estas métricas ni se probó un aumento de conversión.')

page();h('8 Seguridad y observabilidad')
table(['Control','Implementación y comprobación'],[
 ('Autenticación','Token inyectado desde Secrets Manager. Sin token se comprobó 401; con token, modelo y fallback correctos.'),
 ('Transporte','TLS termina en API Gateway. VPC Link-ALB-API usa HTTP privado, con SG que limita origen y puertos 80/8000.'),
 ('Aislamiento','Dos tareas sin IP pública y en AZ distintas. ALB interno. NAT por AZ para salida a servicios AWS.'),
 ('Identidad','LabRole existente para tareas y Lambda. Es una concesión del laboratorio, no una demostración de mínimo privilegio productivo.'),
 ('Datos y secretos','Cifrado de servicios AWS, versionado de S3, PITR y TTL de eventos. El bucket retenido conserva bloqueo público y exigencia de HTTPS.'),
 ('Throttling','HTTP API configurada con 200 solicitudes/s y ráfaga 100; límite de mejor esfuerzo, no capacidad demostrada de Fargate.'),
 ('Logs','Logs de API y consumidor guardados en CloudWatch; retención 14 días. No se incluyen valores de secretos en las evidencias.'),
 ('Métricas','CPU, memoria, p95 del backend ALB, errores y cola. La latencia ALB no incorpora el recorrido de red del cliente.'),
 ('Alarmas y canal','5 alarmas propias y 2 de escalado. Una transición ALARM controlada se recibió por SNS en una cola SQS cifrada.')],[4.1,13.1])
h('Controles que requieren evolución productiva',2)
p('Faltan login y autorización por comprador, roles IAM separados, WAF, cifrado de los tramos internos y rotación automática con reemplazo de tareas. El token del dashboard no debe incrustarse en un frontend público. Las métricas y la caché por réplica requieren interpretarse por instancia.')
p('La recepción SNS validó la integración del canal de alertas mediante una alarma forzada. No demuestra que la carga haya activado un umbral de producción ni se suscribió una dirección de correo. El despliegue automático por GitHub OIDC requiere un rol de confianza específico y no quedó habilitado en el laboratorio.')

page();h('6 Ejecución e idempotencia de eventos')
figure('04_eventos','Figura 4  Flujo asíncrono e idempotencia con SQS y DynamoDB')
p('El cliente conserva un UUID por evento lógico y lo reutiliza al reintentar. La API valida la estructura y devuelve 202 tras publicar en SQS. El consumidor realiza PutItem condicional por event_id. En la prueba se enviaron dos POST con el mismo UUID y se verificó un único registro lógico persistido.')
p('SQS Standard ofrece entrega al menos una vez. El worker usa respuestas parciales ReportBatchItemFailures para reintentar únicamente los mensajes fallidos. La DLQ recibe mensajes que superan cinco recepciones. Esta configuración y los reintentos se cubrieron con pruebas locales; no se ejecutó una campaña de agotamiento de DLQ sobre la demo.')
h('Exportación reproducible',2)
p('export_events_lab.py exige un corte temporal con zona horaria, impone un máximo de lectura, deduplica por UUID, rechaza conflictos y produce un manifiesto con SHA256. No sobrescribe archivos existentes. La salida de dos eventos se abrió con load_api_events, con fechas UTC e identificadores enteros sin pérdida de precisión.')
p('Scan no proporciona un snapshot entre páginas. Para una exportación estable debe usarse una tabla sin escrituras o una copia PITR. El exportador no entrena, evalúa ni promociona un modelo; esas operaciones necesitan el histórico y una comparación offline posterior.')

page();h('Dimensionamiento económico en AWS')
p('Las cotizaciones oficiales se guardaron el 30-10-2026 para us-east-1, Linux x86 On-Demand y 730 horas mensuales. El ALB es interno: se cotizan dos IPv4 para NAT y HTTP API para HTTPS. Los archivos PDF, CSV y JSON originales se entregan por separado.')
table(['Componente y supuesto mensual','USD con 2 tareas'],[
 ('Fargate 2 × 0,5 vCPU / 1 GiB', '36,04'),('Dos NAT zonales y procesamiento supuesto','65,78'),('Dos IPv4 de NAT','7,30'),('ALB y 1 LCU media supuesta','22,27'),('HTTP API con 2 millones de solicitudes','2,00'),('DynamoDB 1 GB, 1 M escrituras, 0,1 M lecturas y PITR','1,09'),('Lambda 1 M invocaciones, 256 MB, 100 ms','0,62'),('SQS 3,5 M operaciones','1,40'),('S3 5 GB y operaciones','0,12'),('ECR 1 GB','0,10'),('CloudWatch 1 GB logs, 7 alarmas y dashboard','1,20'),('Secrets Manager y SNS redondeado','0,41'),('Hipótesis de 4 entrenamientos mensuales','0,20'),('Transferencia 20 GB Internet y 2 GB inter-AZ','1,84'),('Total oficial de Calculator','140,37')],[13.5,3.7])
table(['Escenario','Calculator','Planeación con reserva y 20%'],[('2 tareas todo el mes','USD 140,37','USD 172,04'),('4 tareas todo el mes','USD 176,41','USD 215,29')],[6,4,7.2])
p('Para comparar cuatro tareas se mantiene fijo el resto del tráfico. Calculator aplica una cuota gratuita al dashboard: la planeación añade USD 3 antes de la contingencia. Los defaults regionales 5/3 que aparecen en Properties de NAT no son recursos desplegados ni cargos adicionales; la plantilla contiene dos NAT zonales.')
p('Estos montos no son el gasto de la sesión. El saldo inicial de Academy mostraba USD 10,20 usados de USD 50, con retraso de actualización. El primer stack se retiró y la segunda demo tiene cierre programado. Datos, imágenes, tablas y logs retenidos conservan costo de almacenamiento. No se contrataron reservas ni Savings Plans.')

page();h('7 Despliegue y alta disponibilidad')
figure('05_despliegue','Figura 5  Despliegue real con HTTPS de API Gateway y ALB interno',6.25)
p('CloudFormation creó la red y los servicios; Docker se construyó y probó en CloudShell, y la imagen se publicó en ECR. Se comprobaron dos tareas RUNNING y HEALTHY, dos destinos saludables y ubicación en us-east-1a y us-east-1b, sin IP pública en las tareas.')
p('El servicio mantiene dos réplicas y tiene escalado configurado hasta cuatro por CPU. La reposición de una tarea se ensayó; no se simuló una caída completa de AZ ni se observó un escalado por carga. El modelo se cargó también desde S3 y después se volvió al incluido en la imagen.')
p('La demo nueva se cierra mediante EventBridge y una Lambda vinculada al ARN exacto del stack. Verifica etiquetas de práctica y plazo UTC antes de solicitar DeleteStack. Su invocación de prueba no borra recursos. El cierre conserva los recursos con Retain y la EC2 anterior queda fuera del alcance.')

page();h('9 Decisiones y 10 Validación de calidad')
table(['Ejecución y ensayo','p95 o tiempo','Fallos observados'],[
 ('Primera: 100 solicitudes, 5 hilos',money(old5['p95_ms'])+' ms',old5['errors']),
 ('Primera: 500 solicitudes, 20 hilos',money(old20['p95_ms'])+' ms',old20['errors']),
 ('Segunda: 100 solicitudes, 5 hilos',money(new5['p95_ms'])+' ms',new5['errors']),
 ('Segunda: 500 solicitudes, 20 hilos',money(new20['p95_ms'])+' ms',new20['errors']),
 ('Repetición instrumentada: 500, 20 hilos',money(diag['p95_ms'])+' ms',diag['errors']),
 ('Reposición ECS, primera ejecución','72,82 s','0 en 70 consultas'),
 ('Rollback S3 a imagen, mismo modelo','263 s','Salud comprobada'),
 ('Restauración de tabla PITR','251,13 s','Evento recuperado')],[9.2,3.5,4.5])
p('Las ráfagas se midieron desde CloudShell en us-east-1 y los percentiles incluyen solo respuestas HTTP 200. En la segunda ejecución inicial hubo dos fallos de 500 intentos; la herramienta aún no registraba sus códigos. Se añadió el desglose de estados y se conservó la medición original. La repetición registró '+json.dumps(diag['http_status_counts'],ensure_ascii=False)+'. No se atribuyen retrospectivamente los dos fallos a una causa que no quedó registrada.')
p('La reposición de 72,82 s satisfizo el objetivo de 120 s en ese ensayo. El rollback de 263 s cambió la fuente del mismo artefacto, no los pesos del modelo. PITR tardó 552,08 s incluyendo espera del punto recuperable, cuyo retraso observado fue aproximadamente 300 s. Se restauró una tabla nueva y se verificó el evento, sin redirigir el tráfico ni medir recuperación completa de la aplicación.')
p('Desde Windows se verificaron TLS estricto, health 200 y rechazos 401. El health tardó unos 532 ms con una conexión TLS nueva; no es un percentil de recomendaciones ni demuestra el objetivo desde Chile. La disponibilidad mensual 99,5% y 10.000 usuarios concurrentes siguen sin validación.')
p('Pruebas locales: 27 originales adaptadas, 11 EP2, 4 del exportador y 4 del cierre seguro, 46 aprobadas. CloudFormation pasó cfn-lint. La imagen Linux amd64 pasó build y smoke en CloudShell.')
ci_file=ROOT/'docs/evidencias-aws/github-ci.json'
ci=read(ci_file) if ci_file.exists() else {}
if ci.get('conclusion')=='success':
 link('GitHub Actions aprobó pruebas, CloudFormation y Docker para la revisión '+ci['head_sha'][:7],ci['url'])
 p('La ejecución CI registrada terminó correctamente. El despliegue automático OIDC a AWS permanece sin configurar y no se ejecutó.')
else:
 p('El estado de GitHub Actions se comprueba en la ejecución de CI. El despliegue OIDC no se ejecutó.')

page();h('11 Riesgos y decisiones pendientes')
p('Se eligió API Gateway con VPC Link por ausencia de dominio y se mantuvo un ALB privado. En producción deben revisarse cuotas, throttling, roles mínimos y costo fijo de NAT frente al tráfico real. Para 10.000 usuarios se necesita diseñar comportamiento, generadores distribuidos, carga sostenida y margen ante pérdida de una AZ.')
p('El histórico events.csv es necesario para reentrenar y comparar nuevas métricas. La integración de eventos ya entrega SQLite compatible, pero no constituye una automatización completa de entrenamiento. El cambio de versión debe incluir evaluación, promoción y una prueba de rollback entre modelos distintos.')
p('Antes de la entrega académica corresponde confirmar el número de equipo, las cifras definitivas del caso EP1 y el formato arc42 del AVA. La defensa de hasta diez minutos debe distinguir objetivos, configuración y medición; el material para Claude incluye un guion y las evidencias originales.')
h('12 Glosario',2)
p('AZ: zona de disponibilidad. RPO: pérdida temporal de datos tolerable. RTO: tiempo objetivo de recuperación. DLQ: cola de mensajes que agotaron reintentos. Idempotencia: repetir un evento no duplica su efecto. LCU: unidad de capacidad del ALB. VPC Link: conexión privada de API Gateway al balanceador.')
h('Referencias técnicas en formato APA',2)
refs=[
 ('Amazon Web Services. (s. f.). Amazon ECS services.','https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs_services.html'),
 ('Amazon Web Services. (s. f.). Handling errors for an SQS event source in Lambda.','https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-errorhandling.html'),
 ('Amazon Web Services. (s. f.). Setting a schedule pattern for scheduled rules in Amazon EventBridge.','https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-scheduled-rule-pattern.html'),
 ('Amazon Web Services. (2026). ShopFast EP2 2 réplicas y 4 réplicas [Estimaciones de AWS Pricing Calculator].','https://calculator.aws/#/estimate?id=d074410aa269b21da99d9eafcd24f1cc0ed57403'),
 ('Peña, M., y Yantzen, B. (2026). Recomendador e-commerce [Repositorio de software, base 1cc9149].','https://github.com/Martinignaciiooo/recomendador-ecommerce')]
for title,url in refs:
 para=link(title,url);para.paragraph_format.space_after=Pt(4)
 for run in para.runs:run.font.size=Pt(9)
p('Documentación técnica consultada el 30 de octubre de 2026. Los JSON y los archivos de Calculator permiten rastrear cifras, fechas y alcance de cada ensayo.','Caption')
h('Declaración de uso de inteligencia artificial',2)
p('Se utilizó ChatGPT/Codex para revisar y adaptar código, preparar y ejecutar pruebas y despliegues en el laboratorio autorizado, generar diagramas y actualizar documentación. El equipo debe revisar los entregables y asumir la responsabilidad técnica de su defensa. Claude se utilizará para componer la presentación a partir del contexto y de las evidencias suministradas.')

out=ROOT/'entregables/EP2_Informe_ShopFast_Actualizado.docx';out.parent.mkdir(exist_ok=True)
doc.save(out)
print(out)
