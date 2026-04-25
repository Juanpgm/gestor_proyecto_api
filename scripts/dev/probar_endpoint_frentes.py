"""
Script para probar directamente el endpoint frentes-activos
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api.scripts.unidades_proyecto import get_frentes_activos


async def probar_endpoint():
    """Probar el endpoint frentes-activos directamente"""
    
    print("🔄 Llamando a get_frentes_activos()...\n")
    
    result = await get_frentes_activos()
    
    print(f"{'='*80}")
    print(f"📊 RESULTADO DEL ENDPOINT /frentes-activos")
    print(f"{'='*80}\n")
    
    if result.get("type") == "FeatureCollection":
        features = result.get("features", [])
        properties = result.get("properties", {})
        
        print(f"📈 PROPIEDADES GLOBALES:")
        print(f"   • Total unidades con frentes: {properties.get('total_unidades_con_frentes', 'N/A')}")
        print(f"   • Total frentes activos: {properties.get('total_frentes_activos', 'N/A')}")
        print(f"   • Success: {properties.get('success', 'N/A')}")
        print(f"   • Filtros aplicados: {properties.get('filters', {})}")
        
        print(f"\n📋 FEATURES:")
        print(f"   • Cantidad de features: {len(features)}")
        
        # Analizar features en detalle
        total_intervenciones_en_features = 0
        intervenciones_con_frente_activo = 0
        intervenciones_sin_frente_activo = 0
        features_con_problema = []
        
        for i, feature in enumerate(features):
            props = feature.get("properties", {})
            intervenciones = props.get("intervenciones", [])
            total_intervenciones_en_features += len(intervenciones)
            
            # Contar cuántas tienen frente activo
            con_frente = 0
            sin_frente = 0
            for interv in intervenciones:
                if interv.get("frente_activo") == "Frente activo":
                    con_frente += 1
                    intervenciones_con_frente_activo += 1
                else:
                    sin_frente += 1
                    intervenciones_sin_frente_activo += 1
            
            # Si hay intervenciones sin frente activo, es un problema
            if sin_frente > 0:
                features_con_problema.append({
                    'index': i,
                    'upid': props.get('upid', 'N/A'),
                    'nombre_up': props.get('nombre_up', 'N/A')[:50],
                    'total': len(intervenciones),
                    'con_frente': con_frente,
                    'sin_frente': sin_frente
                })
        
        print(f"\n🔍 ANÁLISIS DETALLADO:")
        print(f"   • Total intervenciones en todos los features: {total_intervenciones_en_features}")
        print(f"   • Intervenciones CON 'Frente activo': {intervenciones_con_frente_activo}")
        print(f"   • Intervenciones SIN 'Frente activo': {intervenciones_sin_frente_activo}")
        
        if intervenciones_sin_frente_activo > 0:
            print(f"\n❌ PROBLEMA DETECTADO:")
            print(f"   Se encontraron {intervenciones_sin_frente_activo} intervenciones sin 'Frente activo'")
            print(f"   en {len(features_con_problema)} features")
            
            print(f"\n   📋 Primeros 10 features con problema:")
            for item in features_con_problema[:10]:
                print(f"\n      {item['index'] + 1}. {item['upid']} - {item['nombre_up']}")
                print(f"         Total: {item['total']}, Con frente: {item['con_frente']}, Sin frente: {item['sin_frente']}")
        else:
            print(f"\n✅ CORRECTO: Todas las intervenciones tienen 'Frente activo'")
        
        # Mostrar algunos ejemplos
        print(f"\n📄 MUESTRA DE FEATURES (primeros 3):")
        for i, feature in enumerate(features[:3], 1):
            props = feature.get("properties", {})
            intervenciones = props.get("intervenciones", [])
            print(f"\n   {i}. UPID: {props.get('upid', 'N/A')}")
            print(f"      Nombre: {props.get('nombre_up', 'N/A')[:60]}")
            print(f"      N° intervenciones: {len(intervenciones)}")
            for j, interv in enumerate(intervenciones, 1):
                print(f"         {j}. Año: {interv.get('ano')}, Estado: {interv.get('estado')}, "
                      f"Frente: {interv.get('frente_activo')}")
    
    else:
        print(f"❌ ERROR: La respuesta no es un FeatureCollection")
        print(f"   Tipo: {result.get('type', 'N/A')}")
        print(f"   Error: {result.get('error', 'N/A')}")
    
    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    asyncio.run(probar_endpoint())
