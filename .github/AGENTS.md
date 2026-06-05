# Directrices del Proyecto — gestor_proyecto_api

## Stack Tecnológico

- **Backend**: FastAPI 0.116+ / Uvicorn / Python 3.12
- **Persistencia**: Firebase Admin SDK + Firestore
- **Auth**: Firebase Auth + JWT + RBAC propio (auth_system/)
- **Storage**: AWS S3 (boto3) para archivos, Firestore para datos
- **Testing**: pytest + pytest-asyncio + httpx + locust
- **Deploy**: Railway (Docker, python:3.12-slim)
- **Frontend**: NextJS (consumidor externo)

## Reglas de Seguridad (Prioridad Máxima)

### Secretos y Credenciales — NUNCA exponer

- **PROHIBIDO** incluir en código, logs, respuestas HTTP, comentarios o documentación:
  - Service account keys, tokens JWT, API keys
  - Valores de `FIREBASE_SERVICE_ACCOUNT_KEY`, `GOOGLE_APPLICATION_CREDENTIALS_JSON`
  - Credenciales AWS (`aws_credentials.json`), claves de Railway
  - Contenido de archivos `.env`, `.env.new` o `credentials/`
  - Contraseñas, secrets de GitHub Actions, `RAILWAY_TOKEN`
- **SIEMPRE** usar variables de entorno (`os.environ`, `python-dotenv`) para configuración sensible.
- **SIEMPRE** validar que `.gitignore` excluya `.env`, `credentials/`, `*.json` de service accounts.
- En logs y errores: incluir contexto operativo (endpoint, entidad, ID) **sin** datos sensibles.
- En respuestas de error HTTP: mensajes genéricos al cliente, detalle solo en logs internos.

### Autenticación y Autorización

- Verificar token Firebase (`verify_firebase_token`) antes de cualquier operación protegida.
- Respetar jerarquía RBAC definida en `auth_system/constants.py` (7 roles, nivel 0-6).
- Los paths públicos están definidos en `auth_system/constants.py` — no agregar nuevos sin revisión.
- Validar permisos con formato `action:resource:scope` antes de operaciones CRUD.
- Nunca confiar en datos del cliente para determinar roles o permisos.

### Validación de Entrada

- Toda entrada del usuario pasa por modelos Pydantic con validación estricta.
- Sanitizar inputs para prevenir inyección en consultas Firestore.
- Aplicar límites de tamaño, paginación obligatoria en listados.
- Validar tipos MIME y tamaño de archivos antes de subir a S3.

## Estilo de Código

- Español para nombres de dominio (`contrato`, `frente`, `intervencion`, `unidad_proyecto`).
- Inglés para patrones técnicos (`router`, `endpoint`, `middleware`, `handler`).
- Tipar parámetros y retornos en funciones nuevas o modificadas.
- Funciones pequeñas y legibles; evitar archivos monolíticos nuevos.
- Mantener `main.py` como orquestador; lógica de negocio en `api/scripts/`.
- Modelos request/response en `api/models/`.
- Configuración Firebase centralizada en `database/firebase_config.py`.

## Arquitectura

```
main.py                    → Orquestador FastAPI (endpoints, middleware, lifespan)
api/routers/               → Routers separados por dominio
api/models/                → Modelos Pydantic (request/response)
api/scripts/               → Lógica de negocio y operaciones
api/utils/                 → Utilidades compartidas
auth_system/               → RBAC, middleware de auth, decoradores, constantes
database/firebase_config.py → Inicialización Firebase (SA key, WIF, ADC)
```

- Middleware stack: UTF-8 → Performance → Monitoring → Timeout → CORS → Auth → Audit.
- Errores con `HTTPException` y códigos HTTP consistentes.
- Diseño asíncrono: no bloquear event loop en endpoints `async`.

## Build y Test

```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar servidor local
python main.py

# Tests rápidos
pytest -q --maxfail=1

# Tests con cobertura
pytest --cov=. --cov-report=term-missing

# Test de carga
locust -f locustfile.py

# Docker local
docker-compose up --build
```

## Convenciones

- Un archivo de test por feature/endpoint (`test_*.py` en raíz).
- Variables de entorno documentadas en `.env.example` — nunca valores reales.
- Deploy automático a Railway via `.github/workflows/deploy.yml` (push a master/main).
- Datos del empréstito sincronizados por cron via `.github/workflows/emprestito-automation.yml`.
- UTF-8 obligatorio en todas las respuestas (soporte completo español).
- Skills de Copilot disponibles en `.github/skills/` — consultar antes de proponer cambios en áreas cubiertas.

## Operaciones según Entorno

| Acción                         | Local                  | Staging                | Producción               |
| ------------------------------ | ---------------------- | ---------------------- | ------------------------ |
| Debug detallado en logs        | ✅                     | ⚠️ Sin datos sensibles | ❌                       |
| Escritura directa en Firestore | ✅ Con mocks preferido | ✅ Datos de prueba     | ⚠️ Requiere confirmación |
| Deploy                         | N/A                    | Manual                 | Automático (push master) |
| Pruebas de carga               | ✅                     | ✅                     | ❌ Nunca contra prod     |

## Checklist antes de cada cambio

- [ ] ¿Se mantiene el contrato del endpoint (request/response)?
- [ ] ¿Hay validación de entrada suficiente con Pydantic?
- [ ] ¿Se manejan errores de Firebase/Firestore sin exponer internos?
- [ ] ¿No se filtraron secretos o credenciales en código/logs/respuestas?
- [ ] ¿Hay tests nuevos o actualizados para el comportamiento modificado?
- [ ] ¿El cambio respeta la jerarquía RBAC existente?
