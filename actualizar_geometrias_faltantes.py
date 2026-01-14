"""
Script para intentar geocodificar las direcciones de los registros sin geometría
"""
import asyncio
from database.firebase_config import get_firestore_client
from google.cloud import firestore

# Direcciones conocidas de Cali, Colombia para estos registros
DIRECCIONES_CONOCIDAS = {
    'UNP-46': {
        'direccion': 'Carrera 2 Norte # 45an-77',
        'barrio': 'Unión de Vivienda Popular',
        'comuna': 'COMUNA 16',
        'ciudad': 'Cali, Valle del Cauca, Colombia',
        # Coordenadas aproximadas de IPS Unión de Vivienda Popular
        'lat': 3.4583,
        'lon': -76.5075
    },
    'UNP-48': {
        'direccion': 'Carrera 139 # 2-68, Corregimiento del Hormiguero',
        'barrio': 'Barrio Manuela Beltrán',
        'comuna': 'Corregimiento',
        'ciudad': 'Cali, Valle del Cauca, Colombia',
        # Coordenadas aproximadas del Hormiguero, Cali
        'lat': 3.3225,
        'lon': -76.4458
    },
    'UNP-6': {
        'direccion': 'Calle 8 con Carrera 32 Esquina',
        'barrio': 'Parcelaciones Pance y la María',
        'comuna': 'COMUNA 12',
        'ciudad': 'Cali, Valle del Cauca, Colombia',
        # Coordenadas aproximadas de esa dirección en Comuna 12, Cali
        'lat': 3.3825,
        'lon': -76.5433
    }
}

async def actualizar_geometrias():
    """Actualizar geometrías de los registros sin coordenadas"""
    
    print("=" * 80)
    print("ACTUALIZACIÓN DE GEOMETRÍAS EN FIREBASE")
    print("=" * 80)
    
    db = get_firestore_client()
    if not db:
        print("❌ No se pudo conectar a Firestore")
        return
    
    for upid, datos in DIRECCIONES_CONOCIDAS.items():
        print(f"\n{'=' * 80}")
        print(f"Actualizando UPID: {upid}")
        print("=" * 80)
        
        # Buscar documento
        query = db.collection('unidades_proyecto').where('upid', '==', upid)
        docs = list(query.stream())
        
        if not docs:
            print(f"❌ No se encontró documento con UPID={upid}")
            continue
        
        doc = docs[0]
        doc_ref = db.collection('unidades_proyecto').document(doc.id)
        
        print(f"✅ Documento encontrado: {doc.id}")
        print(f"📍 Dirección: {datos['direccion']}")
        print(f"🗺️ Barrio: {datos['barrio']}")
        print(f"📌 Comuna: {datos['comuna']}")
        print(f"🌍 Coordenadas a actualizar:")
        print(f"   Latitud: {datos['lat']}")
        print(f"   Longitud: {datos['lon']}")
        
        # Preparar actualización
        geometry_data = {
            "type": "Point",
            "coordinates": [datos['lon'], datos['lat']]  # GeoJSON: [lng, lat]
        }
        
        update_data = {
            'lat': datos['lat'],
            'lon': datos['lon'],
            'geometry': geometry_data,
            'has_geometry': True,
            'geometry_source': 'manual_geocoding',
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        
        # Actualizar documento
        try:
            doc_ref.update(update_data)
            print(f"✅ Geometría actualizada correctamente")
        except Exception as e:
            print(f"❌ Error actualizando: {str(e)}")

if __name__ == "__main__":
    asyncio.run(actualizar_geometrias())
