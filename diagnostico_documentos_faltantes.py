"""
Diagnóstico de documentos faltantes en endpoints de Unidades de Proyecto

Este script compara:
1. Cantidad total de documentos en Firestore
2. Cantidad de documentos devueltos por cada endpoint
3. Presupuesto total en Firestore vs API
"""

import asyncio
from database.firebase_config import get_firestore_client
from api.scripts.unidades_proyecto import (
    get_unidades_proyecto_geometry,
    get_unidades_proyecto_attributes
)

def format_currency(value):
    """Formatear números como moneda"""
    if value is None:
        return "N/A"
    return f"${value:,.0f}"

async def diagnosticar_documentos_faltantes():
    """Diagnóstico completo de documentos faltantes"""
    
    print("=" * 80)
    print("DIAGNÓSTICO: Documentos Faltantes en API de Unidades de Proyecto")
    print("=" * 80)
    print()
    
    # 1. Contar documentos directamente en Firestore
    print("📊 PASO 1: Contando documentos en Firestore...")
    db = get_firestore_client()
    
    if db is None:
        print("❌ ERROR: No se pudo conectar a Firestore")
        return
    
    collection_ref = db.collection('unidades_proyecto')
    
    # Contar todos los documentos
    docs = collection_ref.stream()
    firestore_docs = []
    total_presupuesto_firestore = 0
    docs_sin_presupuesto = 0
    docs_sin_intervenciones = 0
    
    print("   Procesando documentos de Firestore...")
    for doc in docs:
        doc_data = doc.to_dict()
        firestore_docs.append({
            'id': doc.id,
            'upid': doc_data.get('upid'),
            'presupuesto_base': doc_data.get('presupuesto_base'),
            'tiene_intervenciones': 'intervenciones' in doc_data and isinstance(doc_data.get('intervenciones'), list) and len(doc_data.get('intervenciones', [])) > 0
        })
        
        # Calcular presupuesto
        presupuesto = doc_data.get('presupuesto_base')
        if presupuesto:
            try:
                if isinstance(presupuesto, (int, float)):
                    total_presupuesto_firestore += float(presupuesto)
                elif isinstance(presupuesto, str):
                    # Limpiar y convertir
                    cleaned = presupuesto.replace(',', '').replace('$', '').replace(' ', '').strip()
                    if cleaned:
                        total_presupuesto_firestore += float(cleaned)
            except:
                pass
        else:
            docs_sin_presupuesto += 1
        
        # Verificar intervenciones
        if not doc_data.get('intervenciones') or not isinstance(doc_data.get('intervenciones'), list) or len(doc_data.get('intervenciones', [])) == 0:
            docs_sin_intervenciones += 1
    
    total_firestore = len(firestore_docs)
    
    print()
    print(f"✅ Total documentos en Firestore: {total_firestore}")
    print(f"   - Documentos sin presupuesto_base: {docs_sin_presupuesto}")
    print(f"   - Documentos sin intervenciones: {docs_sin_intervenciones}")
    print(f"   - Presupuesto total en Firestore: {format_currency(total_presupuesto_firestore)}")
    print()
    
    # 2. Contar documentos devueltos por endpoint /geometry
    print("📊 PASO 2: Consultando endpoint /unidades-proyecto/geometry...")
    geometry_result = await get_unidades_proyecto_geometry(filters={})
    
    if geometry_result.get("type") == "FeatureCollection":
        geometry_features = geometry_result.get("features", [])
        total_geometry = len(geometry_features)
        
        # Calcular presupuesto en geometry
        total_presupuesto_geometry = 0
        for feature in geometry_features:
            props = feature.get('properties', {})
            intervenciones = props.get('intervenciones', [])
            for interv in intervenciones:
                if isinstance(interv, dict):
                    presupuesto = interv.get('presupuesto_base')
                    if presupuesto:
                        try:
                            total_presupuesto_geometry += float(presupuesto)
                        except:
                            pass
        
        print(f"✅ Total documentos en /geometry: {total_geometry}")
        print(f"   - Presupuesto total en /geometry: {format_currency(total_presupuesto_geometry)}")
    else:
        total_geometry = 0
        total_presupuesto_geometry = 0
        print(f"❌ Error en /geometry: {geometry_result.get('error', 'Desconocido')}")
    
    print()
    
    # 3. Contar documentos devueltos por endpoint /attributes
    print("📊 PASO 3: Consultando endpoint /unidades-proyecto/attributes...")
    attributes_result = await get_unidades_proyecto_attributes(filters={}, limit=None)
    
    if attributes_result.get("success"):
        attributes_data = attributes_result.get("data", [])
        total_attributes = len(attributes_data)
        
        # Calcular presupuesto en attributes
        total_presupuesto_attributes = 0
        for record in attributes_data:
            intervenciones = record.get('intervenciones', [])
            for interv in intervenciones:
                if isinstance(interv, dict):
                    presupuesto = interv.get('presupuesto_base')
                    if presupuesto:
                        try:
                            total_presupuesto_attributes += float(presupuesto)
                        except:
                            pass
        
        print(f"✅ Total documentos en /attributes: {total_attributes}")
        print(f"   - Presupuesto total en /attributes: {format_currency(total_presupuesto_attributes)}")
    else:
        total_attributes = 0
        total_presupuesto_attributes = 0
        print(f"❌ Error en /attributes: {attributes_result.get('error', 'Desconocido')}")
    
    print()
    print("=" * 80)
    print("RESUMEN COMPARATIVO")
    print("=" * 80)
    print()
    
    # Comparación de documentos
    print("📊 DOCUMENTOS:")
    print(f"   Firestore:    {total_firestore:,}")
    print(f"   /geometry:    {total_geometry:,}")
    print(f"   /attributes:  {total_attributes:,}")
    
    missing_geometry = total_firestore - total_geometry
    missing_attributes = total_firestore - total_attributes
    
    if missing_geometry > 0:
        print(f"   ❌ FALTANTES en /geometry:    {missing_geometry:,} documentos ({missing_geometry/total_firestore*100:.1f}%)")
    else:
        print(f"   ✅ /geometry está completo")
    
    if missing_attributes > 0:
        print(f"   ❌ FALTANTES en /attributes:  {missing_attributes:,} documentos ({missing_attributes/total_firestore*100:.1f}%)")
    else:
        print(f"   ✅ /attributes está completo")
    
    print()
    
    # Comparación de presupuestos
    print("💰 PRESUPUESTOS:")
    print(f"   Firestore:    {format_currency(total_presupuesto_firestore)}")
    print(f"   /geometry:    {format_currency(total_presupuesto_geometry)}")
    print(f"   /attributes:  {format_currency(total_presupuesto_attributes)}")
    
    diff_geometry = total_presupuesto_firestore - total_presupuesto_geometry
    diff_attributes = total_presupuesto_firestore - total_presupuesto_attributes
    
    if abs(diff_geometry) > 1000000:  # Diferencia mayor a 1 millón
        print(f"   ❌ DIFERENCIA en /geometry:   {format_currency(diff_geometry)}")
    else:
        print(f"   ✅ /geometry está completo en presupuesto")
    
    if abs(diff_attributes) > 1000000:
        print(f"   ❌ DIFERENCIA en /attributes: {format_currency(diff_attributes)}")
    else:
        print(f"   ✅ /attributes está completo en presupuesto")
    
    print()
    print("=" * 80)
    print("ANÁLISIS DE CAUSAS POSIBLES")
    print("=" * 80)
    print()
    
    # Análisis detallado
    if missing_geometry > 0 or missing_attributes > 0:
        print("🔍 POSIBLES CAUSAS:")
        print()
        
        # Verificar límites implícitos
        print("1. LÍMITES IMPLÍCITOS:")
        print(f"   - Total en Firestore: {total_firestore}")
        print(f"   - ¿Hay un límite de ~1500? {total_firestore > 1500 and total_geometry < 1500}")
        print()
        
        # Verificar documentos sin intervenciones
        print("2. DOCUMENTOS SIN INTERVENCIONES:")
        print(f"   - Docs sin intervenciones: {docs_sin_intervenciones}")
        print(f"   - ¿Coincide con faltantes? {abs(docs_sin_intervenciones - missing_geometry) < 10}")
        print()
        
        # Verificar documentos sin presupuesto
        print("3. DOCUMENTOS SIN PRESUPUESTO:")
        print(f"   - Docs sin presupuesto_base: {docs_sin_presupuesto}")
        print()
        
        # Identificar documentos específicos faltantes
        if total_geometry < total_firestore:
            print("4. IDENTIFICANDO DOCUMENTOS FALTANTES...")
            geometry_upids = set()
            for feature in geometry_features:
                upid = feature.get('properties', {}).get('upid')
                if upid:
                    geometry_upids.add(upid)
            
            firestore_upids = set(doc['upid'] for doc in firestore_docs if doc['upid'])
            missing_upids = firestore_upids - geometry_upids
            
            print(f"   - Total UPIDs faltantes: {len(missing_upids)}")
            if len(missing_upids) > 0:
                print(f"   - Primeros 10 UPIDs faltantes:")
                for upid in list(missing_upids)[:10]:
                    # Encontrar el documento en Firestore
                    doc_info = next((d for d in firestore_docs if d['upid'] == upid), None)
                    if doc_info:
                        tiene_presupuesto = "Sí" if doc_info['presupuesto_base'] else "No"
                        tiene_intervenciones = "Sí" if doc_info['tiene_intervenciones'] else "No"
                        print(f"     • {upid}: Presupuesto={tiene_presupuesto}, Intervenciones={tiene_intervenciones}")
    else:
        print("✅ NO HAY DOCUMENTOS FALTANTES - La API está exponiendo todos los documentos")
    
    print()
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(diagnosticar_documentos_faltantes())
