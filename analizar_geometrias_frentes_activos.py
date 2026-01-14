"""
Analizar geometrías en frentes activos para identificar por qué el frontend muestra menos registros
"""
import asyncio
import json

async def analizar_geometrias():
    """Analizar geometrías de frentes activos"""
    
    print("=" * 80)
    print("ANÁLISIS: GEOMETRÍAS EN FRENTES ACTIVOS")
    print("=" * 80)
    
    from api.scripts.unidades_proyecto import get_frentes_activos
    
    result = await get_frentes_activos()
    
    features = result.get('features', [])
    
    print(f"\n1. Total features devueltos por endpoint: {len(features)}")
    print(f"   Total frentes activos: {result.get('properties', {}).get('total_frentes_activos')}")
    
    # Analizar geometrías
    print(f"\n2. Análisis de geometrías:")
    
    sin_geometria = []
    con_geometria_invalida = []
    con_geometria_valida = []
    con_coordenadas_null = []
    
    for feature in features:
        geometry = feature.get('geometry')
        properties = feature.get('properties', {})
        upid = properties.get('upid')
        nombre_centro = properties.get('nombre_centro_gestor', '')
        
        if not geometry:
            sin_geometria.append({
                'upid': upid,
                'nombre_centro': nombre_centro
            })
        else:
            coords = geometry.get('coordinates', [])
            geom_type = geometry.get('type')
            
            # Verificar si son coordenadas nulas [0, 0]
            if coords == [0, 0] or coords == [0.0, 0.0]:
                con_coordenadas_null.append({
                    'upid': upid,
                    'nombre_centro': nombre_centro,
                    'geometry_type': geom_type,
                    'coordinates': coords
                })
            # Verificar si tiene coordenadas válidas
            elif coords and len(coords) >= 2:
                # Para Point
                if geom_type == 'Point':
                    lng, lat = coords[0], coords[1]
                    if lng != 0 and lat != 0:
                        con_geometria_valida.append({
                            'upid': upid,
                            'nombre_centro': nombre_centro,
                            'coordinates': coords
                        })
                    else:
                        con_geometria_invalida.append({
                            'upid': upid,
                            'nombre_centro': nombre_centro,
                            'coordinates': coords
                        })
                else:
                    # Otros tipos de geometría
                    con_geometria_valida.append({
                        'upid': upid,
                        'nombre_centro': nombre_centro,
                        'geometry_type': geom_type
                    })
            else:
                con_geometria_invalida.append({
                    'upid': upid,
                    'nombre_centro': nombre_centro,
                    'coordinates': coords
                })
    
    print(f"\n   - Con geometría válida (coords != [0,0]): {len(con_geometria_valida)}")
    print(f"   - Con coordenadas nulas [0,0]: {len(con_coordenadas_null)}")
    print(f"   - Con geometría inválida: {len(con_geometria_invalida)}")
    print(f"   - Sin geometría: {len(sin_geometria)}")
    
    # Mostrar detalles de coordenadas nulas
    if con_coordenadas_null:
        print(f"\n3. Registros con coordenadas nulas [0,0] ({len(con_coordenadas_null)}):")
        for item in con_coordenadas_null[:10]:  # Mostrar solo primeros 10
            print(f"   - {item['upid']}: {item['nombre_centro']}")
    
    # Contar por centro gestor
    print(f"\n4. Distribución por centro gestor:")
    centros = {}
    centros_con_geom_valida = {}
    
    for feature in features:
        props = feature.get('properties', {})
        centro = props.get('nombre_centro_gestor', 'Sin centro')
        geometry = feature.get('geometry', {})
        coords = geometry.get('coordinates', [])
        
        # Contar total
        if centro not in centros:
            centros[centro] = 0
        centros[centro] += 1
        
        # Contar solo con geometría válida
        if coords and coords != [0, 0] and coords != [0.0, 0.0]:
            if centro not in centros_con_geom_valida:
                centros_con_geom_valida[centro] = 0
            centros_con_geom_valida[centro] += 1
    
    for centro in sorted(centros.keys()):
        total = centros[centro]
        validas = centros_con_geom_valida.get(centro, 0)
        print(f"   - {centro}: {validas}/{total} con geometría válida")
    
    print(f"\n5. RESUMEN:")
    print(f"   - Total en endpoint: {len(features)}")
    print(f"   - Con geometría válida: {len(con_geometria_valida)}")
    print(f"   - Diferencia (sin coordenadas válidas): {len(features) - len(con_geometria_valida)}")
    print(f"\n   💡 Si el frontend filtra por geometría válida, debería mostrar: {len(con_geometria_valida)}")
    
    print("\n" + "=" * 80)
    print("FIN DEL ANÁLISIS")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(analizar_geometrias())
