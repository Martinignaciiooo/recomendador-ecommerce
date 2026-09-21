# Sistema de Recomendación de Productos — Implementación

Implementación del Caso 1 (ITY1102) para la Evaluación Final Transversal: modelo
entrenado sobre el dataset real, API REST, dashboard, tests, contenedor, CI/CD,
scripts de despliegue en AWS y despliegue en SageMaker.

---

## Resultados medidos

Split **temporal** (entrenar con el pasado, predecir el futuro), corte 30-01-2021,
1.087 usuarios evaluables en test.

| Modelo | Precision@10 | Recall@10 | MAP@10 | Cobertura |
|---|---|---|---|---|
| Popularidad (baseline) | 0,0125 | 0,0441 | 0,0239 | 0,2 % |
| Item-item CF (coseno) | 0,0113 | 0,0440 | 0,0154 | 37,3 % |
| **ALS, 32 factores (en producción)** | **0,0220** | **0,0818** | **0,0368** | 17,4 % |

**ALS vs. baseline: +76 % precisión, +85 % recall, +54 % MAP.**
Configuración elegida por barrido de 8 combinaciones (`out/sweep.json`): la de mejor
MAP@10. Contrapartida: el ALS de 128 factores cubre más catálogo (34,7 %) con algo
menos de precisión; se priorizó la relevancia.

**Latencia** (`out/carga.json`, 1.500 solicitudes a usuarios distintos, un proceso):

| | p50 | p95 | p99 |
|---|---|---|---|
| Cálculo en el servidor | 0,19 ms | 0,25 ms | 0,30 ms |
| Extremo a extremo (HTTP incluido) | 1,09 ms | 1,47 ms | 2,37 ms |

Presupuesto del caso: 200 ms. Throughput: ~876 solicitudes/s en un solo proceso.
Medido en local: en EC2 se suma la latencia de red, que conviene medir y reportar.

**Tests:** 27 pasando, sin necesitar el dataset (corren en CI).

### Cómo NO leer estos números

Precision@10 = 0,022 significa que, en promedio, 0,22 de cada 10 productos recomendados
aparecieron en la actividad real del usuario durante el periodo de test. **No es una
predicción de la conversión.** Afirmar que el sistema lleva la conversión de 1,5 % a
3,5 % requiere un test A/B en producción; con estos datos solo puede afirmarse que el
modelo supera claramente a no personalizar.

---

## Hallazgos sobre los datos

1. **Dispersión extrema.** Mediana de eventos por usuario: **1**. De 407.283 usuarios,
   solo 7.706 tienen dos o más compras. Tras filtrar (≥5 interacciones), la matriz es
   de 22.434 × 7.656 con densidad **0,04 %**. El *cold start* es el caso dominante:
   el fallback (AD3) sostiene la experiencia para la mayoría de los visitantes.
2. **Item-item CF no supera a la baseline en precisión**: con esta densidad, la
   co-ocurrencia entre productos es demasiado escasa. Por eso se eligió ALS.
3. **La baseline cubre 0,2 % del catálogo**: recomienda casi lo mismo a todos.
4. **El dataset cubre ~5 meses**, no los 2 años del enunciado. Las cifras del caso se
   usan como requisitos de negocio; el dataset, como base técnica.

---

## Diferencias entre el diseño (EP1) y la implementación

La pauta de la EFT pide justificar los cambios respecto del diseño inicial:

