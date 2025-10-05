#!/usr/bin/env python3
"""
🔧 DIAGNÓSTICO ESPECÍFICO - PROBLEMAS CON FILTROS DE COMUNA
============================================================
Este script analiza los valores exactos de comuna_corregimiento 
para identificar por qué algunos filtros funcionan y otros no.
"""

import asyncio
import aiohttp
import json
from collections import Counter
import unicodedata

BASE_URL = "http://localhost:8000"

async def diagnose_comuna_filtering():
    """Diagnosticar problemas específicos con filtros de comuna"""
    print("🔍 INICIANDO DIAGNÓSTICO DE FILTROS DE COMUNA")
    print("=" * 60)
    
    async with aiohttp.ClientSession() as session:
        # 1. Obtener TODOS los datos sin filtros para análisis
        print("📋 1. Obteniendo TODOS los datos para análisis...")
        try:
            async with session.get(f"{BASE_URL}/unidades-proyecto/geometry") as response:
                all_data = await response.json()
                print(f"✅ Obtenidos {all_data.get('count', 0)} registros totales")
        except Exception as e:
            print(f"❌ Error obteniendo datos: {e}")
            return
        
        # 2. Analizar valores únicos de comuna_corregimiento
        print("\n📊 2. ANÁLISIS DE VALORES DE COMUNA_CORREGIMIENTO:")
        print("-" * 50)
        
        all_comunas = []
        for item in all_data.get('data', []):
            props = item.get('properties', {})
            comuna = props.get('comuna_corregimiento')
            if comuna:
                all_comunas.append(comuna)
        
        # Contador de comunas
        comuna_counts = Counter(all_comunas)
        print(f"Total de registros con comuna: {len(all_comunas)}")
        print(f"Valores únicos de comuna: {len(comuna_counts)}")
        
        print("\n🏘️ DISTRIBUCIÓN DE COMUNAS:")
        for comuna, count in sorted(comuna_counts.items()):
            # Mostrar información detallada de cada comuna
            comuna_repr = repr(comuna)  # Mostrar caracteres especiales
            comuna_bytes = comuna.encode('utf-8')
            print(f"  • '{comuna}' → {count} registros")
            print(f"    └─ Repr: {comuna_repr}")
            print(f"    └─ Bytes: {comuna_bytes}")
            print(f"    └─ Longitud: {len(comuna)} caracteres")
            
            # Analizar caracteres individuales
            chars_info = []
            for char in comuna:
                char_name = unicodedata.name(char, f"U+{ord(char):04X}")
                chars_info.append(f"{char}({char_name})")
            print(f"    └─ Caracteres: {' '.join(chars_info[:3])}...")
            print()
        
        # 3. Probar filtros específicos problemáticos
        print("🔍 3. PROBANDO FILTROS ESPECÍFICOS:")
        print("-" * 40)
        
        test_comunas = ["COMUNA 01", "COMUNA 04", "COMUNA 10", "COMUNA 1", "COMUNA 4"]
        
        for test_comuna in test_comunas:
            print(f"\n🎯 Probando filtro: '{test_comuna}'")
            try:
                params = {"comuna_corregimiento": test_comuna, "limit": 5}
                async with session.get(f"{BASE_URL}/unidades-proyecto/geometry", params=params) as response:
                    result = await response.json()
                    count = result.get('count', 0)
                    status = "✅" if count > 0 else "❌"
                    print(f"  {status} Resultado: {count} registros")
                    
                    if count > 0:
                        # Mostrar muestra del primer resultado
                        first_item = result['data'][0]['properties']
                        actual_comuna = first_item.get('comuna_corregimiento', 'N/A')
                        print(f"  📍 Comuna encontrada: '{actual_comuna}'")
                        print(f"  🆔 UPID: {first_item.get('upid', 'N/A')}")
                    else:
                        # Buscar coincidencias parciales en los datos originales
                        matches = []
                        for item in all_data.get('data', []):
                            props = item.get('properties', {})
                            comuna = props.get('comuna_corregimiento', '')
                            if test_comuna.lower() in comuna.lower() or comuna.lower() in test_comuna.lower():
                                matches.append(comuna)
                        
                        if matches:
                            print(f"  🔍 Posibles coincidencias en datos: {list(set(matches))}")
                        else:
                            print(f"  ❓ No se encontraron coincidencias similares")
            
            except Exception as e:
                print(f"  ❌ Error: {e}")
        
        # 4. Análisis de filtrado interno
        print("\n🛠️ 4. ANÁLISIS DEL FILTRADO CLIENT-SIDE:")
        print("-" * 40)
        
        # Simular el filtrado client-side como lo hace la API
        test_filter = "COMUNA 01"
        manual_matches = []
        
        for item in all_data.get('data', []):
            props = item.get('properties', {})
            comuna = props.get('comuna_corregimiento', '')
            
            # Diferentes tipos de comparación
            exact_match = comuna == test_filter
            case_insensitive = comuna.lower() == test_filter.lower()
            stripped_match = comuna.strip() == test_filter.strip()
            
            if exact_match or case_insensitive or stripped_match:
                manual_matches.append({
                    'upid': props.get('upid'),
                    'comuna': comuna,
                    'exact': exact_match,
                    'case_insensitive': case_insensitive,
                    'stripped': stripped_match
                })
        
        print(f"Filtro manual para '{test_filter}':")
        print(f"  • Coincidencias encontradas: {len(manual_matches)}")
        for match in manual_matches[:3]:  # Mostrar primeras 3
            print(f"  • {match['upid']}: '{match['comuna']}'")
            print(f"    └─ Exacto: {match['exact']}, Case-insensitive: {match['case_insensitive']}, Stripped: {match['stripped']}")
        
        # 5. Recomendaciones
        print("\n💡 5. RECOMENDACIONES:")
        print("-" * 30)
        
        if len(manual_matches) > 0:
            print("✅ Los datos existen, problema en el filtrado client-side")
            print("🔧 Revisar función de filtrado en unidades_proyecto.py")
        else:
            print("❓ Los datos pueden no existir o tener formato diferente")
            print("🔍 Verificar formato exacto de los valores en la base de datos")
        
        print("\n📝 PASOS SIGUIENTES:")
        print("1. Revisar función apply_client_side_filters()")
        print("2. Implementar filtrado case-insensitive y con trim")
        print("3. Considerar normalización Unicode")
        print("4. Agregar logging detallado al filtrado")

if __name__ == "__main__":
    asyncio.run(diagnose_comuna_filtering())