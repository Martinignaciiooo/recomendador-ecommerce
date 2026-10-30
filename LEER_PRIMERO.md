# ShopFast EP2 implementado y validado

## Informe y material de presentación

- entregables/EP2_Informe_ShopFast_Actualizado.docx: informe editable actualizado de diez páginas.
- entregables/EP2_Informe_ShopFast_Actualizado.pdf: el mismo informe para revisión o entrega.
- docs/para-claude: prompt, contexto completo, guion de diez diapositivas y métricas verificadas.
- diagrams: cinco diagramas actualizados en PNG, SVG y Draw.io.
- docs/pricing-aws y docs/COSTOS.md: cotizaciones oficiales de dos y cuatro réplicas, exports y supuestos.
- docs/evidencias-aws: copias publicables que separan las dos ejecuciones y ocultan la cuenta AWS.

El ZIP de CloudShell contiene fuentes de ejecución. Los informes y el material separado para Claude están en el paquete completo y en el repositorio.

## Estado real al 30 de octubre de 2026

Pasaron 46 pruebas locales y la validación de ambas plantillas. Docker se construyó en CloudShell y la API se desplegó en Learner Lab 186191. Se comprobaron HTTPS, dos tareas privadas en dos AZ, eventos idempotentes, logs, métricas, SNS, cargas breves, reposición ECS, modelo S3, rollback de fuente y una copia PITR. Los errores de las cargas posteriores permanecen documentados.

La integración continua de GitHub Actions aprobó pruebas, CloudFormation, build y smoke Docker en la revisión 5314dc0. El despliegue OIDC a AWS no se configuró ni ejecutó. La ejecución está enlazada en el README y el informe.

La primera ejecución se retiró y verificó. La segunda demo tiene cierre programado el 30-10-2026 a las 03:55 de Santiago. El README contiene enlaces y el archivo autocierre.json conserva el horario. Los recursos retenidos generan costo residual; la EC2 anterior no se modificó.

El modelo es el artefacto real preentrenado v20260921-052859. Se exportaron eventos de DynamoDB al formato SQLite del entrenamiento, pero falta data/events.csv para entrenar y evaluar otra versión. No se validaron 10.000 usuarios ni disponibilidad mensual.

## Preparación de la defensa

Usar el prompt y el guion para que Claude construya el PPTX y PDF de diez diapositivas y diez minutos. Confirmar el número de equipo y la plantilla extendida del AVA sin inventarlos. La pauta solicita al menos cinco diagramas, dos fuentes técnicas APA y declaración IA; el informe actualizado los contempla. No incluir credenciales en Claude, capturas, documentos o GitHub.