| Diseño EP1 | Implementación | Motivo |
|---|---|---|
| ECS Fargate con autoescalado | EC2 + Docker | La EFT pide "EC2 o servicio equivalente"; un solo servidor basta para demostrar el sistema y reduce la complejidad operativa para 2 personas. El contenedor es el mismo, así que migrar a ECS no exige cambiar código. |
| DynamoDB para features | Factores del modelo en memoria | El modelo completo pesa 4,5 MB; leerlo desde una base agregaría latencia sin beneficio a esta escala. DynamoDB se justifica si el catálogo crece órdenes de magnitud. |
| API Gateway + ACM | Caddy (HTTPS automático con Let's Encrypt) | Mismo resultado (TLS, un punto de entrada) sin costo ni configuración adicional. |
| Registro de modelos en SageMaker | Registro propio versionado (`out/models/vYYYYMMDD-HHMMSS/` + puntero `current`) | Implementa AD4 de forma simple y verificable; SageMaker se usa para el despliegue AIaaS. |
| Eventos a un data lake en S3 | SQLite en volumen persistente | Suficiente para el volumen de la demo; el reentrenamiento ya los incorpora. En producción real, S3. |

---

## Arquitectura implementada

```
                      HTTPS (Let's Encrypt)
Navegador / Shopify ──────────► Caddy ──► API FastAPI (Docker, EC2)
                                           ├─ caché LRU            (AD1)
                                           ├─ núcleo ALS (core.py)
                                           ├─ fallback más vendidos (AD3)
                                           ├─ /eventos ──► SQLite ──┐
                                           └─ /metricas, /dashboard │
                                                                    │
       cron semanal: retrain.sh ◄─────────────────────────────────┘
          prepare_data → train_final → registro de modelos versionado (AD4)
                                        └─ se activa solo si no empeora

GitHub push ──► Actions: build → test (27) → imagen Docker → smoke test → deploy SSH
                                                          deploy.sh: health check + rollback

SageMaker Serverless ◄── deploy_sagemaker.py (mismo core.py, mismo modelo)
```

---

## Estructura

```
src/
  prepare_data.py     carga, suma eventos de la API, split temporal, matriz dispersa
  train_evaluate.py   3 modelos + métricas (precision, recall, MAP, cobertura)
  tune.py             barrido de hiperparámetros + benchmark de latencia
  train_final.py      entrenamiento de producción: versiona y promueve (champion/challenger)
  core.py             inferencia compartida por la API y SageMaker (solo numpy/scipy)
  api.py              API REST: caché, fallback, eventos, métricas, auth, dashboard
  static/dashboard.html
  tests_reco.py       27 tests
out/models/           registro de modelos (el activo lo indica 'current')
out/*.json, *.png     métricas, barrido, prueba de carga, gráfico comparativo
sagemaker/            handler de inferencia + script de despliegue
deploy/               bootstrap EC2, deploy con rollback, reentrenamiento, Caddy, guía
.github/workflows/    pipeline CI/CD
Dockerfile
```

---

## Uso local

```bash
pip install -r requirements.txt
cd src

# La API funciona de inmediato con el modelo incluido:
uvicorn api:app --reload             # http://localhost:8000/dashboard  ·  /docs
pytest -v tests_reco.py              # 27 tests

# Reentrenar desde cero (requiere data/events.csv, ver data/LEEME.txt):
python prepare_data.py               # ~30 s
python train_evaluate.py             # compara los 3 modelos
python tune.py                       # barrido + latencia
python train_final.py                # versiona y promueve si no empeora
```

## Endpoints

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| GET | `/recomendaciones?user_id=&k=` | sí | Top-k con categoría, marca y precio. `source`: `model`, `cache` o `fallback` |
| POST | `/eventos` | sí | Registra `view`/`cart`/`purchase`; invalida la caché del usuario |
| GET | `/metricas` | no | p50/p95/p99, tasas de caché, fallback y error |
| GET | `/modelo` | no | Versión activa, configuración, métricas offline vs baseline |
| GET | `/salud` | no | Health check (balanceador y pipeline) |
| GET | `/dashboard` | no* | Panel web (*las consultas que hace sí usan el token) |

La autenticación se activa definiendo `RECO_API_TOKEN` (en EC2 lo genera el bootstrap).

---

## Despliegue en AWS

Ver **`deploy/GUIA_DESPLIEGUE_AWS.md`**: EC2, HTTPS, CI/CD, monitoreo, reentrenamiento
y SageMaker, paso a paso.

## Qué está verificado y qué no

| Verificado en este entorno | No verificado (requiere su cuenta AWS / GitHub) |
|---|---|
| Entrenamiento, evaluación y promoción de modelos | Construcción real de la imagen Docker |
| 27 tests en entorno limpio sin el dataset | Ejecución del workflow en GitHub Actions |
| API con solo las dependencias de la imagen | Bootstrap y deploy en EC2, certificado HTTPS |
| Dashboard en navegador real (Chromium) | Despliegue en SageMaker |
| Handler de SageMaker y empaquetado del modelo | Latencia real a través de internet |
| Sintaxis de scripts bash y del workflow YAML | |
