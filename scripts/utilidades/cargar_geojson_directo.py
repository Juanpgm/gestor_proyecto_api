"""
Script directo para cargar GeoJSON a Firebase sin pasar por el endpoint
Evita problemas de timeout del servidor web
"""

import asyncio
import json
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

from api.scripts.unidades_proyecto_loader import load_geojson_to_firestore


async def main():
    """Cargar GeoJSON directamente a Firebase"""
    
    print("=" * 80)
    print("CARGA DIRECTA DE GEOJSON A FIREBASE")
    print("=" * 80)
    print()
    
    # Ruta al archivo GeoJSON
    geojson_path = Path(__file__).parent / "context" / "unidades_proyecto.geojson"
    
    if not geojson_path.exists():
        print(f"❌ Archivo no encontrado: {geojson_path}")
        return
    
    print(f"📁 Archivo: {geojson_path}")
    print(f"📊 Configuración:")
    print(f"   - Batch size: 100")
    print(f"   - Override existing: True")
    print(f"   - Override UPID: True")
    print(f"   - Dry run: False")
    print()
    
    # Confirmar
    confirmacion = input("⚠️  ¿Desea continuar con la carga REAL a Firebase? (sí/no): ").strip().lower()
    if confirmacion not in ['sí', 'si', 's', 'yes', 'y']:
        print("❌ Operación cancelada")
        return
    
    print()
    print("=" * 80)
    print("INICIANDO CARGA...")
    print("=" * 80)
    print()
    
    # Leer archivo
    try:
        with open(geojson_path, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)
    except Exception as e:
        print(f"❌ Error leyendo archivo: {e}")
        return
    
    # Ejecutar carga
    result = await load_geojson_to_firestore(
        geojson_data=geojson_data,
        batch_size=100,  # Batches más pequeños para evitar timeouts
        override_existing=True,  # Sobrescribir para ir más rápido
        override_upid=True,  # Generar nuevos UPIDs
        dry_run=False
    )
    
    # Mostrar resultados
    print()
    print("=" * 80)
    print("RESULTADOS FINALES")
    print("=" * 80)
    print()
    
    if result.get('success'):
        print(f"✅ {result.get('message')}")
        print()
        
        stats = result.get('stats', {})
        print("📊 Estadísticas:")
        print(f"   - Total features: {stats.get('total_features', 0)}")
        print(f"   - Procesados: {stats.get('processed', 0)}")
        print(f"   - Creados: {stats.get('created', 0)}")
        print(f"   - Actualizados: {stats.get('updated', 0)}")
        print(f"   - Omitidos: {stats.get('skipped', 0)}")
        print(f"   - Errores: {stats.get('errors', 0)}")
        
        if stats.get('errors', 0) > 0:
            print()
            print("⚠️  Errores encontrados:")
            for error in stats.get('error_details', [])[:10]:
                print(f"   - Feature {error.get('index')}: {error.get('error')}")
    else:
        print(f"❌ Error: {result.get('error')}")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
