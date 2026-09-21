# Guía de despliegue en AWS

Tiempo estimado: 60–90 minutos la primera vez. Al terminar tendrán:

- La API corriendo en EC2 con HTTPS y autenticación
- El dashboard accesible desde el navegador
- CI/CD: cada push a `main` corre los tests y despliega solo, con rollback si falla
- Reentrenamiento semanal programado
- (Opcional) El modelo publicado en SageMaker

> **Nada de esto fue ejecutado en AWS por quien preparó el código**: no tenía acceso a
> su cuenta. Todo lo que se pudo verificar sin AWS está verificado (tests, imagen
> simulada, handler de SageMaker, sintaxis de scripts y del workflow). Si algo falla,
> la sección final de problemas frecuentes cubre los casos más probables.

---

## 0. Requisitos

- Cuenta AWS (propia o **AWS Academy Learner Lab**)
- Cuenta GitHub
- Cuenta en **duckdns.org** (gratis, para tener dominio y HTTPS)
- En su computador: `git` y un cliente SSH

---

## 1. Subir el código a GitHub

```bash
cd sistema
git init && git add . && git commit -m "Sistema de recomendación"
git branch -M main
git remote add origin https://github.com/<usuario>/<repo>.git
git push -u origin main
```

El `.gitignore` ya excluye `events.csv` (100 MB) y los datos de producción. El modelo
entrenado (`out/models/`, 4,5 MB) **sí** se sube: la imagen lo necesita.

El repo debe ser **público** para que la instancia lo clone sin credenciales. Si lo
quieren privado, configuren una *deploy key* (GitHub > Settings > Deploy keys).

Al hacer el push, GitHub Actions ya corre el job **Build y test** (pestaña *Actions*).
El job **Deploy** fallará hasta completar el paso 6: es esperado.

---

## 2. Crear la instancia EC2

Consola AWS > EC2 > *Launch instance*:

| Campo | Valor |
|---|---|
| Nombre | `reco-api` |
| AMI | Amazon Linux 2023 |
| Tipo | `t3.small` (2 vCPU, 2 GB) |
| Key pair | crear una nueva, descargar el `.pem` y guardarlo bien |
| Almacenamiento | 20 GB gp3 |
| Security group | SSH (22) **solo desde "My IP"**; HTTP (80) y HTTPS (443) desde cualquier lugar |
| IAM instance profile | `LabInstanceProfile` en AWS Academy (opcional, para logs en CloudWatch) |

Recomendado: asignar una **Elastic IP** (EC2 > Elastic IPs > Allocate > Associate) para
que la IP no cambie al reiniciar. En AWS Academy la sesión tiene tiempo limitado y, sin
Elastic IP, la IP pública puede cambiar al volver a iniciar el laboratorio.

**Costo aproximado:** una t3.small encendida todo el mes ronda los USD 15 en us-east-1.
Verifiquen el valor vigente en la calculadora de AWS. Apáguenla cuando no la usen.

---

## 3. Dominio con DuckDNS

1. Entrar a duckdns.org con su cuenta de GitHub o Google.
2. Crear un subdominio, por ejemplo `reco-equipo3` → queda `reco-equipo3.duckdns.org`.
3. En *current ip*, poner la IP pública (o Elastic IP) de la instancia y *update ip*.

Let's Encrypt necesita un dominio para emitir el certificado; no lo emite para una IP.

---

## 4. Preparar la instancia

```bash
chmod 400 mi-llave.pem
ssh -i mi-llave.pem ec2-user@<IP_PUBLICA>

# ya dentro de la instancia:
curl -fsSLO https://raw.githubusercontent.com/<usuario>/<repo>/main/deploy/bootstrap_ec2.sh
bash bootstrap_ec2.sh https://github.com/<usuario>/<repo>.git reco-equipo3.duckdns.org
```

El script instala Docker, clona el repo, genera un **token de API aleatorio**, levanta
Caddy (HTTPS automático) y hace el primer despliegue. Al final imprime el token:
**guárdenlo**, lo necesitan para el dashboard y para Postman.

Cierren la sesión SSH y vuelvan a entrar (para que `ec2-user` quede en el grupo docker).

---

## 5. Verificar

```bash
TOKEN=<el token impreso>
DOM=reco-equipo3.duckdns.org

curl https://$DOM/salud
curl -H "Authorization: Bearer $TOKEN" "https://$DOM/recomendaciones?user_id=1515915625353230683&k=5"
curl -H "Authorization: Bearer $TOKEN" "https://$DOM/recomendaciones?user_id=999999999999&k=5"   # fallback
curl "https://$DOM/recomendaciones?user_id=1"      # sin token: debe responder 401
```

Dashboard: `https://reco-equipo3.duckdns.org/dashboard` (pegar el token en "Acceso").
Documentación interactiva de la API: `https://reco-equipo3.duckdns.org/docs`.

---

## 6. Activar el despliegue automático

GitHub > repo > Settings > Secrets and variables > Actions > *New repository secret*:

| Secreto | Valor |
|---|---|
| `EC2_HOST` | IP pública o Elastic IP |
| `EC2_USER` | `ec2-user` |
| `EC2_SSH_KEY` | contenido completo del `.pem`, incluidas las líneas BEGIN/END |
| `PUBLIC_DOMAIN` | `reco-equipo3.duckdns.org` |

