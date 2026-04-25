"""
Análisis comparativo detallado de frentes activos - Estado actual
"""
import asyncio

async def analisis_comparativo():
    """Análisis comparativo del estado actual"""
    
    print("=" * 100)
    print("VERIFICACIÓN COMPLETA: ESTADO ACTUAL DE FRENTES ACTIVOS")
    print("=" * 100)
    
    from api.scripts.unidades_proyecto import get_frentes_activos
    
    result = await get_frentes_activos()
    features = result.get('features', [])
    
    print(f"\n{'='*100}")
    print(f"1. RESUMEN GENERAL")
    print(f"{'='*100}")
    print(f"Total UNIDADES: {len(features)}")
    print(f"Total INTERVENCIONES: {result.get('properties', {}).get('total_frentes_activos')}")
    
    # Análisis por geometría
    con_geom = [f for f in features if f['properties'].get('has_valid_geometry', False)]
    sin_geom = [f for f in features if not f['properties'].get('has_valid_geometry', False)]
    
    print(f"\n{'='*100}")
    print(f"2. DISTRIBUCIÓN POR GEOMETRÍA")
    print(f"{'='*100}")
    print(f"✅ Con geometría válida: {len(con_geom)}")
    print(f"❌ Sin geometría válida: {len(sin_geom)}")
    
    # Análisis por centro gestor
    print(f"\n{'='*100}")
    print(f"3. DISTRIBUCIÓN POR CENTRO GESTOR")
    print(f"{'='*100}")
    
    centros = {}
    for f in features:
        props = f['properties']
        centro = props.get('nombre_centro_gestor', 'Sin centro')
        has_valid = props.get('has_valid_geometry', False)
        
        if centro not in centros:
            centros[centro] = {'total': 0, 'con_geom': 0, 'sin_geom': 0, 'intervenciones': 0}
        
        centros[centro]['total'] += 1
        centros[centro]['intervenciones'] += len(props.get('intervenciones', []))
        
        if has_valid:
            centros[centro]['con_geom'] += 1
        else:
            centros[centro]['sin_geom'] += 1
    
    for centro in sorted(centros.keys()):
        info = centros[centro]
        print(f"\n📍 {centro}")
        print(f"   Total: {info['total']} unidades | {info['intervenciones']} intervenciones")
        print(f"   ✅ Con geometría: {info['con_geom']} | ❌ Sin geometría: {info['sin_geom']}")
    
    # Detallar los que NO tienen geometría válida
    print(f"\n{'='*100}")
    print(f"4. DETALLE: UNIDADES SIN GEOMETRÍA VÁLIDA")
    print(f"{'='*100}")
    
    # Agrupar por centro
    sin_geom_por_centro = {}
    for f in sin_geom:
        props = f['properties']
        centro = props.get('nombre_centro_gestor', 'Sin centro')
        if centro not in sin_geom_por_centro:
            sin_geom_por_centro[centro] = []
        sin_geom_por_centro[centro].append(props)
    
    for centro in sorted(sin_geom_por_centro.keys()):
        unidades = sin_geom_por_centro[centro]
        print(f"\n📍 {centro} ({len(unidades)} unidades)")
        print(f"   {'-'*90}")
        for props in sorted(unidades, key=lambda x: x.get('upid', '')):
            intervs = props.get('intervenciones', [])
            print(f"   • {props.get('upid')} - {props.get('nombre_up')} ({len(intervs)} intervenciones)")
    
    # Verificar Secretaría de Salud específicamente
    print(f"\n{'='*100}")
    print(f"5. VERIFICACIÓN ESPECIAL: SECRETARÍA DE SALUD PÚBLICA")
    print(f"{'='*100}")
    
    salud_features = [f for f in features 
                      if 'Salud' in f['properties'].get('nombre_centro_gestor', '')]
    
    print(f"Total unidades de Secretaría de Salud: {len(salud_features)}")
    
    salud_con_geom = [f for f in salud_features 
                      if f['properties'].get('has_valid_geometry', False)]
    salud_sin_geom = [f for f in salud_features 
                      if not f['properties'].get('has_valid_geometry', False)]
    
    print(f"✅ Con geometría válida: {len(salud_con_geom)}")
    print(f"❌ Sin geometría válida: {len(salud_sin_geom)}")
    
    if salud_sin_geom:
        print(f"\nUnidades de Salud SIN geometría válida:")
        for f in salud_sin_geom:
            props = f['properties']
            print(f"   • {props.get('upid')} - {props.get('nombre_up')}")
    
    # Lista completa de UPIDs sin geometría
    print(f"\n{'='*100}")
    print(f"6. LISTA DE UPIDs SIN GEOMETRÍA VÁLIDA")
    print(f"{'='*100}")
    
    upids_sin_geom = sorted([f['properties']['upid'] for f in sin_geom])
    print(f"Total: {len(upids_sin_geom)}")
    print(f"\n{', '.join(upids_sin_geom)}")
    
    # Explicación para el frontend
    print(f"\n{'='*100}")
    print(f"7. ANÁLISIS: ¿POR QUÉ EL FRONTEND MUESTRA 56?")
    print(f"{'='*100}")
    
    print(f"""
Estado actual:
   - Total en endpoint: {len(features)}
   - Con geometría válida: {len(con_geom)}
   - Sin geometría válida: {len(sin_geom)}
   - Frontend muestra: 56
   
Opciones de filtrado:
   1. Si filtra por has_valid_geometry=true → debería mostrar {len(con_geom)}
   2. Si excluye solo ciertos centros gestores → 56
   3. Si tiene lógica personalizada → 56
   
Diferencia: {len(features)} - 56 = {len(features) - 56} unidades no mostradas

Posibilidad: El frontend está excluyendo {len(features) - 56} unidades específicas.
""")
    
    # Verificar campos en respuesta
    print(f"{'='*100}")
    print(f"8. VERIFICACIÓN DE CAMPOS EN RESPUESTA")
    print(f"{'='*100}")
    
    if features:
        ejemplo = features[0]['properties']
        campos = sorted(ejemplo.keys())
        
        print(f"Campos presentes en properties:")
        for campo in campos:
            if campo != 'intervenciones':
                print(f"   • {campo}")
        
        print(f"\nCampos que NO deben estar presentes:")
        campos_prohibidos = ['departamento', 'municipio', 'geometry_type', 
                            'has_geometry', 'centros_gravedad']
        for campo in campos_prohibidos:
            if campo in ejemplo:
                print(f"   ❌ {campo}: PRESENTE")
            else:
                print(f"   ✅ {campo}: NO PRESENTE")
        
        print(f"\nCampo permitido:")
        if 'has_valid_geometry' in ejemplo:
            print(f"   ✅ has_valid_geometry: PRESENTE")
        else:
            print(f"   ❌ has_valid_geometry: NO PRESENTE")
    
    print(f"\n{'='*100}")
    print("FIN DE LA VERIFICACIÓN")
    print(f"{'='*100}")

if __name__ == "__main__":
    asyncio.run(analisis_comparativo())
