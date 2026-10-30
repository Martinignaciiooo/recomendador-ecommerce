# Prompt para crear la presentación completa

Actúa como diseñador de presentaciones técnicas y prepara el PPTX final y su PDF para la Evaluación Parcial 2 de ITY1102. Usa los archivos adjuntos de ShopFast; el informe actualizado y los JSON tienen prioridad sobre cualquier propuesta histórica. Los autores son Martín Peña y Benjamín Yantzen. No inventes número de equipo, datos, capturas, entrenamiento o pruebas no ejecutadas.

Genera diez diapositivas 16:9 y notas del presentador para una defensa de exactamente diez minutos, siguiendo GUION_10_DIAPOSITIVAS.md. Distribuye las primeras cinco entre Martín y las últimas cinco en Benjamín. Mantén las fuentes, los matices y las cifras del contexto completo.

Incluye cinco diagramas: contexto, contenedores, componentes, eventos y despliegue. Recréales con formas nativas editables o SVG legible a partir de 04_Diagramas. Usa títulos de 30–36 pt, cuerpo 22–26 pt y etiquetas de diagramas al menos 18 pt. Si una imagen queda demasiado pequeña, simplifica su representación sin cambiar servicios ni flujos. No pegues páginas enteras del Word como diapositivas.

Usa diseño sobrio con fondo claro, azul oscuro y acentos AWS discretos. Cada lámina debe tener una conclusión concreta, pocas líneas y un visual útil. Incluye una comparación gráfica del pricing de 2/4 réplicas y una tabla breve de pruebas. Deja el detalle técnico en las notas.

Obligatorio: diferenciar primera ejecución cerrada de segunda demo temporal; HTTPS termina en API Gateway y el ALB es interno; LabRole es una restricción del lab; la alerta SNS se forzó para probar el canal; los percentiles son desde CloudShell y solo de respuestas 200; las dos solicitudes fallidas de la segunda carga original no tienen código conservado; la repetición sí mostró 499 HTTP 200 y un 429; rollback usó el mismo modelo; PITR restauró una tabla nueva sin cambiar tráfico; no hubo reentrenamiento nuevo, A/B, prueba de 10.000 usuarios ni SLA mensual validado. El exportador DynamoDB→SQLite sí está implementado y probado.

Los USD 140,37/176,41 son escenarios mensuales de 730 h y tráfico constante. No son el consumo real del laboratorio. Los USD 172,04/215,29 de planeación incluyen USD 3 de reserva de dashboard y 20% de contingencia. Conserva los exports originales y explica los defaults no seleccionados de NAT regional si se pregunta.

Incluye al menos dos fuentes técnicas oficiales en APA y una declaración breve de uso de IA. La última lámina debe distinguir implementado, probado y pendiente. Añade enlaces de referencia en notas y un vínculo a la demo con su expiración; nunca incluyas tokens, claves AWS ni valores de Secrets Manager.

Antes de finalizar, verifica que todos los números coincidan con METRICAS_VERIFICADAS.json, que la duración sume 600 s y que ningún diagrama muestre ALB público con ACM como si fuera el despliegue real. Entrega PPTX editable y PDF listos para presentar.
