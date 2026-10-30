# Paquete completo de la EP2 ShopFast

## Documentos

- `entregables/EP2_Informe_ShopFast.docx`: informe editable de 10 páginas.
- `entregables/EP2_EquipoN_Pena_Yantzen.pdf`: informe PDF preparado anteriormente.
- `entregables/Guia_AWS_ShopFast_EP2.docx`: pasos de cuenta, HTTPS, despliegue, pruebas, evidencias y retirada.
- `entregables/EP2_Presentacion_EquipoN.pptx`: presentación editable con notas.
- `entregables/EP2_Presentacion_EquipoN.pdf`: presentación para entregar.
- `pauta/EP2_ITY1102_Estudiante.pdf`: pauta original del docente.
- `diagrams/`: cinco diagramas Draw.io editables y sus vistas.

## Proyecto

El código, modelo real, Dockerfile, CloudFormation, workflow y scripts están en la raíz del paquete. Lee README.md antes de desplegar.

Estado actualizado al 30-10-2026: **46 pruebas locales aprobadas**, cfn-lint correcto, Docker construido y AWS probado en Learner Lab 186191. Se verificaron HTTPS, dos réplicas privadas en dos AZ, eventos, alertas, carga, reposición ECS, modelo S3, rollback y PITR. README.md separa las dos ejecuciones y conserva los errores observados. El informe actualizado está en `entregables/EP2_Informe_ShopFast_Actualizado.docx`.

El primer stack se retiró después del respaldo. La demo se recreó con cierre programado el 30-10-2026 a las 03:55 de Santiago; el README contiene los enlaces actuales. Los recursos retenidos tienen costo residual y la EC2 anterior no se modificó. La variante usa HTTPS de API Gateway porque no había dominio. `infra/shopfast-learner-lab.json` y `scripts/lab.sh` permiten repetirla con la cuenta esperada configurada.

Las cotizaciones oficiales de dos y cuatro réplicas, con enlaces y exportaciones PDF/CSV/JSON, están en `docs/COSTOS.md` y `evidencias/`. Esos montos mensuales no son el consumo de esta sesión.

GitHub Actions/OIDC y el reentrenamiento completo quedan pendientes; no se publicaron cambios en GitHub. Ya se exportaron eventos de DynamoDB al formato del entrenamiento, pero falta `data/events.csv` para entrenar y evaluar de nuevo. Confirmar caso EP1, número de equipo y plantilla arc42 extendida del AVA. Los documentos y diapositivas preparados anteriormente deben incorporar los resultados del README antes de la entrega académica final.

La pauta pide un informe PDF de 10 páginas, al menos cinco diagramas, dos fuentes técnicas APA y declaración IA, más defensa de máximo 10 minutos. Reemplazar EquipoN en los nombres y actualizar con evidencias reales antes de entregar.
