# Herramientas y Restricciones — gestor_proyecto_api

Configuración de herramientas, comandos permitidos y restricciones operativas para el desarrollo seguro de esta API.

---

## Herramientas del Proyecto

### Desarrollo Local

| Herramienta     | Comando                                    | Propósito                      |
| --------------- | ------------------------------------------ | ------------------------------ |
| Servidor local  | `python main.py`                           | Ejecutar API en puerto 8000    |
| Docker local    | `docker-compose up --build`                | Ejecutar en contenedor         |
| Tests rápidos   | `pytest -q --maxfail=1`                    | Validación rápida tras cambios |
| Tests cobertura | `pytest --cov=. --cov-report=term-missing` | Cobertura completa             |
| Tests de carga  | `locust -f locustfile.py`                  | Performance/estrés             |
| Linter          | `python -m py_compile main.py`             | Verificar sintaxis             |
| Dependencias    | `pip install -r requirements.txt`          | Instalar producción            |
| Deps testing    | `pip install -r requirements-test.txt`     | Instalar testing               |

### CI/CD (GitHub Actions)

| Workflow        | Trigger                | Archivo                                       |
| --------------- | ---------------------- | --------------------------------------------- |
| Deploy Railway  | Push a master/main     | `.github/workflows/deploy.yml`                |
| Empréstito Sync | Cron (6x/día) + manual | `.github/workflows/emprestito-automation.yml` |

### Servicios Externos

| Servicio      | SDK/Cliente              | Variable de Config                       |
| ------------- | ------------------------ | ---------------------------------------- |
| Firebase Auth | `firebase-admin`         | `FIREBASE_SERVICE_ACCOUNT_KEY`           |
| Firestore     | `google-cloud-firestore` | (mismo SA key)                           |
| AWS S3        | `boto3`                  | `AWS_CREDENTIALS_FILE_UNIDADES_PROYECTO` |
| Google Sheets | `gspread`                | (credenciales Google)                    |
| SECOP API     | `sodapy`                 | (API pública)                            |

---

## Restricciones de Seguridad para Herramientas

### Terminal — Comandos PROHIBIDOS

Nunca ejecutar estos comandos en ningún entorno:

```bash
# PROHIBIDO — exponer secretos
cat .env
echo $FIREBASE_SERVICE_ACCOUNT_KEY
printenv | grep KEY
cat credentials/*.json
base64 -d <<< $FIREBASE_SERVICE_ACCOUNT_KEY

# PROHIBIDO — operaciones destructivas sin confirmación
rm -rf .git
git push --force
git reset --hard
DROP TABLE / DELETE FROM (operaciones masivas en DB)

# PROHIBIDO — bypass de seguridad
git commit --no-verify
pip install --trusted-host  # Sin certificado SSL
```

### Terminal — Comandos que REQUIEREN confirmación

```bash
# Requiere confirmación explícita del usuario
git push origin master          # Deploy a producción
railway deploy                  # Deploy manual
docker-compose down -v          # Pérdida de volúmenes
pip install <paquete-nuevo>     # Cambio de dependencias
```

### Terminal — Comandos SEGUROS (ejecutar libremente)

```bash
# Lectura y diagnóstico
cat requirements.txt
python -c "import fastapi; print(fastapi.__version__)"
pytest -q --maxfail=1
pytest test_<específico>.py -q
python -m py_compile <archivo>.py
git status
git log --oneline -10
git diff
docker-compose ps

# Navegación
ls api/ auth_system/ database/
cat .env.example
```

---

## Restricciones por Archivo

### Archivos que NUNCA deben modificarse sin revisión

| Archivo                        | Razón                              | Acción requerida                       |
| ------------------------------ | ---------------------------------- | -------------------------------------- |
| `database/firebase_config.py`  | Inicialización crítica de Firebase | Revisión de seguridad                  |
| `auth_system/constants.py`     | Roles, permisos, paths públicos    | Validar implicaciones RBAC             |
| `auth_system/middleware.py`    | Filtro de auth en cada request     | Testing exhaustivo                     |
| `.github/workflows/deploy.yml` | Pipeline de producción             | Verificar secrets                      |
| `Dockerfile`                   | Imagen de producción               | Validar seguridad del contenedor       |
| `.gitignore`                   | Protección de archivos sensibles   | Solo agregar, nunca quitar exclusiones |

