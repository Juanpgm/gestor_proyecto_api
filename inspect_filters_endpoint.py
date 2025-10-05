"""
Script para inspeccionar el endpoint /filters y generar tests basados en filtros reales
"""
import asyncio
import aiohttp
import json

async def get_filters_from_endpoint():
    """Obtener filtros reales del endpoint"""
    base_url = "http://localhost:8000"
    
    try:
        async with aiohttp.ClientSession() as session:
            # Obtener filtros disponibles
            filters_url = f"{base_url}/unidades-proyecto/filters"
            async with session.get(filters_url) as response:
                if response.status == 200:
                    filters_data = await response.json()
                    print("=== FILTROS DISPONIBLES ===")
                    print(json.dumps(filters_data, indent=2, ensure_ascii=False))
                    
                    # Extraer valores únicos para cada filtro
                    filters = filters_data.get('filters', {})
                    
                    print("\n=== ANÁLISIS DE FILTROS ===")
                    for filter_name, values in filters.items():
                        print(f"\n{filter_name}:")
                        if isinstance(values, list):
                            print(f"  Total valores: {len(values)}")
                            for i, value in enumerate(values[:10]):  # Solo primeros 10
                                print(f"  [{i+1}] {value}")
                            if len(values) > 10:
                                print(f"  ... y {len(values) - 10} más")
                        else:
                            print(f"  Tipo: {type(values)}")
                            print(f"  Valor: {values}")
                    
                    return filters_data
                else:
                    print(f"❌ Error: {response.status}")
                    text = await response.text()
                    print(text)
                    return None
                    
    except Exception as e:
        print(f"❌ Error conectando: {e}")
        return None

async def main():
    print("🔍 Inspeccionando endpoint /filters...")
    filters_data = await get_filters_from_endpoint()
    
    if filters_data:
        print("\n✅ Filtros obtenidos exitosamente")
        
        # Guardar en archivo para referencia
        with open('filters_inspection.json', 'w', encoding='utf-8') as f:
            json.dump(filters_data, f, indent=2, ensure_ascii=False)
        print("📄 Datos guardados en 'filters_inspection.json'")
    else:
        print("❌ No se pudieron obtener los filtros")

if __name__ == "__main__":
    asyncio.run(main())