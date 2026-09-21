# Imagen de la API de recomendaciones.
# Solo incluye lo necesario para servir: numpy, scipy y FastAPI.
# El entrenamiento (implicit, pandas) no va en la imagen de producción.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OPENBLAS_NUM_THREADS=1 \
    MODEL_ROOT=/app/out/models \
    EVENTS_DB=/app/data/eventos.db

WORKDIR /app
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

COPY src/core.py src/api.py src/
COPY src/static/ src/static/
COPY out/models/ out/models/

# Usuario sin privilegios: si el proceso se compromete, no tiene root
RUN useradd --create-home --uid 1000 app && mkdir -p /app/data && chown -R app:app /app
USER app

WORKDIR /app/src
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/salud', timeout=2)" || exit 1

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
