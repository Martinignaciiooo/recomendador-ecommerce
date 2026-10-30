# Ejecutar ShopFast en Learner Lab

Esta guía corresponde a la variante real de Academy. La plantilla de producción con dominio y ACM se conserva en infra/shopfast.json; no es la utilizada en la demo.

Usar el curso 186191 y us-east-1. Configurar SHOPFAST_EXPECTED_ACCOUNT_ID con la cuenta mostrada por ese laboratorio, no con una cuenta personal. El script compara esa identidad antes de hacer cambios. No guardar claves ni tokens en el repositorio.

Seguir la secuencia del README: preflight, build, bootstrap, service, verify, recovery, model-s3, rollback y cleanup. Extraer el ZIP en un directorio nuevo para conservar evidencias anteriores. El bootstrap crea NAT con cobro por hora. No ejecutar bootstrap sobre un stack existente.

La demo actual es HTTPS API Gateway → VPC Link → ALB interno → ECS privado. El dashboard está en /dashboard, Swagger en /docs y la salud pública en /health/ready. Recomendaciones, métricas y modelo necesitan el Bearer de Secrets Manager. El panel es administrativo, no un login de compradores.

La segunda demo usa DemoCloseAt y DemoCloseCron para habilitar el cierre mediante EventBridge y Lambda. La función comprueba el ARN exacto, las etiquetas Project/Practice y el plazo antes de solicitar DeleteStack. El horario actual y la prueba dry_run están en las evidencias. No se depende de mantener abierto CloudShell.

Guardar los JSON y las capturas antes de retirar. cleanup inspecciona el stack, lo elimina, espera y verifica NAT, EIP, ALB y ECS. S3, ECR, DynamoDB y logs se conservan con costo residual. La EC2 anterior y los stacks de otros proyectos quedan fuera del cierre.

El README y el informe actualizado separan ambos ensayos, sus errores de carga y sus límites. No presentar las cotizaciones mensuales como consumo de la sesión, ni una ráfaga breve como 10.000 usuarios concurrentes o SLA mensual validado.
