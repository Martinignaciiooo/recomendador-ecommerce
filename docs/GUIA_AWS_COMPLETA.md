# Ejecutar ShopFast en Learner Lab

Esta guía corresponde a la variante real de Academy. La plantilla de producción con dominio y ACM se conserva en infra/shopfast.json; no es la utilizada en la demo.

Usar el curso 186191 y us-east-1. Configurar SHOPFAST_EXPECTED_ACCOUNT_ID con la cuenta mostrada por ese laboratorio, no con una cuenta personal. El script compara esa identidad antes de hacer cambios. No guardar claves ni tokens en el repositorio.

Seguir la secuencia del README: preflight, build, bootstrap, service, verify, recovery, model-s3, rollback y cleanup. Extraer el ZIP en un directorio nuevo para conservar evidencias anteriores. El bootstrap crea NAT con cobro por hora. No ejecutar bootstrap sobre un stack existente.

La demo actual es HTTPS API Gateway → VPC Link → ALB interno → ECS privado. El dashboard está en /dashboard, Swagger en /docs y la salud pública en /health/ready. Recomendaciones, métricas y modelo necesitan el Bearer de Secrets Manager. El panel es administrativo, no un login de compradores.

La segunda demo usa DemoCloseAt y DemoCloseCron para habilitar el cierre mediante EventBridge y Lambda. La función comprueba el ARN exacto, las etiquetas Project/Practice y el plazo antes de solicitar DeleteStack. El horario actual y la prueba dry_run están en las evidencias. No se depende de mantener abierto CloudShell.

Guardar los JSON y las capturas antes de retirar. cleanup inspecciona el stack, lo elimina, espera y verifica NAT, EIP, ALB y ECS. S3, ECR, DynamoDB y logs se conservan con costo residual. La EC2 anterior y los stacks de otros proyectos quedan fuera del cierre.

El README y el informe actualizado separan ambos ensayos, sus errores de carga y sus límites. No presentar las cotizaciones mensuales como consumo de la sesión, ni una ráfaga breve como 10.000 usuarios concurrentes o SLA mensual validado.

# Acceso a la demo

- Dashboard: https://s1a1vms9gh.execute-api.us-east-1.amazonaws.com/dashboard
- Salud pública: https://s1a1vms9gh.execute-api.us-east-1.amazonaws.com/health/ready
- Swagger: https://s1a1vms9gh.execute-api.us-east-1.amazonaws.com/docs
- Cierre programado: 2026-10-30T03:55:00-03:00 (America/Santiago); 2026-10-30T06:55:00+00:00 UTC.

El dashboard es administrativo y requiere el token del proyecto. Entra por AWS Academy → curso 186191 → Learner Lab → AWS → Secrets Manager. Identifica el secreto del stack shopfast-ep2-lab mediante su Output SecretArn y copia solo su campo token al panel. No pegues el valor en Claude, GitHub, capturas ni diapositivas. Esta entrega no contiene credenciales.

La ruta de salud permite comprobar el modelo sin token. El mensaje del panel sin autenticación no sustituye esa comprobación. Al vencer el plazo, la Lambda de cierre solicita eliminar exclusivamente el ARN de este stack. Conserva S3, ECR, tablas y logs con costo residual. La EC2 anterior queda fuera de ese cierre.

Para detener antes, usar scripts/lab.sh cleanup en la sesión del laboratorio, con SHOPFAST_EXPECTED_ACCOUNT_ID configurada. Para repetir, usar el README del código y un directorio nuevo. No ejecutar bootstrap sobre un servicio que ya existe.
