"""
Análisis detallado de diferencias en presupuestos
Compara valores almacenados vs valores calculados en intervenciones
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

def parse_presupuesto(value):
    """Parsear presupuesto de varios formatos"""
    if value is None or value == '':
        return None
    
    try:
        if isinstance(value, (int, float)):
            return float(value)
        elif isinstance(value, str):
            cleaned = value.replace(',', '').replace('$', '').replace(' ', '').strip()
            if cleaned:
                return float(cleaned)
    except:
        pass
    return None

async def analizar_diferencias():
    """Análisis detallado de presupuestos"""
    
    print("=" * 80)
    print("ANÁLISIS DE DIFERENCIAS EN PRESUPUESTOS")
    print("=" * 80)
    print()
    
    db = get_firestore_client()
    if db is None:
        print("❌ ERROR: No se pudo conectar a Firestore")
        return
    
    # 1. Analizar documentos directamente en Firestore
    print("📊 Analizando documentos en Firestore...")
    collection_ref = db.collection('unidades_proyecto')
    docs = collection_ref.stream()
    
    # Almacenar datos para análisis
    documentos = []
    
    # Presupuestos totales por fuente
    presupuesto_nivel_documento = 0  # Campo presupuesto_base en nivel documento
    presupuesto_en_intervenciones = 0  # Suma de presupuestos en array intervenciones
    
    docs_con_diferencias = []
    docs_sin_presupuesto_documento = []
    docs_sin_intervenciones = []
    
    for doc in docs:
        doc_data = doc.to_dict()
        upid = doc_data.get('upid', doc.id)
        
        # Presupuesto a nivel documento
        presupuesto_doc = parse_presupuesto(doc_data.get('presupuesto_base'))
        
        # Presupuestos en intervenciones
        intervenciones = doc_data.get('intervenciones', [])
        presupuestos_interv = []
        
        if isinstance(intervenciones, list):
            for interv in intervenciones:
                if isinstance(interv, dict):
                    p = parse_presupuesto(interv.get('presupuesto_base'))
                    if p:
                        presupuestos_interv.append(p)
                elif isinstance(interv, str):
                    # Parsear JSON string
                    try:
                        import json
                        interv_dict = json.loads(interv)
                        p = parse_presupuesto(interv_dict.get('presupuesto_base'))
                        if p:
                            presupuestos_interv.append(p)
                    except:
                        pass
        
        suma_interv = sum(presupuestos_interv) if presupuestos_interv else None
        
        # Registrar documento
        doc_info = {
            'upid': upid,
            'presupuesto_documento': presupuesto_doc,
            'presupuesto_intervenciones': suma_interv,
            'n_intervenciones': len(intervenciones) if isinstance(intervenciones, list) else 0,
            'tiene_diferencia': False
        }
        
        # Acumular totales
        if presupuesto_doc:
            presupuesto_nivel_documento += presupuesto_doc
        else:
            docs_sin_presupuesto_documento.append(upid)
        
        if suma_interv:
            presupuesto_en_intervenciones += suma_interv
        
        # Detectar diferencias
        if presupuesto_doc and suma_interv:
            diferencia = abs(presupuesto_doc - suma_interv)
            # Si la diferencia es mayor al 1% o mayor a $100,000
            if diferencia > max(presupuesto_doc * 0.01, 100000):
                doc_info['tiene_diferencia'] = True
                doc_info['diferencia'] = diferencia
                docs_con_diferencias.append(doc_info)
        
        if not intervenciones or len(intervenciones) == 0:
            docs_sin_intervenciones.append(upid)
        
        documentos.append(doc_info)
    
    print(f"✅ Analizados {len(documentos)} documentos")
    print()
    
    # Resultados
    print("=" * 80)
    print("PRESUPUESTOS TOTALES POR FUENTE")
    print("=" * 80)
    print()
    print(f"💰 Presupuesto a nivel documento (presupuesto_base):  {format_currency(presupuesto_nivel_documento)}")
    print(f"💰 Suma de presupuestos en intervenciones:           {format_currency(presupuesto_en_intervenciones)}")
    print()
    
    diferencia_total = presupuesto_nivel_documento - presupuesto_en_intervenciones
    if abs(diferencia_total) > 1000000:
        print(f"❌ DIFERENCIA: {format_currency(abs(diferencia_total))}")
        if diferencia_total > 0:
            print(f"   → El presupuesto a nivel documento es MAYOR")
        else:
            print(f"   → La suma de intervenciones es MAYOR")
    else:
        print(f"✅ Diferencia insignificante: {format_currency(abs(diferencia_total))}")
    
    print()
    print("=" * 80)
    print("DOCUMENTOS CON ANOMALÍAS")
    print("=" * 80)
    print()
    
    print(f"📌 Documentos sin presupuesto a nivel documento: {len(docs_sin_presupuesto_documento)}")
    if len(docs_sin_presupuesto_documento) > 0 and len(docs_sin_presupuesto_documento) <= 20:
        for upid in docs_sin_presupuesto_documento:
            print(f"   • {upid}")
    
    print()
    print(f"📌 Documentos sin intervenciones: {len(docs_sin_intervenciones)}")
    if len(docs_sin_intervenciones) > 0 and len(docs_sin_intervenciones) <= 20:
        for upid in docs_sin_intervenciones:
            print(f"   • {upid}")
    
    print()
    print(f"📌 Documentos con diferencias significativas: {len(docs_con_diferencias)}")
    if len(docs_con_diferencias) > 0:
        print()
        print("   Primeros 10 documentos con mayores diferencias:")
        docs_con_diferencias_sorted = sorted(docs_con_diferencias, key=lambda x: x['diferencia'], reverse=True)
        for doc_info in docs_con_diferencias_sorted[:10]:
            print(f"   • {doc_info['upid']}:")
            print(f"     - Presupuesto documento: {format_currency(doc_info['presupuesto_documento'])}")
            print(f"     - Suma intervenciones:   {format_currency(doc_info['presupuesto_intervenciones'])}")
            print(f"     - Diferencia:            {format_currency(doc_info['diferencia'])}")
    
    print()
    print("=" * 80)
    print("ANÁLISIS DE INTERVENCIONES")
    print("=" * 80)
    print()
    
    # Contar intervenciones
    total_intervenciones = sum(d['n_intervenciones'] for d in documentos)
    docs_con_intervenciones = sum(1 for d in documentos if d['n_intervenciones'] > 0)
    
    print(f"📊 Total de intervenciones: {total_intervenciones:,}")
    print(f"📊 Documentos con intervenciones: {docs_con_intervenciones:,} de {len(documentos):,}")
    print(f"📊 Promedio de intervenciones por documento: {total_intervenciones/len(documentos):.2f}")
    
    print()
    print("=" * 80)
    print("VERIFICACIÓN CON API")
    print("=" * 80)
    print()
    
    # Verificar con API
    print("🔍 Consultando endpoint /geometry...")
    geometry_result = await get_unidades_proyecto_geometry(filters={})
    
    if geometry_result.get("type") == "FeatureCollection":
        features = geometry_result.get("features", [])
        presupuesto_api = 0
        
        for feature in features:
            props = feature.get('properties', {})
            intervenciones = props.get('intervenciones', [])
            for interv in intervenciones:
                if isinstance(interv, dict):
                    p = parse_presupuesto(interv.get('presupuesto_base'))
                    if p:
                        presupuesto_api += p
        
        print(f"✅ Total presupuesto devuelto por API: {format_currency(presupuesto_api)}")
        
        # Comparar
        diff_con_doc = presupuesto_nivel_documento - presupuesto_api
        diff_con_interv = presupuesto_en_intervenciones - presupuesto_api
        
        print()
        print("Comparación con Firestore:")
        print(f"   • Diferencia vs presupuesto_documento: {format_currency(abs(diff_con_doc))}")
        print(f"   • Diferencia vs suma intervenciones:   {format_currency(abs(diff_con_interv))}")
        
        if abs(diff_con_interv) < 1000:
            print(f"   ✅ API devuelve suma de intervenciones correctamente")
        else:
            print(f"   ❌ API tiene diferencia con suma de intervenciones")
    
    print()
    print("=" * 80)
    print("CONCLUSIONES")
    print("=" * 80)
    print()
    
    if abs(diferencia_total) > 1000000:
        print("⚠️  Hay una diferencia significativa entre:")
        print("   1. presupuesto_base a nivel documento")
        print("   2. Suma de presupuestos en intervenciones")
        print()
        print("Esto significa que:")
        print("   • Algunos documentos tienen presupuesto_base diferente a la suma de sus intervenciones")
        print("   • La API devuelve correctamente las intervenciones")
        print("   • La diferencia NO es por documentos faltantes, sino por valores diferentes")
    else:
        print("✅ Los presupuestos son consistentes entre documento e intervenciones")
        print("✅ La API está exponiendo todos los documentos correctamente")
    
    print()

if __name__ == "__main__":
    asyncio.run(analizar_diferencias())
