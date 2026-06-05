"""
Script de diagnóstico para revisar el endpoint /frentes-activos
"""
import asyncio
import json
from database.firebase_config import get_firestore_client

async def diagnosticar_frentes_activos():
    """Diagnosticar datos de frentes activos"""
    
    print("=" * 80)
    print("DIAGNÓSTICO: FRENTES ACTIVOS")
    print("=" * 80)
    
    db = get_firestore_client()
    if not db:
        print("❌ No se pudo conectar a Firestore")
        return
    
    # Buscar registros de Secretaría de Salud Pública
    print("\n1. Buscando registros de 'Secretaría de Salud Pública'...")
    
    query = db.collection('unidades_proyecto')
    docs = list(query.stream())
    
    print(f"   Total documentos en colección: {len(docs)}")
    
    # Filtrar por Secretaría de Salud Pública
    salud_docs = []
    for doc in docs:
        doc_data = doc.to_dict()
        nombre_centro = (doc_data.get('nombre_centro_gestor') or 
                        doc_data.get('properties', {}).get('nombre_centro_gestor'))
        
        if nombre_centro and 'Salud' in nombre_centro:
            salud_docs.append((doc.id, doc_data))
    
    print(f"   Documentos de Secretaría de Salud: {len(salud_docs)}")
    
    # Revisar estructura de intervenciones
    print("\n2. Analizando estructura de intervenciones...")
    
    for i, (doc_id, doc_data) in enumerate(salud_docs[:5]):  # Solo primeros 5
        print(f"\n   Doc {i+1}: {doc_id}")
        print(f"   UPID: {doc_data.get('upid', 'N/A')}")
        print(f"   Nombre centro: {doc_data.get('nombre_centro_gestor', 'N/A')}")
        
        # Revisar si tiene intervenciones
        if 'intervenciones' in doc_data:
            intervenciones = doc_data['intervenciones']
            print(f"   Tiene campo 'intervenciones': {len(intervenciones)} items")
            
            # Analizar primera intervención
            if intervenciones:
                primera = intervenciones[0]
                if isinstance(primera, str):
                    print(f"   Primera intervención es STRING")
                    try:
                        import json
                        parsed = json.loads(primera)
                        print(f"   Después de parsear:")
                        print(f"      - frente_activo: {parsed.get('frente_activo', 'N/A')}")
                        print(f"      - estado: {parsed.get('estado', 'N/A')}")
                    except Exception as e:
                        print(f"   ⚠️ Error parseando: {e}")
                else:
                    print(f"   Primera intervención es DICT")
                    print(f"      - frente_activo: {primera.get('frente_activo', 'N/A')}")
                    print(f"      - estado: {primera.get('estado', 'N/A')}")
        else:
            print(f"   ❌ NO tiene campo 'intervenciones'")
    
    # Contar frentes activos
    print("\n3. Contando frentes activos en Secretaría de Salud...")
    
    total_con_frente_activo = 0
    total_intervenciones_frente_activo = 0
    
    for doc_id, doc_data in salud_docs:
        if 'intervenciones' in doc_data:
            intervenciones = doc_data['intervenciones']
            tiene_frente = False
            
            for interv in intervenciones:
                # Parsear si es string
                if isinstance(interv, str):
                    try:
                        interv = json.loads(interv)
                    except:
                        continue
                
                # Revisar frente_activo
                frente_activo = interv.get('frente_activo')
                if frente_activo == 'Frente activo':
                    tiene_frente = True
                    total_intervenciones_frente_activo += 1
            
            if tiene_frente:
                total_con_frente_activo += 1
    
    print(f"   Unidades con al menos 1 frente activo: {total_con_frente_activo}")
    print(f"   Total intervenciones con frente activo: {total_intervenciones_frente_activo}")
    
    # Probar la función get_frentes_activos
    print("\n4. Probando función get_frentes_activos()...")
    
    try:
        from api.scripts.unidades_proyecto import get_frentes_activos
        result = await get_frentes_activos()
        
        print(f"   Type: {result.get('type')}")
        print(f"   Features: {len(result.get('features', []))}")
        print(f"   Total frentes activos: {result.get('properties', {}).get('total_frentes_activos')}")
        print(f"   Total unidades con frentes: {result.get('properties', {}).get('total_unidades_con_frentes')}")
        
        # Revisar si hay features de Secretaría de Salud
        features = result.get('features', [])
        salud_features = []
        for f in features:
            props = f.get('properties', {})
            nombre_centro = props.get('nombre_centro_gestor', '')
            if 'Salud' in nombre_centro:
                salud_features.append(f)
        
        print(f"\n   Features de Secretaría de Salud en resultado: {len(salud_features)}")
        
        # Mostrar campos de un feature de ejemplo
        if salud_features:
            ejemplo = salud_features[0]['properties']
            print(f"\n   Campos en properties del feature (ejemplo):")
            for key in sorted(ejemplo.keys()):
                if key != 'intervenciones':  # No mostrar intervenciones completas
                    print(f"      - {key}: {ejemplo.get(key)}")
            
            # Mostrar campos problemáticos
            print(f"\n   🔍 CAMPOS PROBLEMÁTICOS:")
            print(f"      - departamento: {ejemplo.get('departamento')}")
            print(f"      - municipio: {ejemplo.get('municipio')}")
            print(f"      - geometry_type: {ejemplo.get('geometry_type')}")
            print(f"      - has_geometry: {ejemplo.get('has_geometry')}")
            print(f"      - has_valid_geometry: {ejemplo.get('has_valid_geometry')}")
            print(f"      - centros_gravedad: {ejemplo.get('centros_gravedad')}")
    
    except Exception as e:
        print(f"   ❌ Error probando función: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("FIN DEL DIAGNÓSTICO")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(diagnosticar_frentes_activos())
