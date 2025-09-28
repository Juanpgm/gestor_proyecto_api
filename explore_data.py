#!/usr/bin/env python3
"""
Script para explorar la estructura real de los datos en Firestore
"""

import asyncio
from api.scripts.unidades_proyecto import get_unidades_proyecto_attributes

async def explore_data_structure():
    print("🔍 Explorando estructura de datos en Firestore...")
    
    # Obtener una muestra de datos
    result = await get_unidades_proyecto_attributes()
    
    if not result["success"]:
        print(f"❌ Error: {result['error']}")
        return
    
    data = result["data"]
    print(f"📊 Total de registros: {len(data)}")
    
    if len(data) == 0:
        print("❌ No hay datos disponibles")
        return
    
    # Analizar los primeros registros
    print("\n🔍 ANÁLISIS DE ESTRUCTURA:")
    print("="*50)
    
    for i, record in enumerate(data[:3]):  # Primeros 3 registros
        print(f"\n📋 REGISTRO {i+1}:")
        print("-" * 30)
        
        # Mostrar todos los campos disponibles
        for key, value in record.items():
            # Mostrar valor truncado para campos largos
            if isinstance(value, str) and len(value) > 50:
                display_value = value[:47] + "..."
            else:
                display_value = value
            
            print(f"  {key}: {display_value} ({type(value).__name__})")
    
    # Obtener todos los campos únicos
    print(f"\n📝 TODOS LOS CAMPOS ENCONTRADOS:")
    print("="*50)
    
    all_fields = set()
    for record in data:
        all_fields.update(record.keys())
    
    sorted_fields = sorted(list(all_fields))
    for field in sorted_fields:
        # Contar cuántos registros tienen este campo con valor
        count_with_value = sum(1 for record in data if record.get(field) not in [None, '', 'null'])
        percentage = (count_with_value / len(data)) * 100
        print(f"  {field}: {count_with_value}/{len(data)} registros ({percentage:.1f}%)")
    
    # Buscar campos que podrían contener los datos que necesitamos
    print(f"\n🎯 CAMPOS CANDIDATOS PARA AGREGACIONES:")
    print("="*50)
    
    # Campos financieros
    financial_fields = [f for f in sorted_fields if any(keyword in f.lower() for keyword in ['presupuesto', 'costo', 'valor', 'monto', 'precio'])]
    if financial_fields:
        print(f"💰 Campos financieros: {financial_fields}")
    
    # Campos de avance
    progress_fields = [f for f in sorted_fields if any(keyword in f.lower() for keyword in ['avance', 'progreso', 'porcentaje', 'completado'])]
    if progress_fields:
        print(f"📈 Campos de avance: {progress_fields}")
    
    # Campos de ubicación
    location_fields = [f for f in sorted_fields if any(keyword in f.lower() for keyword in ['comuna', 'barrio', 'vereda', 'ubicacion', 'direccion'])]
    if location_fields:
        print(f"📍 Campos de ubicación: {location_fields}")
    
    # Campos de estado y tipo
    status_fields = [f for f in sorted_fields if any(keyword in f.lower() for keyword in ['estado', 'tipo', 'intervencion', 'categoria'])]
    if status_fields:
        print(f"⚡ Campos de estado/tipo: {status_fields}")
    
    # Campos de referencia
    reference_fields = [f for f in sorted_fields if any(keyword in f.lower() for keyword in ['referencia', 'proceso', 'contrato', 'bpin'])]
    if reference_fields:
        print(f"📋 Campos de referencia: {reference_fields}")
    
    print(f"\n🎯 MUESTRA DE VALORES PARA CAMPOS CLAVE:")
    print("="*50)
    
    # Mostrar valores de muestra para campos potencialmente útiles
    key_fields = financial_fields + progress_fields + location_fields + status_fields + reference_fields
    
    for field in key_fields[:10]:  # Solo los primeros 10 campos clave
        values = [record.get(field) for record in data[:5] if record.get(field) not in [None, '', 'null']]
        if values:
            print(f"  {field}: {values[:3]}...")  # Primeros 3 valores

if __name__ == "__main__":
    asyncio.run(explore_data_structure())