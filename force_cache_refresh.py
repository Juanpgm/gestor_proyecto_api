#!/usr/bin/env python3
"""
🔧 LIMPIEZA DE CACHE - FORZAR RECARGA COMPLETA
============================================
Script para limpiar cache corrupto y forzar recarga desde Firestore
"""

import asyncio
import aiohttp
import json

BASE_URL = "http://localhost:8000"

async def force_cache_refresh():
    """Forzar limpieza y recarga de cache"""
    print("🧹 INICIANDO LIMPIEZA DE CACHE Y RECARGA")
    print("=" * 60)
    
    async with aiohttp.ClientSession() as session:
        # 1. Obtener datos con parámetro especial para limpiar cache
        print("📋 1. Forzando limpieza de cache...")
        try:
            # Agregar parámetro timestamp para bypass de cache
            import time
            timestamp = int(time.time())
            
            # Llamar con parámetro que force recarga
            async with session.get(f"{BASE_URL}/unidades-proyecto/geometry?force_refresh={timestamp}&limit=100") as response:
                data = await response.json()
                
                print(f"✅ Status: {response.status}")
                print(f"✅ Count: {data.get('count', 0)}")
                print(f"✅ Cache hit: {data.get('cache_hit', False)}")
                
                items = data.get('data', [])
                
                # Análisis de comunas después de recarga
                print(f"\n📊 2. ANÁLISIS DESPUÉS DE RECARGA:")
                print("-" * 50)
                
                comunas_found = {}
                for item in items:
                    comuna = item.get('comuna_corregimiento')
                    if comuna and comuna not in comunas_found:
                        comunas_found[comuna] = 0
                    if comuna:
                        comunas_found[comuna] += 1
                
                print(f"Comunas únicas encontradas: {len(comunas_found)}")
                for comuna, count in sorted(comunas_found.items()):
                    print(f"  • '{comuna}' → {count} registros")
                
                # 3. Probar filtros después de recarga
                print(f"\n🧪 3. PROBANDO FILTROS DESPUÉS DE RECARGA:")
                print("-" * 60)
                
                test_comunas = ["COMUNA 01", "COMUNA 04", "COMUNA 10"]
                
                for test_comuna in test_comunas:
                    print(f"\n🎯 Probando: '{test_comuna}'")
                    try:
                        params = {"comuna_corregimiento": test_comuna, "limit": 5}
                        async with session.get(f"{BASE_URL}/unidades-proyecto/geometry", params=params) as filter_response:
                            filter_data = await filter_response.json()
                            count = filter_data.get('count', 0)
                            status = "✅" if count > 0 else "❌"
                            cache_hit = filter_data.get('cache_hit', False)
                            
                            print(f"  {status} Resultado: {count} registros (cache_hit: {cache_hit})")
                            
                            if count > 0:
                                first_result = filter_data['data'][0]
                                actual_comuna = first_result.get('comuna_corregimiento', 'N/A')
                                upid = first_result.get('upid', 'N/A')
                                print(f"  📍 Comuna: '{actual_comuna}', UPID: {upid}")
                    
                    except Exception as e:
                        print(f"  ❌ Error: {e}")
                
        except Exception as e:
            print(f"❌ Error en recarga: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(force_cache_refresh())