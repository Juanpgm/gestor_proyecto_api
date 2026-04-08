# Skills Maestro — gestor_proyecto_api

Índice centralizado de habilidades especializadas para optimizar el desarrollo en este repositorio.

## Skills Disponibles

| Skill                   | Archivo                                                      | Propósito                                           |
| ----------------------- | ------------------------------------------------------------ | --------------------------------------------------- |
| FastAPI + Firebase API  | `skills/fastapi-firebase-api-skills.md`                      | Desarrollo robusto, testing, seguridad, rendimiento |
| Alta Concurrencia       | `skills/fastapi-high-concurrency-endpoints-skills.md`        | Optimización de endpoints críticos bajo carga       |
| Migraciones Firestore   | `skills/firestore-zero-downtime-migrations-skills.md`        | Cambios de esquema sin downtime                     |
| Reglas por Entorno      | `skills/environment-operational-rules-skills.md`             | Ajustes por local/staging/prod                      |
| Testing Autónomo        | `skills/smart-testing-autonomy-and-critical-gates-skills.md` | Autonomía con gates de seguridad                    |
| **Seguridad API REST**  | _(este archivo)_                                             | Protección de secretos y hardening                  |
| **Diseño de Endpoints** | _(este archivo)_                                             | Mejores prácticas REST en FastAPI                   |
| **Firestore Seguro**    | _(este archivo)_                                             | Operaciones seguras con Firestore                   |

---

## Skill: Seguridad para API REST en FastAPI

### Gestión de Secretos

**Regla absoluta**: Cero secretos en código fuente, logs, respuestas o artefactos.

#### Patrón obligatorio para credenciales

```python
# CORRECTO — variables de entorno
import os
firebase_key = os.environ.get("FIREBASE_SERVICE_ACCOUNT_KEY")
if not firebase_key:
    raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_KEY no configurada")

# PROHIBIDO — valores hardcodeados
firebase_key = "eyJ0eXBlIjoic2VydmljZV9hY2NvdW50..."  # NUNCA
```

#### Archivos que NUNCA deben estar en el repositorio

- `.env`, `.env.new`, `.env.production`, `.env.local`
- `credentials/*.json` (AWS, Firebase service accounts)
- `*-service-account*.json`
- Archivos con tokens, API keys o claves privadas

#### Verificación de .gitignore

Antes de cualquier commit, confirmar que `.gitignore` incluye:

```
.env
.env.*
credentials/
*service-account*.json
*-sa-key*.json
```

### Respuestas de Error Seguras

```python
# CORRECTO — error genérico al cliente, detalle en logs
import logging
logger = logging.getLogger(__name__)

try:
    result = await firestore_operation()
except Exception as e:
    logger.error(f"Error en operación Firestore para contrato {contrato_id}: {type(e).__name__}")
    raise HTTPException(status_code=500, detail="Error interno del servidor")

# PROHIBIDO — exponer internos al cliente
raise HTTPException(status_code=500, detail=f"Firestore error: {str(e)}")  # NUNCA
raise HTTPException(status_code=500, detail=f"Key: {service_account_key}")  # NUNCA
```

### Headers de Seguridad Recomendados

```python
# Middleware o en respuestas individuales
response.headers["X-Content-Type-Options"] = "nosniff"
response.headers["X-Frame-Options"] = "DENY"
response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
response.headers["Cache-Control"] = "no-store"  # Para endpoints con datos sensibles
```

### CORS — Configuración Segura

- Orígenes explícitos desde variables de entorno (`FRONTEND_URL`, `CORS_ORIGINS`).
- NUNCA usar `allow_origins=["*"]` en producción.
- Limitar métodos y headers permitidos al mínimo necesario.

### Rate Limiting

- Aplicar límites por IP/usuario en endpoints de autenticación (`/auth/login`, `/auth/register`).
- Endpoints de escritura masiva con throttling progresivo.
- Usar `slowapi` cuando esté habilitado en el entorno.

---

## Skill: Diseño de Endpoints REST en FastAPI

### Convenciones de URL

```
GET    /recurso                    → Listar (con paginación)
GET    /recurso/{id}               → Obtener uno
POST   /recurso                    → Crear
PUT    /recurso/{id}               → Actualizar completo
PATCH  /recurso/{id}               → Actualizar parcial
DELETE /recurso/{id}               → Eliminar
```

Para este proyecto usar kebab-case en URLs: `/unidades-proyecto`, `/proyectos-presupuestales`.

