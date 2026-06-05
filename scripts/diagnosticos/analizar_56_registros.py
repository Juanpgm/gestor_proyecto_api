"""
Análisis detallado para encontrar qué 56 registros podría estar mostrando el frontend
"""
import asyncio
import json

async def analizar_56_registros():
    """Analizar diferentes combinaciones para llegar a 56"""
    
    print("=" * 80)
    print("ANÁLISIS: ¿POR QUÉ 56 REGISTROS?")
    print("=" * 80)
    
    from api.scripts.unidades_proyecto import get_frentes_activos
    
    result = await get_frentes_activos()
    features = result.get('features', [])
    
    print(f"\n1. Total features: {len(features)}")
    
    # Diferentes criterios de filtrado
    print(f"\n2. Probando diferentes criterios:")
    
    # Solo coordenadas válidas (no [0,0])
    validas = [f for f in features 
               if f.get('geometry', {}).get('coordinates', []) not in [[0, 0], [0.0, 0.0]]]
    print(f"   a) Solo coords válidas (no [0,0]): {len(validas)}")
    
    # Con has_geometry = True (del documento original de Firestore)
    from database.firebase_config import get_firestore_client
    db = get_firestore_client()
    
    # Obtener has_geometry de Firestore para cada feature
    upids = [f['properties']['upid'] for f in features]
    has_geometry_map = {}
    
    for upid in upids:
        doc_ref = db.collection('unidades_proyecto').document(upid)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            has_geometry_map[upid] = data.get('has_geometry', False)
    
    con_has_geometry = [f for f in features 
                        if has_geometry_map.get(f['properties']['upid'], False)]
    print(f"   b) Con has_geometry=True: {len(con_has_geometry)}")
    
    # Combinación: coordenadas válidas Y has_geometry
    combo = [f for f in features 
             if f.get('geometry', {}).get('coordinates', []) not in [[0, 0], [0.0, 0.0]]
             and has_geometry_map.get(f['properties']['upid'], False)]
    print(f"   c) Coords válidas Y has_geometry=True: {len(combo)}")
    
    # Solo con lat/lng diferentes de 0
    con_coords_reales = []
    for f in features:
        geom = f.get('geometry', {})
        coords = geom.get('coordinates', [])
        if len(coords) >= 2:
            lng, lat = coords[0], coords[1]
            if lng != 0 and lat != 0:
                con_coords_reales.append(f)
    print(f"   d) Con lng!=0 Y lat!=0: {len(con_coords_reales)}")
    
    # Análisis de UPIDs específicos
    print(f"\n3. Análisis detallado de registros:")
    print(f"\n   Registros SIN coordenadas válidas ({65 - len(validas)}):")
    sin_coords_validas = [f for f in features 
                          if f.get('geometry', {}).get('coordinates', []) in [[0, 0], [0.0, 0.0]]]
    for f in sin_coords_validas:
        props = f['properties']
        upid = props.get('upid')
        centro = props.get('nombre_centro_gestor', 'N/A')
        has_geom = has_geometry_map.get(upid, False)
        print(f"      {upid}: {centro} | has_geometry={has_geom}")
    
    print(f"\n   Registros CON coordenadas válidas PERO sin has_geometry:")
    sin_has_geom = [f for f in features 
                    if f.get('geometry', {}).get('coordinates', []) not in [[0, 0], [0.0, 0.0]]
                    and not has_geometry_map.get(f['properties']['upid'], False)]
    print(f"      Total: {len(sin_has_geom)}")
    for f in sin_has_geom[:5]:  # Mostrar solo primeros 5
        props = f['properties']
        upid = props.get('upid')
        centro = props.get('nombre_centro_gestor', 'N/A')
        coords = f.get('geometry', {}).get('coordinates', [])
        print(f"      {upid}: {centro} | coords={coords}")
    
    # Verificar si 56 = 65 - 9
    print(f"\n4. Cálculo inverso:")
    print(f"   65 (total) - 9 = 56")
    print(f"   ¿Hay exactamente 9 registros con alguna característica específica?")
    
    # Contar registros sin has_geometry en Firestore
    sin_has_geometry_count = sum(1 for upid in upids if not has_geometry_map.get(upid, False))
    print(f"   - Sin has_geometry en Firestore: {sin_has_geometry_count}")
    
    # Contar centros específicos
    por_deporte = [f for f in features 
                   if 'Deporte' in f['properties'].get('nombre_centro_gestor', '')]
    print(f"   - De Secretaría del Deporte: {len(por_deporte)}")
    
    print(f"\n5. HIPÓTESIS:")
    if len(por_deporte) == 9:
        print(f"   💡 El frontend podría estar EXCLUYENDO los 9 registros de 'Secretaría del Deporte'")
        print(f"   Estos 9 registros tienen coordenadas [0,0] (sin geometría real)")
    
    print(f"\n   O tal vez el frontend está filtrando por:")
    print(f"   - Combinación de has_geometry Y coordenadas válidas")
    print(f"   - O excluyendo algún centro gestor específico")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    asyncio.run(analizar_56_registros())
