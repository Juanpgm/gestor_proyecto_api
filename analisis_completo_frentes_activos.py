"""
Análisis completo de frentes activos: todas las intervenciones y geometrías
"""
import asyncio
import json

async def analisis_completo():
    """Análisis detallado de todas las intervenciones con frente activo"""
    
    print("=" * 100)
    print("ANÁLISIS COMPLETO: FRENTES ACTIVOS")
    print("=" * 100)
    
    from api.scripts.unidades_proyecto import get_frentes_activos
    
    result = await get_frentes_activos()
    features = result.get('features', [])
    
    print(f"\n{'='*100}")
    print(f"RESUMEN GENERAL")
    print(f"{'='*100}")
    print(f"Total UNIDADES con frentes activos: {len(features)}")
    print(f"Total INTERVENCIONES con frente activo: {result.get('properties', {}).get('total_frentes_activos')}")
    
    # Separar por geometría válida
    con_geometria_valida = []
    sin_geometria_valida = []
    
    total_intervenciones_con_geom = 0
    total_intervenciones_sin_geom = 0
    
    for f in features:
        props = f.get('properties', {})
        has_valid = props.get('has_valid_geometry', False)
        intervenciones = props.get('intervenciones', [])
        
        if has_valid:
            con_geometria_valida.append(f)
            total_intervenciones_con_geom += len(intervenciones)
        else:
            sin_geometria_valida.append(f)
            total_intervenciones_sin_geom += len(intervenciones)
    
    print(f"\n{'='*100}")
    print(f"DISTRIBUCIÓN POR GEOMETRÍA")
    print(f"{'='*100}")
    print(f"✅ UNIDADES con geometría válida: {len(con_geometria_valida)} ({total_intervenciones_con_geom} intervenciones)")
    print(f"❌ UNIDADES sin geometría válida: {len(sin_geometria_valida)} ({total_intervenciones_sin_geom} intervenciones)")
    
    # Detallar TODAS las unidades con geometría válida
    print(f"\n{'='*100}")
    print(f"DETALLE: UNIDADES CON GEOMETRÍA VÁLIDA ({len(con_geometria_valida)} unidades)")
    print(f"{'='*100}")
    
    for i, f in enumerate(con_geometria_valida, 1):
        props = f.get('properties', {})
        geom = f.get('geometry', {})
        coords = geom.get('coordinates', [])
        intervenciones = props.get('intervenciones', [])
        
        print(f"\n{i}. {props.get('upid')} - {props.get('nombre_up')}")
        print(f"   Centro Gestor: {props.get('nombre_centro_gestor')}")
        print(f"   Ubicación: {props.get('barrio_vereda')} - {props.get('comuna_corregimiento')}")
        print(f"   Coordenadas: {coords}")
        print(f"   Intervenciones con frente activo ({len(intervenciones)}):")
        for j, interv in enumerate(intervenciones, 1):
            print(f"      {j}) {interv.get('tipo_intervencion')} - {interv.get('estado')}")
            print(f"         Año: {interv.get('ano')} | Frente: {interv.get('frente_activo')}")
    
    # Detallar TODAS las unidades SIN geometría válida
    print(f"\n{'='*100}")
    print(f"DETALLE: UNIDADES SIN GEOMETRÍA VÁLIDA ({len(sin_geometria_valida)} unidades)")
    print(f"{'='*100}")
    print(f"⚠️  ESTAS UNIDADES NO SE PUEDEN VISUALIZAR EN EL MAPA")
    print(f"{'='*100}")
    
    # Agrupar por centro gestor
    por_centro = {}
    for f in sin_geometria_valida:
        props = f.get('properties', {})
        centro = props.get('nombre_centro_gestor', 'Sin centro')
        if centro not in por_centro:
            por_centro[centro] = []
        por_centro[centro].append(f)
    
    for centro in sorted(por_centro.keys()):
        unidades = por_centro[centro]
        total_intervs = sum(len(u['properties'].get('intervenciones', [])) for u in unidades)
        
        print(f"\n📍 {centro}")
        print(f"   Total unidades: {len(unidades)} | Total intervenciones: {total_intervs}")
        print(f"   {'-'*90}")
        
        for i, f in enumerate(unidades, 1):
            props = f.get('properties', {})
            geom = f.get('geometry', {})
            coords = geom.get('coordinates', [])
            intervenciones = props.get('intervenciones', [])
            
            print(f"\n   {i}. {props.get('upid')} - {props.get('nombre_up')}")
            print(f"      Ubicación: {props.get('barrio_vereda')} - {props.get('comuna_corregimiento')}")
            print(f"      Coordenadas: {coords} ⚠️  [SIN COORDENADAS REALES]")
            print(f"      Intervenciones con frente activo ({len(intervenciones)}):")
            for j, interv in enumerate(intervenciones, 1):
                print(f"         {j}) {interv.get('tipo_intervencion')} - {interv.get('estado')}")
                print(f"            Año: {interv.get('ano')} | Frente: {interv.get('frente_activo')}")
    
    # Exportar lista de UPIDs sin geometría
    print(f"\n{'='*100}")
    print(f"LISTA DE UPIDs SIN GEOMETRÍA VÁLIDA (para corrección)")
    print(f"{'='*100}")
    
    upids_sin_geom = [f['properties']['upid'] for f in sin_geometria_valida]
    print(f"Total: {len(upids_sin_geom)} unidades")
    print(f"\nUPIDs: {', '.join(sorted(upids_sin_geom))}")
    
    # Explicación del frontend
    print(f"\n{'='*100}")
    print(f"EXPLICACIÓN: ¿POR QUÉ EL FRONTEND MUESTRA MENOS?")
    print(f"{'='*100}")
    print(f"""
El frontend muestra 56 porque está filtrando las unidades sin coordenadas válidas.

📊 MATEMÁTICA:
   - Total unidades en endpoint: {len(features)}
   - Unidades con geometría válida: {len(con_geometria_valida)}
   - Unidades sin geometría válida: {len(sin_geometria_valida)}
   - Lo que muestra el frontend: 56

💡 ANÁLISIS:
   Si el frontend filtra por has_valid_geometry=true, debería mostrar: {len(con_geometria_valida)}
   Pero muestra 56, lo que sugiere que:
   
   Opción 1: Está excluyendo solo las 9 de "Secretaría del Deporte" (65 - 9 = 56)
   Opción 2: Tiene alguna lógica personalizada que resulta en 56
   
⚠️  IMPORTANTE: Son {result.get('properties', {}).get('total_frentes_activos')} INTERVENCIONES,
   distribuidas en {len(features)} UNIDADES.
   
   Una unidad puede tener múltiples intervenciones con frente activo.
   El mapa muestra UNIDADES (puntos en el mapa), no intervenciones individuales.
""")
    
    print(f"{'='*100}")
    print("FIN DEL ANÁLISIS")
    print(f"{'='*100}")

if __name__ == "__main__":
    asyncio.run(analisis_completo())