### Archivos que NUNCA deben leerse/exponerse

| Archivo/Patrón           | Contenido                           |
| ------------------------ | ----------------------------------- |
| `.env`                   | Todas las credenciales del proyecto |
| `.env.new`               | Credenciales alternativas           |
| `credentials/*.json`     | Claves AWS                          |
| `*service-account*.json` | Firebase SA keys                    |

### Archivos seguros para editar libremente

- `api/scripts/*.py` — Lógica de negocio (con tests)
- `api/models/*.py` — Modelos Pydantic
- `api/routers/*.py` — Routers FastAPI
- `test_*.py` — Archivos de test
- `api/utils/*.py` — Utilidades
- `README.md`, `docs/**` — Documentación

---

## Políticas de Dependencias

### Agregar nueva dependencia

1. Verificar que no existe alternativa ya instalada.
2. Comprobar mantenimiento activo y ausencia de CVEs conocidos.
3. Agregar versión pinneada en `requirements.txt` (ej: `paquete==1.2.3`).
4. Si es solo para testing: agregar en `requirements-test.txt`.
5. Documentar propósito en comentario si no es obvio.

### Actualizar dependencia existente

1. Verificar changelog y breaking changes.
2. Ejecutar suite de tests completa tras actualización.
3. Validar en staging antes de merge a master.

### Dependencias PROHIBIDAS

- Paquetes que requieran acceso root o permisos de sistema elevados.
- Paquetes con vulnerabilidades conocidas sin parche.
- Paquetes que envíen telemetría a servidores externos sin consentimiento.
- Forks no oficiales de paquetes críticos (firebase-admin, boto3, fastapi).

---

## Políticas de Logging

### Qué registrar (SIEMPRE)

```python
logger.info(f"Endpoint {method} {path} - usuario={uid} - status={status}")
logger.error(f"Error en {operation} para {entity_id}: {error_type}")
logger.warning(f"Intento de acceso no autorizado: uid={uid}, path={path}")
```

### Qué NO registrar (NUNCA)

```python
# PROHIBIDO en logs
logger.info(f"Token: {token}")                    # Token JWT
logger.debug(f"SA Key: {service_account_key}")     # Service account
logger.error(f"Credenciales: {credentials}")       # Cualquier credencial
logger.info(f"Password: {password}")               # Contraseñas
logger.debug(f"Request body: {request.body()}")    # Puede contener datos sensibles
```

### Formato de logs recomendado

```
[TIMESTAMP] [LEVEL] [endpoint/operación] [entity_type:entity_id] mensaje_descriptivo
```

---

## Políticas de Docker

### Imagen de producción

- Base: `python:3.12-slim` (mínima superficie de ataque).
- Usuario no-root (`appuser`).
- Sin herramientas de debug en producción.
- Health check activo en `/health`.
- Variables sensibles via Railway secrets (nunca en Dockerfile/docker-compose).

### docker-compose local

- `.env` montado por `env_file`, nunca copiado al contenedor.
- Puertos expuestos solo en desarrollo.
- No montar volúmenes con credenciales.

---

## Resumen de Niveles de Acción

| Nivel        | Tipo de Acción                                              | Confirmación                 |
| ------------ | ----------------------------------------------------------- | ---------------------------- |
| 0 - Seguro   | Lectura, búsqueda, tests unitarios                          | Ninguna                      |
| 1 - Moderado | Tests integración, benchmarks locales                       | Aviso previo                 |
| 2 - Delicado | Escritura Firestore, cambio de credenciales, instalar deps  | Confirmación explícita       |
| 3 - Crítico  | Deploy prod, borrado masivo, migración, rotación de secrets | Confirmación + plan rollback |
