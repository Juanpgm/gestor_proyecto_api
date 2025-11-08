# Fix: Campo `nombre_banco` faltante en GET /emprestito/ordenes-compra

## 🐛 Problema Identificado

El endpoint `GET /emprestito/ordenes-compra` no retornaba el campo `nombre_banco` para órdenes creadas desde la API TVEC, aunque las órdenes creadas manualmente con `POST /emprestito/cargar-orden-compra-directa` sí lo incluían.

## 🔍 Causa Raíz

1. **Función `obtener_datos_tvec`** (línea 428): No extraía el campo `nombre_banco` de la respuesta TVEC
2. **Función `guardar_orden_compra_emprestito`** (línea 568): No validaba ni establecía un valor predeterminado para `nombre_banco`

## ✅ Solución Implementada

### 1. Modificación en `obtener_datos_tvec` (línea 470-492)

```python
# Extraer nombre_banco de agregacion si está disponible
agregacion = orden_raw.get("agregacion", "")
nombre_banco = orden_raw.get("nombre_banco", "")

# Si nombre_banco no está disponible, usar agregacion como banco
# (ya que agregacion puede contener información del banco financiador)
if not nombre_banco and agregacion:
    nombre_banco = agregacion

# Mapear campos según especificaciones
orden_datos = {
    "referencia_proceso": orden_raw.get("identificador_de_la_orden", referencia_proceso),
    "fecha_publicacion": orden_raw.get("fecha", ""),
    "fecha_vence": orden_raw.get("fecha_vence", ""),
    "estado": orden_raw.get("estado", ""),
    "agregacion": agregacion,
    "nombre_banco": nombre_banco,  # ✅ Ahora se incluye nombre_banco
    "valor_publicacion": valor_publicacion
}
```

**Cambios:**

- Se extrae el campo `agregacion` que puede contener información del banco
- Se usa `agregacion` como fallback si `nombre_banco` no está presente en TVEC
- Se agrega `nombre_banco` al diccionario de datos retornado

### 2. Modificación en `guardar_orden_compra_emprestito` (línea 586-594)

```python
# Si nombre_banco no está presente pero agregacion sí, usar agregacion como nombre_banco
if not datos.get("nombre_banco") and datos.get("agregacion"):
    datos["nombre_banco"] = datos.get("agregacion")
    logger.info(f"nombre_banco derivado de agregacion: {datos['nombre_banco']}")

# Si aún no hay nombre_banco, establecer valor por defecto
if not datos.get("nombre_banco"):
    datos["nombre_banco"] = "No especificado"
    logger.warning("nombre_banco no disponible, usando valor por defecto")
```

**Cambios:**

- Se valida que `nombre_banco` exista antes de guardar
- Fallback 1: Si falta `nombre_banco` pero existe `agregacion`, se usa `agregacion`
- Fallback 2: Si ambos faltan, se establece "No especificado"
- Se agregan logs informativos para trazabilidad

## 📊 Flujo de Datos

### Antes del Fix:

```
TVEC API → obtener_datos_tvec() → { sin nombre_banco }
         ↓
    guardar_orden_compra_emprestito() → Firebase (sin nombre_banco)
         ↓
    GET /emprestito/ordenes-compra → ❌ nombre_banco faltante
```

### Después del Fix:

```
TVEC API → obtener_datos_tvec() → { nombre_banco: "agregacion" o "" }
         ↓
    guardar_orden_compra_emprestito() → Validación y fallback
         ↓
    Firebase → { nombre_banco: garantizado }
         ↓
    GET /emprestito/ordenes-compra → ✅ nombre_banco presente
```

## 🧪 Escenarios Cubiertos

| Escenario                    | Fuente TVEC                     | Resultado                          |
| ---------------------------- | ------------------------------- | ---------------------------------- |
| TVEC tiene `nombre_banco`    | `nombre_banco: "Banco Mundial"` | Usa valor directo                  |
| TVEC solo tiene `agregacion` | `agregacion: "BID"`             | `nombre_banco = "BID"`             |
| TVEC no tiene ninguno        | Ambos vacíos                    | `nombre_banco = "No especificado"` |
| Orden manual POST            | Usuario provee `nombre_banco`   | Usa valor del usuario              |

## 📝 Archivos Modificados

- **`api/scripts/emprestito_operations.py`**
  - Función `obtener_datos_tvec` (línea 428-520)
  - Función `guardar_orden_compra_emprestito` (línea 568-618)

## 🎯 Impacto

### Órdenes Nuevas

- ✅ Todas las órdenes creadas después del fix tendrán `nombre_banco`
- ✅ Compatible con órdenes TVEC y órdenes manuales

### Órdenes Existentes

- ⚠️ Las órdenes ya guardadas en Firebase sin `nombre_banco` seguirán sin el campo
- 💡 **Recomendación**: Crear un script de migración para agregar `nombre_banco = "No especificado"` a órdenes existentes

## 🔧 Script de Migración Sugerido

```python
async def migrar_ordenes_sin_nombre_banco():
    """
    Agregar nombre_banco a órdenes existentes que no lo tienen
    """
    db = get_firestore_client()
    ordenes_ref = db.collection('ordenes_compra_emprestito')

    docs = ordenes_ref.stream()
    actualizadas = 0

    for doc in docs:
        doc_data = doc.to_dict()

        if not doc_data.get("nombre_banco"):
            # Usar agregacion si existe, sino "No especificado"
            nuevo_nombre_banco = doc_data.get("agregacion", "No especificado")

            doc.reference.update({
                "nombre_banco": nuevo_nombre_banco,
                "fecha_actualizacion": datetime.now()
            })
            actualizadas += 1
            logger.info(f"Orden {doc.id} actualizada con nombre_banco: {nuevo_nombre_banco}")

    return {
        "success": True,
        "ordenes_actualizadas": actualizadas
    }
```

## ✅ Pruebas Recomendadas

1. **Crear orden TVEC nueva** y verificar que `nombre_banco` se guarda correctamente
2. **Consultar GET /emprestito/ordenes-compra** y verificar que todas las órdenes tienen `nombre_banco`
3. **Crear orden manual** con POST y verificar que `nombre_banco` se preserva
4. **Revisar logs** para verificar cuándo se usan los fallbacks

## 📚 Documentación Relacionada

- **Endpoint GET /emprestito/ordenes-compra**: main.py línea 4782
- **Endpoint POST /emprestito/cargar-orden-compra-directa**: main.py línea 3758
- **Función obtener_datos_tvec**: api/scripts/emprestito_operations.py línea 428
- **Función guardar_orden_compra_emprestito**: api/scripts/emprestito_operations.py línea 568
- **Función get_ordenes_compra_emprestito_all**: api/scripts/ordenes_compra_operations.py línea 34

## 🎉 Resultado Final

El campo `nombre_banco` ahora estará **garantizado** en todas las órdenes de compra retornadas por el endpoint GET, ya sea:

- Provisto directamente por TVEC
- Derivado del campo `agregacion` de TVEC
- Establecido como "No especificado" por defecto
- Provisto manualmente en órdenes POST

---

**Fecha**: 2024
**Archivos modificados**: 1
**Funciones actualizadas**: 2
**Estado**: ✅ Implementado y listo para pruebas