### Modelo de Respuesta Consistente

```python
# Patrón estándar de respuesta
{
    "success": True,
    "data": { ... },           # Payload principal
    "message": "Operación exitosa",
    "total": 150,              # Solo en listados paginados
    "page": 1,
    "page_size": 50
}

# Patrón de error
{
    "success": False,
    "detail": "Descripción del error para el cliente",
    "error_code": "RESOURCE_NOT_FOUND"  # Código máquina opcional
}
```

### Validación con Pydantic

```python
from pydantic import BaseModel, Field, field_validator

class ContratoCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=500)
    valor: float = Field(..., gt=0)
    centro_gestor: str = Field(..., pattern=r"^[A-Z0-9-]+$")

    @field_validator("nombre")
    @classmethod
    def sanitize_nombre(cls, v: str) -> str:
        return v.strip()
```

### Paginación Obligatoria

Todo endpoint que retorne listas debe implementar paginación:

```python
@app.get("/recurso")
async def listar_recursos(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    offset = (page - 1) * page_size
    # ... query con limit/offset
```

### Manejo de Errores por Capas

| Capa                 | Responsabilidad                            |
| -------------------- | ------------------------------------------ |
| Pydantic             | Validación de formato/tipo de entrada      |
| Endpoint             | Lógica de negocio y autorización           |
| Operations (scripts) | Errores de Firestore/S3/servicios externos |
| Middleware           | Auth, timeout, CORS, encoding              |

### Documentación Automática

- Cada endpoint con `summary`, `description`, `response_model` y `tags`.
- Modelos Pydantic con `Field(description=...)` para OpenAPI.
- Accesible en `/docs` (Swagger) y `/redoc`.

---

## Skill: Operaciones Firestore Seguras

### Reglas de Acceso a Datos

```python
# CORRECTO — validar existencia antes de operar
doc_ref = db.collection("contratos").document(contrato_id)
doc = doc_ref.get()
if not doc.exists:
    raise HTTPException(status_code=404, detail="Contrato no encontrado")

# CORRECTO — leer solo campos necesarios
doc = doc_ref.get(field_paths=["nombre", "estado", "valor"])

# PROHIBIDO — asumir que el documento existe
data = doc_ref.get().to_dict()["campo"]  # Puede lanzar KeyError/TypeError
```

### Escritura Idempotente

```python
# Usar merge=True para actualizaciones parciales seguras
doc_ref.set({"estado": "activo", "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
```

### Consultas Eficientes

- Evitar lecturas N+1: agrupar IDs y usar `get_all()` o consultas con `in`.
- Límite máximo explícito en queries: `.limit(FIRESTORE_BATCH_SIZE)`.
- Usar `FIRESTORE_TIMEOUT` de variables de entorno para timeouts.

### Transacciones para Consistencia

```python
@firestore.transactional
def actualizar_con_consistencia(transaction, doc_ref, nuevos_datos):
    snapshot = doc_ref.get(transaction=transaction)
    if not snapshot.exists:
        raise ValueError("Documento no encontrado")
    transaction.update(doc_ref, nuevos_datos)
```

### Prevención de Inyección en Queries

- Nunca construir paths de colección/documento con input del usuario sin validar.
- Sanitizar IDs de documento: solo alfanuméricos, guiones y guiones bajos.

```python
import re

def validate_document_id(doc_id: str) -> str:
    if not re.match(r'^[a-zA-Z0-9_-]+$', doc_id):
        raise HTTPException(status_code=400, detail="ID de documento inválido")
    return doc_id
```

---

## Checklist de Seguridad por Cambio

- [ ] ¿Las credenciales se obtienen exclusivamente de variables de entorno?
- [ ] ¿Los errores al cliente no exponen detalles internos (stack traces, queries, keys)?
- [ ] ¿Los logs registran contexto operativo SIN datos sensibles?
- [ ] ¿Las entradas están validadas con Pydantic antes de llegar a lógica de negocio?
- [ ] ¿CORS está configurado con orígenes explícitos (no `*` en producción)?
- [ ] ¿El endpoint requiere autenticación si accede a datos protegidos?
- [ ] ¿Los IDs de Firestore están sanitizados contra inyección de path?
- [ ] ¿`.gitignore` cubre todos los archivos sensibles?
- [ ] ¿Las respuestas no incluyen campos internos (IDs de SA, project IDs sensibles)?
- [ ] ¿El nuevo endpoint respeta el patrón de respuesta consistente del proyecto?
