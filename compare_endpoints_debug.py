"""
Verificar la discrepancia entre endpoints attributes vs geometry
"""
import asyncio
import aiohttp
import json

async def compare_endpoints():
    """Comparar datos entre endpoints"""
    base_url = "http://localhost:8000"
    
    async with aiohttp.ClientSession() as session:
        print("🔍 Comparando endpoints attributes vs geometry...")
        
        # 1. Probar endpoint attributes sin filtros
        print("\n1️⃣ ENDPOINT ATTRIBUTES (sin filtros)")
        try:
            async with session.get(f"{base_url}/unidades-proyecto/attributes") as response:
                if response.status == 200:
                    data = await response.json()
                    attributes_data = data.get('data', [])
                    print(f"   ✅ Status: {response.status}")
                    print(f"   📊 Registros: {len(attributes_data)}")
                    
                    if attributes_data:
                        # Mostrar muestra de datos
                        sample = attributes_data[0]
                        properties = sample.get('properties', {})
                        print(f"   📝 Muestra - UPID: {properties.get('upid', 'N/A')}")
                        print(f"   📝 Muestra - Comuna: {properties.get('comuna_corregimiento', 'N/A')}")
                        print(f"   📝 Muestra - Barrio: {properties.get('barrio_vereda', 'N/A')}")
                        print(f"   📝 Muestra - Estado: {properties.get('estado', 'N/A')}")
                        
                        # Contar comunas únicas
                        comunas = set()
                        barrios = set()
                        for record in attributes_data:
                            props = record.get('properties', {})
                            if props.get('comuna_corregimiento'):
                                comunas.add(props.get('comuna_corregimiento'))
                            if props.get('barrio_vereda'):
                                barrios.add(props.get('barrio_vereda'))
                        
                        print(f"   🏘️ Comunas únicas en attributes: {len(comunas)}")
                        print(f"   🏠 Barrios únicos en attributes: {len(barrios)}")
                        if len(comunas) > 0:
                            print(f"   📋 Primeras 5 comunas: {list(comunas)[:5]}")
                else:
                    print(f"   ❌ Error: {response.status}")
        except Exception as e:
            print(f"   ❌ Exception: {e}")
        
        # 2. Probar endpoint geometry sin filtros  
        print("\n2️⃣ ENDPOINT GEOMETRY (sin filtros)")
        try:
            async with session.get(f"{base_url}/unidades-proyecto/geometry") as response:
                if response.status == 200:
                    data = await response.json()
                    features = data.get('features', [])
                    print(f"   ✅ Status: {response.status}")
                    print(f"   📊 Registros: {len(features)}")
                    
                    if features:
                        # Mostrar muestra de datos
                        sample = features[0]
                        properties = sample.get('properties', {})
                        print(f"   📝 Muestra - UPID: {properties.get('upid', 'N/A')}")
                        print(f"   📝 Muestra - Comuna: {properties.get('comuna_corregimiento', 'N/A')}")
                        print(f"   📝 Muestra - Barrio: {properties.get('barrio_vereda', 'N/A')}")
                        print(f"   📝 Muestra - Estado: {properties.get('estado', 'N/A')}")
                        
                        # Contar comunas únicas
                        comunas = set()
                        barrios = set()
                        for feature in features:
                            props = feature.get('properties', {})
                            if props.get('comuna_corregimiento'):
                                comunas.add(props.get('comuna_corregimiento'))
                            if props.get('barrio_vereda'):
                                barrios.add(props.get('barrio_vereda'))
                        
                        print(f"   🏘️ Comunas únicas en geometry: {len(comunas)}")
                        print(f"   🏠 Barrios únicos en geometry: {len(barrios)}")
                        if len(comunas) > 0:
                            print(f"   📋 Comunas encontradas: {list(comunas)}")
                        if len(barrios) > 0:
                            print(f"   📋 Barrios encontrados: {list(barrios)}")
                else:
                    print(f"   ❌ Error: {response.status}")
        except Exception as e:
            print(f"   ❌ Exception: {e}")
        
        # 3. Probar con filtro específico conocido
        print("\n3️⃣ ENDPOINT GEOMETRY con filtro COMUNA 01")
        try:
            params = {'comuna_corregimiento': 'COMUNA 01'}
            async with session.get(f"{base_url}/unidades-proyecto/geometry", params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    features = data.get('features', [])
                    print(f"   ✅ Status: {response.status}")
                    print(f"   📊 Registros con COMUNA 01: {len(features)}")
                else:
                    print(f"   ❌ Error: {response.status}")
        except Exception as e:
            print(f"   ❌ Exception: {e}")

asyncio.run(compare_endpoints())