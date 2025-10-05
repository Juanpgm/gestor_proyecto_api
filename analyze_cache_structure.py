#!/usr/bin/env python3
"""
🛠️ FIX TEMPORAL - ANÁLISIS DE DATOS EN CACHE
===========================================
Script para analizar la estructura exacta de los datos 
en cache y identificar por qué los filtros no funcionan.
"""

import asyncio
import aiohttp
import json

BASE_URL = "http://localhost:8000"

async def analyze_cache_data():
    """Analizar datos exactos en cache"""
    print("🔍 ANÁLISIS DE DATOS EN CACHE - ESTRUCTURA COMPLETA")
    print("=" * 60)
    
    async with aiohttp.ClientSession() as session:
        # Obtener datos SIN filtros para ver estructura completa
        print("📋 1. Obteniendo datos SIN filtros...")
        try:
            async with session.get(f"{BASE_URL}/unidades-proyecto/geometry?limit=50") as response:
                raw_response = await response.text()
                data = json.loads(raw_response)
                
                print(f"✅ Status: {response.status}")
                print(f"✅ Count: {data.get('count', 0)}")
                print(f"✅ Cache hit: {data.get('cache_hit', False)}")
                
                items = data.get('data', [])
                if not items:
                    print("❌ No hay datos en la respuesta")
                    return
                
                print(f"\n📊 2. ANÁLISIS DEL PRIMER REGISTRO:")
                print("-" * 50)
                first_item = items[0]
                
                # Mostrar estructura completa
                print("🔍 ESTRUCTURA COMPLETA DEL PRIMER REGISTRO:")
                for key, value in first_item.items():
                    if isinstance(value, str):
                        print(f"  • {key}: '{value}' (len={len(value)})")
                        print(f"    └─ Repr: {repr(value)}")
                        print(f"    └─ Bytes: {value.encode('utf-8')}")
                    elif isinstance(value, (int, float)):
                        print(f"  • {key}: {value} ({type(value).__name__})")
                    elif isinstance(value, list):
                        print(f"  • {key}: [lista con {len(value)} elementos]")
                    elif isinstance(value, dict):
                        print(f"  • {key}: {{dict con {len(value)} claves}}")
                        if key == 'properties':
                            print("    Properties content:")
                            for pk, pv in value.items():
                                print(f"      - {pk}: {repr(pv)}")
                    else:
                        print(f"  • {key}: {value} ({type(value).__name__})")
                
                # Análisis específico de comuna_corregimiento
                print(f"\n🏘️ 3. ANÁLISIS ESPECÍFICO DE COMUNA_CORREGIMIENTO:")
                print("-" * 60)
                
                comuna_direct = first_item.get('comuna_corregimiento')
                comuna_props = first_item.get('properties', {}).get('comuna_corregimiento')
                
                print(f"Comuna directa: {repr(comuna_direct)}")
                print(f"Comuna en properties: {repr(comuna_props)}")
                
                if comuna_direct:
                    print(f"  • Valor: '{comuna_direct}'")
                    print(f"  • Longitud: {len(comuna_direct)}")
                    print(f"  • Bytes: {comuna_direct.encode('utf-8')}")
                    print(f"  • Stripped: '{comuna_direct.strip()}'")
                    print(f"  • Lower: '{comuna_direct.lower()}'")
                
                if comuna_props:
                    print(f"  • Props valor: '{comuna_props}'")
                    print(f"  • Props longitud: {len(comuna_props)}")
                    print(f"  • Props bytes: {comuna_props.encode('utf-8')}")
                
                # Análisis de TODOS los registros para ver variedad
                print(f"\n📈 4. ANÁLISIS DE TODOS LOS REGISTROS ({len(items)} total):")
                print("-" * 60)
                
                comunas_found = {}
                for i, item in enumerate(items):
                    comuna = item.get('comuna_corregimiento') or item.get('properties', {}).get('comuna_corregimiento')
                    if comuna:
                        if comuna not in comunas_found:
                            comunas_found[comuna] = []
                        comunas_found[comuna].append(i)
                
                print(f"Comunas únicas encontradas: {len(comunas_found)}")
                for comuna, indices in comunas_found.items():
                    print(f"  • '{comuna}' → {len(indices)} registros (indices: {indices[:5]}...)")
                    print(f"    └─ Repr: {repr(comuna)}")
                    print(f"    └─ Bytes: {comuna.encode('utf-8')}")
                
                # Probar filtros manualmente
                print(f"\n🧪 5. PRUEBA MANUAL DE FILTROS:")
                print("-" * 40)
                
                test_values = ["COMUNA 01", "COMUNA 04", "COMUNA 10"]
                
                for test_val in test_values:
                    print(f"\n🎯 Probando filtro manual: '{test_val}'")
                    matches = []
                    
                    for i, item in enumerate(items):
                        comuna_direct = item.get('comuna_corregimiento')
                        comuna_props = item.get('properties', {}).get('comuna_corregimiento')
                        
                        # Diferentes tipos de comparación
                        exact_direct = comuna_direct == test_val if comuna_direct else False
                        exact_props = comuna_props == test_val if comuna_props else False
                        case_direct = comuna_direct.lower() == test_val.lower() if comuna_direct else False
                        case_props = comuna_props.lower() == test_val.lower() if comuna_props else False
                        strip_direct = comuna_direct.strip() == test_val.strip() if comuna_direct else False
                        strip_props = comuna_props.strip() == test_val.strip() if comuna_props else False
                        
                        if any([exact_direct, exact_props, case_direct, case_props, strip_direct, strip_props]):
                            matches.append({
                                'index': i,
                                'upid': item.get('upid'),
                                'comuna_direct': comuna_direct,
                                'comuna_props': comuna_props,
                                'exact_direct': exact_direct,
                                'exact_props': exact_props,
                                'case_direct': case_direct,
                                'case_props': case_props,
                                'strip_direct': strip_direct,
                                'strip_props': strip_props
                            })
                    
                    print(f"  ✅ Coincidencias manuales: {len(matches)}")
                    for match in matches[:2]:  # Primeras 2
                        print(f"    • Registro {match['index']} (UPID: {match['upid']})")
                        print(f"      └─ Comuna direct: '{match['comuna_direct']}'")
                        print(f"      └─ Comuna props: '{match['comuna_props']}'")
                        print(f"      └─ Matches: exact_d={match['exact_direct']}, exact_p={match['exact_props']}")
                        print(f"      └─ Matches: case_d={match['case_direct']}, case_p={match['case_props']}")
                        print(f"      └─ Matches: strip_d={match['strip_direct']}, strip_p={match['strip_props']}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(analyze_cache_data())