# Evidencias de ejecución de AWS

Los originales privados se conservan en evidencias del computador y en los ZIP descargados de CloudShell. Las copias publicables de docs/evidencias-aws ocultan la cuenta y omiten detalles de red innecesarios; no contienen valores de secretos.

primera_ejecucion contiene salud/autorización, dos cargas sin errores, eventos idempotentes, reposición 72,82 s, modelo S3, rollback de fuente 263 s, copia PITR 251,13 s (552,08 s con espera), exportación compatible y cierre verificado.

segunda_ejecucion contiene la nueva URL y cierre programado, inventario resumido, salud, eventos y SNS. Las cargas fueron 100/5 (p95 71,13 ms, cero fallos) y 500/20 (p95 101,73 ms, dos fallos sin códigos conservados). La repetición instrumentada conserva 499 HTTP 200 y un HTTP 429, p95 115,04 ms. No se sustituyeron las mediciones anteriores.

Los percentiles se calculan solo con respuestas 200 desde CloudShell en us-east-1. El throughput cuenta intentos, no únicamente respuestas correctas. La prueba Windows comprueba TLS y autorización; sus 532 ms de health no son p95 de recomendaciones.

Las cotizaciones originales PDF/CSV/JSON están separadas del consumo real. Las métricas offline de out/metricas.json son previas y no provienen de entrenamiento nuevo. La disponibilidad mensual, 10.000 usuarios, failover completo de AZ, corte de tráfico a la tabla restaurada y despliegue OIDC no fueron ensayados.
