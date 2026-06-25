# Revisión del catálogo de Centros Gestores

`centros_catalog_revision.csv` es la lista canónica actual (27 centros) generada desde
`back/auth_system/centros_catalog.py`. Confirmá o corregí esta lista **antes** de
normalizar datos en Firestore, porque el registro de usuarios y el filtrado por centro
validan contra ella.

## Columnas
- **nombre_canonico**: el nombre oficial que se guardará en usuarios y registros.
- **origen**:
  - `ejecucion+registro` (19): aparecen en datos de ejecución (`centro_gestor.json`) y en el
    formulario de registro. Alta confianza.
  - `solo_registro` (8): se ofrecían en el registro pero NO tienen datos de ejecución todavía.
    **Revisá estos**: confirmá que son centros reales y no entradas viejas del formulario.
- **aliases_conocidos**: variantes (normalizadas) que mapean a ese canónico al canonicalizar.
- **confirmar**: poné `SI`, `NO` (eliminar del catálogo) o `CORREGIR: <nombre correcto>`.

## Filas que requieren tu decisión
- **#19 Gestión del Riesgo**: hoy los alias `DAGRD` / "Departamento Administrativo de Gestión
  del Riesgo" mapean a "Secretaría de Gestión del Riesgo...". Confirmá que son la MISMA entidad
  (renombrada) y no dos distintas.
- **#20–#27 (`solo_registro`)**: confirmá cuáles son centros gestores vigentes.

## Cómo aplicar cambios
Editá la lista `CENTROS_GESTORES` (y `_ALIASES_RAW` si agregás variantes) en AMBOS archivos,
manteniéndolos idénticos:
- `back/auth_system/centros_catalog.py`
- `front/src/utils/centrosCatalog.ts`

Luego corré los tests: `pytest back/test/unit/test_rbac_centro_scoping.py` y
`npx vitest run src/utils` en `front/`.

## Después de confirmar
1. Auditoría (no escribe): `python back/scripts/migraciones/auditar_normalizar_centros.py`
   → revisá los centros no mapeables y la lista de usuarios que quedarían bloqueados.
2. Agregá alias para cualquier variante real que aparezca, hasta que la lista de bloqueados
   sea aceptable.
3. Normalizá: `python back/scripts/migraciones/auditar_normalizar_centros.py --apply`
4. Recién entonces desplegá el endurecimiento de scoping del backend.
