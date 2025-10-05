"""
Analizar los campos geométricos disponibles en los datos
"""
import asyncio
import aiohttp
import json

async def analyze_geometry_fields():
    """Analizar qué campos geométricos tienen realmente los datos"""
    base_url = "http://localhost:8000"
    
    async with aiohttp.ClientSession() as session:
        print("🔍 Analizando campos geométricos en datos attributes...")
        
        try:
            async with session.get(f"{base_url}/unidades-proyecto/attributes?limit=50") as response:
                if response.status == 200:
                    data = await response.json()
                    attributes_data = data.get('data', [])
                    print(f"✅ Obtenidos {len(attributes_data)} registros para análisis")
                    
                    if attributes_data:
                        # Analizar campos geométricos en muestra
                        geo_fields = ['upid', 'coordenadas', 'geometry', 'coordinates', 'lat', 'lng']
                        field_stats = {}
                        
                        for field in geo_fields:
                            field_stats[field] = {
                                'present': 0,
                                'empty': 0,
                                'sample_values': []
                            }
                        
                        for i, record in enumerate(attributes_data[:10]):  # Solo primeros 10 para muestra
                            properties = record.get('properties', {})
                            
                            print(f"\n📝 REGISTRO {i+1} - UPID: {properties.get('upid', 'N/A')}")
                            print(f"   Comuna: {properties.get('comuna_corregimiento', 'N/A')}")
                            print(f"   Barrio: {properties.get('barrio_vereda', 'N/A')}")
                            
                            # Verificar cada campo geométrico
                            for field in geo_fields:
                                # Buscar en properties y raíz
                                value = properties.get(field) or record.get(field)
                                
                                if value and str(value).strip() and str(value).strip().lower() not in ['null', 'none', '']:
                                    field_stats[field]['present'] += 1
                                    if len(field_stats[field]['sample_values']) < 3:
                                        field_stats[field]['sample_values'].append(str(value)[:50])
                                    print(f"   ✅ {field}: {str(value)[:50]}...")
                                else:
                                    field_stats[field]['empty'] += 1
                                    print(f"   ❌ {field}: VACÍO/NULO")
                        
                        print(f"\n📊 RESUMEN DE CAMPOS GEOMÉTRICOS (en primeros 10 registros):")
                        for field, stats in field_stats.items():
                            print(f"   {field}: {stats['present']} presentes, {stats['empty']} vacíos")
                            if stats['sample_values']:
                                print(f"      Ejemplos: {stats['sample_values']}")
                        
                        # Contar todos los registros con geometría válida según criterio actual
                        valid_geometry_count = 0
                        for record in attributes_data:
                            properties = record.get('properties', {})
                            
                            # Aplicar mismo criterio que get_unidades_proyecto_geometry
                            has_upid = properties.get('upid') or record.get('upid')
                            has_geometry = any([
                                properties.get('coordenadas') or record.get('coordenadas'),
                                properties.get('geometry') or record.get('geometry'),
                                properties.get('coordinates') or record.get('coordinates'),
                                properties.get('lat') or record.get('lat'),
                                properties.get('lng') or record.get('lng')
                            ])
                            
                            if has_upid and has_geometry:
                                valid_geometry_count += 1
                        
                        print(f"\n🎯 ANÁLISIS FINAL:")
                        print(f"   Total registros analizados: {len(attributes_data)}")
                        print(f"   Registros con UPID y geometría válida: {valid_geometry_count}")
                        print(f"   Registros que NO pasarían filtro geometry: {len(attributes_data) - valid_geometry_count}")
                        
                        if valid_geometry_count == 0:
                            print(f"\n🚨 PROBLEMA ENCONTRADO:")
                            print(f"   ❌ NINGÚN registro tiene campos geométricos válidos")
                            print(f"   ❌ Por esto el endpoint geometry retorna 0 registros")
                            print(f"   🔧 SOLUCIÓN: Relajar criterio de geometría o verificar estructura de datos")
                else:
                    print(f"❌ Error: {response.status}")
        except Exception as e:
            print(f"❌ Exception: {e}")

asyncio.run(analyze_geometry_fields())