El security group permite SSH solo desde su IP, y GitHub Actions usa otras IPs. Para
la demo, la opción simple es abrir el puerto 22 a `0.0.0.0/0` (la llave `.pem` sigue
siendo obligatoria). Documenten ese compromiso en el informe como riesgo conocido.

Prueba: hagan un cambio pequeño (p. ej. el título del dashboard), `git push`, y miren
la pestaña *Actions*: build → test → deploy → verificación HTTPS.

**Probar el rollback** (buena evidencia para la defensa): introduzcan a propósito un
error que rompa el arranque (p. ej. una ruta de modelo inexistente en el Dockerfile),
hagan push y verán en el log de *Deploy* el mensaje `ROLLBACK a reco-api:<commit>`,
con el servicio anterior siguiendo en línea. Luego reviertan el cambio.

---

## 7. Monitoreo

- **Aplicación:** `/metricas` y el dashboard muestran p50/p95/p99, tasa de caché,
  fallback y error en tiempo real.
- **Infraestructura:** CloudWatch recoge automáticamente CPU, red y *status checks*
  de la instancia. Creen una alarma: EC2 > instancia > *Monitoring* > *Create alarm*
  sobre `StatusCheckFailed` ≥ 1.
- **Logs en CloudWatch (opcional):** requiere el instance profile del paso 2.

  ```bash
  echo "AWSLOGS_GROUP=/reco/api" | sudo tee -a /etc/environment
  AWSLOGS_GROUP=/reco/api bash /opt/reco/app/deploy/deploy.sh
  ```

  Para que el despliegue automático lo mantenga, agreguen `export AWSLOGS_GROUP=/reco/api`
  antes de `bash deploy/deploy.sh` en `.github/workflows/ci-cd.yml`.

---

## 8. Reentrenamiento semanal

```bash
# desde su computador: subir el dataset a la instancia
scp -i mi-llave.pem events.csv ec2-user@<IP>:/opt/reco/app/data/

# en la instancia: probarlo una vez a mano (la primera vez instala dependencias, ~3 min)
bash /opt/reco/app/deploy/retrain.sh

# programarlo: domingos a las 03:00
(crontab -l 2>/dev/null; echo "0 3 * * 0 bash /opt/reco/app/deploy/retrain.sh >> /opt/reco/retrain.log 2>&1") | crontab -
```

En Amazon Linux 2023 `cron` puede no venir instalado: `sudo dnf install -y cronie && sudo systemctl enable --now crond`.

Si una t3.small se queda sin memoria al reentrenar, súbanla a t3.medium durante ese proceso.

**Volver a un modelo anterior:**

```bash
bash /opt/reco/app/deploy/rollback_modelo.sh             # lista versiones
bash /opt/reco/app/deploy/rollback_modelo.sh v2026...    # activa una
```

---

## 9. SageMaker (plataforma AIaaS)

Desde su computador, con credenciales AWS configuradas (`aws configure`, o las que
entrega AWS Academy en *AWS Details*):

```bash
pip install -r requirements-sagemaker.txt
python sagemaker/deploy_sagemaker.py desplegar --rol arn:aws:iam::<CUENTA>:role/LabRole
```

Usa **Serverless Inference**: cobra por invocación, no por hora. Tarda 5–10 minutos y
al final prueba el endpoint con un usuario conocido y uno nuevo.

Si su cuenta no permite serverless: `--instancia ml.t2.medium`. **Esa opción cobra por
hora aunque nadie la use.** Eliminen el endpoint al terminar:

```bash
python sagemaker/deploy_sagemaker.py eliminar --endpoint reco-als-<version>
```

**Por qué hay dos despliegues (EC2 y SageMaker):** EC2 sirve el tráfico con caché,
fallback y métricas propias; SageMaker demuestra el despliegue en plataforma AIaaS
administrada. Comparar la latencia de ambos es un buen punto para la defensa (IE20).

---

## Problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| Caddy no obtiene certificado | DuckDNS no apunta a la IP, o puertos 80/443 cerrados | Revisar DuckDNS y security group; `docker logs caddy` |
| `permission denied` con docker | la sesión no tomó el grupo docker | salir y volver a entrar por SSH |
| Deploy en Actions falla al conectar | puerto 22 cerrado a GitHub o `.pem` mal copiado | ver paso 6 |
| La API no arranca | registro de modelos vacío | `ls /opt/reco/models` debe mostrar `current` y una carpeta `v...` |
| 401 en el dashboard | falta el token | pegarlo en la tarjeta "Acceso" (`sudo cat /opt/reco/.env`) |
| Todo quedó con IP nueva | se reinició el laboratorio sin Elastic IP | actualizar DuckDNS y el secreto `EC2_HOST` |
| SageMaker: `AccessDenied` | el rol no tiene permisos | en AWS Academy usar `LabRole` |

---

## Checklist para la demostración en vivo

- [ ] Pestañas abiertas: dashboard, `/docs`, pestaña *Actions* de GitHub, consola EC2/CloudWatch
- [ ] Token a mano (no pegado en diapositivas)
- [ ] Postman o terminal con los `curl` del paso 5
- [ ] Mostrar las tres rutas: `model`, `cache` y `fallback`
- [ ] Registrar una compra desde el dashboard y mostrar que la caché se invalida
- [ ] Mostrar un run verde de CI/CD y, si es posible, el log de un rollback
- [ ] Plan B: capturas del sistema funcionando por si falla la conexión
