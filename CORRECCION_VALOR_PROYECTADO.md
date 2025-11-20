# 🔧 Corrección: Endpoint POST "/emprestito/crear-tabla-proyecciones"

**Fecha:** 20 de noviembre de 2025  
**Problema:** La variable `valor_proyectado` no se estaba procesando correctamente desde Google Sheets  
**Causa:** La columna en Google Sheets se llama `"VALOR TOTAL"` (sin salto de línea)

---

## 📋 Problema Identificado

El endpoint no estaba capturando correctamente el campo `valor_proyectado` porque:

1. **Nombre real en Google Sheets:** `"VALOR TOTAL"` (sin salto de línea, solo con espacio)
2. **Lógica anterior:** No tenía esta variante como prioridad en la búsqueda
3. **Búsqueda insuficiente:** No normalizaba correctamente espacios múltiples ni consideraba todas las variantes

---

## ✅ Solución Implementada

### Archivo modificado:
- `api/scripts/emprestito_operations.py` - Función `procesar_datos_proyecciones`

### Cambios principales:

#### 1. **Separación del procesamiento de `valor_proyectado`**
   - Ahora se procesa de forma independiente del resto de campos
   - Evita conflictos de sobrescritura de valores

#### 2. **Variantes de columna ampliadas** (en orden de prioridad):
```python
columnas_valor_proyectado = [
    "VALOR TOTAL",           # Nombre real en Google Sheets ✅ PRIORIDAD 1
    "valor_proyectado",      # Nombre ideal
    "VALOR \n TOTAL",        # Con espacios y salto de línea (legacy)
    "VALOR\n TOTAL",         # Sin espacio antes del salto
    "VALOR \nTOTAL",         # Con espacio antes, sin después
    "VALOR\nTOTAL",          # Sin espacios
    "VALOR  TOTAL",          # Con doble espacio
]
```

#### 3. **Normalización mejorada con regex**:
```python
# Normaliza espacios múltiples, saltos de línea, retornos de carro y tabuladores
col_clean = re.sub(r'\s+', ' ', col.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')).lower().strip()
```

#### 4. **Triple nivel de búsqueda**:
   1. **Búsqueda exacta:** Compara el nombre exacto de la columna
   2. **Búsqueda normalizada:** Compara versiones normalizadas (sin espacios extra ni saltos)
   3. **Búsqueda por palabras clave:** Si contiene "valor" Y "total" → MATCH

#### 5. **Logs mejorados**:
   - Muestra la columna exacta encontrada en el DataFrame
   - Formato del valor original y procesado
   - Warnings claros cuando no se encuentra el campo

#### 6. **Garantía de inicialización**:
   - Si no se encuentra ninguna variante, asigna `0` como valor por defecto
   - Registra warning en los logs para detectar problemas

---

## 🧪 Validación

### Script de prueba: `test_valor_sheets_real.py`

Resultados confirmados:
- ✅ Detecta correctamente `"VALOR \n TOTAL"` con espacios
- ✅ Procesa todas las variantes de formato (con/sin espacios, saltos de línea, etc.)
- ✅ Limpia correctamente formatos numéricos ($, puntos, comas)
- ✅ Convierte valores correctamente a float

### Ejemplo de procesamiento:
```
Columna original en Sheets: "VALOR TOTAL"
Valor en celda: "$1.500.000.000"
Resultado procesado: 1500000000.0 ✅
```

---

## 📊 Casos de prueba exitosos

| Formato en Sheets | Detectado | Procesado | Prioridad |
|-------------------|-----------|-----------|-----------|
| `VALOR TOTAL` | ✅ | ✅ | **1** 🎯 |
| `valor_proyectado` | ✅ | ✅ | 2 |
| `VALOR \n TOTAL` | ✅ | ✅ | 3 |
| `VALOR\n TOTAL` | ✅ | ✅ | 4 |
| `VALOR  TOTAL` | ✅ | ✅ | 5 |
| `VALOR   TOTAL` | ✅ | ✅ | 5 |

---

## 🚀 Próximos pasos

1. **Reiniciar servidor API** (si está corriendo):
   ```bash
   # Detener el servidor actual
   # Iniciar nuevamente
   python main.py
   ```

2. **Probar el endpoint**:
   ```bash
   POST /emprestito/crear-tabla-proyecciones
   ```

3. **Verificar en logs**:
   - Buscar mensajes como: `✅ Fila X: valor_proyectado = 1,500,000,000 desde columna 'VALOR TOTAL'`
   - Verificar que no aparezcan warnings de `valor_proyectado no encontrado`

4. **Consultar datos guardados**:
   - Revisar colección `proyecciones_emprestito` en Firebase
   - Verificar que los documentos contengan el campo `valor_proyectado` con valores numéricos

---

## 📝 Notas técnicas

- **Compatibilidad:** Mantiene compatibilidad con todas las variantes anteriores
- **Performance:** Búsqueda optimizada con orden de prioridad
- **Robustez:** Maneja espacios múltiples, tabuladores, y diferentes tipos de saltos de línea
- **Fallback:** Búsqueda por palabras clave como último recurso
- **Debugging:** Logs detallados para diagnóstico

---

## ✅ Checklist de verificación

- [x] Variantes de columna ampliadas
- [x] Normalización con regex implementada
- [x] Búsqueda por palabras clave agregada
- [x] Logs mejorados
- [x] Scripts de prueba creados
- [x] Validación exitosa
- [ ] Prueba en servidor real
- [ ] Verificación en Firebase

---

**Desarrollado por:** GitHub Copilot  
**Fecha:** 20 de noviembre de 2025
