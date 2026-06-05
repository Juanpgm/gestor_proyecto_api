# Skill: Contrato API Back ↔ Front

**Cuándo cargar**: Al modificar endpoints existentes que el frontend consume, al agregar nuevos campos a response shapes, o al coordinar cambios que afectan a ambos repos.

---

## Principio de Contrato

CaliTrack tiene dos repos independientes (`gestor_proyecto_api` / `gestor_proyectos_vercel`) con deployments separados (Railway / Vercel). Un cambio en el backend que rompa el contrato de API **rompe silenciosamente el frontend**.

### Regla de Oro
> Antes de cambiar un response shape o un endpoint URL, actualizar:
> 1. `obsidian_vault/02_API_CONTRACTS/endpoints_catalog.md`
> 2. Los tipos TypeScript en `front/src/types/<dominio>.ts`

---

## Catálogo de Endpoints Críticos (resumen)

### Auth
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/auth/login` | Login, retorna token y datos de usuario |
| GET | `/auth/me` | Info del usuario autenticado + rol |
| POST | `/auth/logout` | Invalida sesión |

### Contratos
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/contratos/` | Lista con filtros opcionales |
| GET | `/contratos/{id}` | Detalle de contrato |
| PATCH | `/contratos/{id}` | Actualizar estado |
| GET | `/contratos/{id}/documentos` | Documentos S3 del contrato |

### Unidades de Proyecto (UP)
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/unidades-proyecto/` | Lista de UPs con geometrías GeoJSON |
| GET | `/unidades-proyecto/{id}` | Detalle UP |
| GET | `/unidades-proyecto/{id}/avances` | Avances de ejecución |
| POST | `/unidades-proyecto/{id}/avances` | Cargar avance |

### Frentes Activos
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/frentes-activos/` | Frentes en ejecución |
| GET | `/frentes-activos/{id}` | Detalle frente |

### Empréstito
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/emprestito/` | Datos del empréstito |
| GET | `/emprestito/calidad` | Indicadores de calidad |
| GET | `/emprestito/flujo-caja` | Flujo de caja |

### Captura 360°
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/captura-360/upload` | Upload de foto georreferenciada |
| GET | `/captura-360/{contrato_id}` | Fotos de un contrato |

---

## Response Shape Estándar

El backend retorna JSON con esta estructura consistente:

```python
# ✅ Respuesta exitosa (FastAPI)
{
    "status": "success",
    "data": { ... },      # El objeto de dominio
    "message": null
}

# ✅ Lista con paginación
{
    "status": "success",
    "data": [...],
    "total": 150,
    "page": 1,
    "per_page": 50
}

# ✅ Error (HTTPException)
{
    "detail": "Contrato no encontrado"   # FastAPI default
}
```

### Tipos TypeScript correspondientes

```typescript
// src/types/common.ts
export interface ApiResponse<T> {
  status: 'success' | 'error';
  data: T;
  message?: string;
}

export interface PaginatedResponse<T> {
  status: 'success';
  data: T[];
  total: number;
  page: number;
  per_page: number;
}

export interface ApiErrorResponse {
  detail: string;
}
```

---

## Campos de Fechas — Formato Estándar

```python
# Backend (Python) — siempre ISO 8601
from datetime import datetime
fecha_inicio: datetime = datetime.now()  # → "2026-04-24T10:30:00"
```

```typescript
// Frontend (TypeScript) — string ISO, parsear con Date o date-fns
const fecha = new Date(contrato.fecha_inicio);
import { format } from 'date-fns';
import { es } from 'date-fns/locale';
format(fecha, 'dd/MM/yyyy', { locale: es }); // → "24/04/2026"
```

---

## Headers Requeridos por el Backend

```typescript
// Todo request autenticado DEBE incluir:
{
  'Authorization': `Bearer ${idToken}`,   // Firebase ID Token
  'Content-Type': 'application/json',
}

// Para upload de archivos:
{
  'Authorization': `Bearer ${idToken}`,
  // NO incluir Content-Type — el browser lo setea con el boundary correcto
}
```

---

## CORS — Configuración Backend

El backend tiene configurado CORS en `main.py`:
```python
# Dominios permitidos en producción:
# - https://calitrack-red.vercel.app (frontend Vercel)
# - http://localhost:3000 (desarrollo local)
```

El proxy de Next.js en `/api/proxy/[...path]` elimina la necesidad de CORS en el browser porque las llamadas son server-to-server.

---

## Breaking Changes — Protocolo

Cuando un cambio en el backend ROMPE el contrato:

1. **Crear un branch nuevo** en el repo del backend
2. **Notificar el cambio** actualizando `obsidian_vault/02_API_CONTRACTS/endpoints_catalog.md`
3. **Actualizar tipos** en `front/src/types/` en el mismo PR o en PR coordinado
4. **Deploy coordinado**: deploy backend primero, luego frontend (o usar feature flags)
5. **Nunca** hacer breaking change en `master` sin verificar que el frontend está actualizado

---

## Validación de Datos en Frontera

### Backend (Pydantic v2)
```python
# back/api/models/contratos.py
from pydantic import BaseModel, Field
from datetime import datetime

class ContratoCreate(BaseModel):
    numero_contrato: str = Field(..., min_length=1, max_length=50)
    valor_contrato: float = Field(..., gt=0)
    fecha_inicio: datetime
    contratista: str = Field(..., min_length=3)
```

### Frontend (Zod)
```typescript
// src/types/contratos.ts — Validación en formularios
import { z } from 'zod';

export const contratoSchema = z.object({
  numero_contrato: z.string().min(1).max(50),
  valor_contrato: z.number().positive(),
  fecha_inicio: z.string().datetime(),
  contratista: z.string().min(3),
});

export type ContratoCreate = z.infer<typeof contratoSchema>;
```

---

## Checklist de Cambio de API

Antes de hacer merge de cualquier cambio que modifique endpoints:

- [ ] `endpoints_catalog.md` actualizado en el vault
- [ ] Tipos TypeScript actualizados en `front/src/types/`
- [ ] Response shape estándar respetado (no romper estructura)
- [ ] Tests de backend actualizados (`back/test/`)
- [ ] Tests de service frontend actualizados (`front/src/__tests__/`)
- [ ] Variables de entorno actualizadas si cambia base URL
- [ ] CORS configurado para el nuevo dominio si aplica
- [ ] Coordinado deploy: backend primero
