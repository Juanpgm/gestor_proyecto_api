"""
Script para verificar en Firebase si los registros sin geometría tienen coordenadas
"""
import asyncio
from database.firebase_config import get_firestore_client

async def verificar_geometrias_firebase():
    """Verificar geometrías en Firebase"""
    
    print("=" * 80)
    print("VERIFICACIÓN DE GEOMETRÍAS EN FIREBASE")
    print("=" * 80)
    
    db = get_firestore_client()
    if not db:
        print("❌ No se pudo conectar a Firestore")
        return
    
    # UPIDs sin geometría
    upids_sin_geo = ['UNP-46', 'UNP-48', 'UNP-6']
    
    for upid in upids_sin_geo:
        print(f"\n{'=' * 80}")
        print(f"UPID: {upid}")
        print("=" * 80)
        
        # Buscar documento
        query = db.collection('unidades_proyecto').where('upid', '==', upid)
        docs = list(query.stream())
        
        if not docs:
            print(f"❌ No se encontró documento con UPID={upid}")
            continue
        
        doc = docs[0]
        doc_data = doc.to_dict()
        
        print(f"✅ Documento encontrado: {doc.id}")
        print(f"\nCampos en nivel superior:")
        print(f"  Keys: {list(doc_data.keys())}")
        
        # Buscar geometría en diferentes ubicaciones
        print(f"\nBuscando geometría:")
        
        # 1. Campo geometry
        if 'geometry' in doc_data:
            print(f"  ✓ geometry: {doc_data['geometry']}")
        else:
            print(f"  ✗ No tiene campo 'geometry'")
        
        # 2. Campo coordinates
        if 'coordinates' in doc_data:
            print(f"  ✓ coordinates: {doc_data['coordinates']}")
        else:
            print(f"  ✗ No tiene campo 'coordinates'")
        
        # 3. Campo coordenadas
        if 'coordenadas' in doc_data:
            print(f"  ✓ coordenadas: {doc_data['coordenadas']}")
        else:
            print(f"  ✗ No tiene campo 'coordenadas'")
        
        # 4. Campos lat/lng
        lat = doc_data.get('lat') or doc_data.get('latitude')
        lng = doc_data.get('lng') or doc_data.get('lon') or doc_data.get('longitude')
        
        if lat:
            print(f"  ✓ lat/latitude: {lat}")
        else:
            print(f"  ✗ No tiene campo 'lat' o 'latitude'")
        
        if lng:
            print(f"  ✓ lng/lon/longitude: {lng}")
        else:
            print(f"  ✗ No tiene campo 'lng', 'lon' o 'longitude'")
        
        # 5. Dentro de properties
        if 'properties' in doc_data:
            props = doc_data['properties']
            print(f"\n  Buscando en 'properties':")
            
            if 'geometry' in props:
                print(f"    ✓ properties.geometry: {props['geometry']}")
            else:
                print(f"    ✗ No tiene properties.geometry")
            
            if 'coordinates' in props:
                print(f"    ✓ properties.coordinates: {props['coordinates']}")
            else:
                print(f"    ✗ No tiene properties.coordinates")
            
            if 'coordenadas' in props:
                print(f"    ✓ properties.coordenadas: {props['coordenadas']}")
            else:
                print(f"    ✗ No tiene properties.coordenadas")
            
            lat_prop = props.get('lat') or props.get('latitude')
            lng_prop = props.get('lng') or props.get('lon') or props.get('longitude')
            
            if lat_prop:
                print(f"    ✓ properties.lat/latitude: {lat_prop}")
            else:
                print(f"    ✗ No tiene properties.lat o properties.latitude")
            
            if lng_prop:
                print(f"    ✓ properties.lng/lon/longitude: {lng_prop}")
            else:
                print(f"    ✗ No tiene properties.lng, properties.lon o properties.longitude")
        
        # 6. Otros campos potenciales
        print(f"\nOtros campos potenciales:")
        campos_geo = ['geom', 'location', 'point', 'coord', 'position', 'latitud', 'longitud']
        for campo in campos_geo:
            if campo in doc_data:
                print(f"  ✓ {campo}: {doc_data[campo]}")
        
        # 7. Mostrar todos los campos para análisis
        print(f"\nTODOS LOS CAMPOS DEL DOCUMENTO:")
        for key, value in doc_data.items():
            if key != 'intervenciones':  # Excluir intervenciones para no saturar
                value_str = str(value)[:100]  # Limitar longitud
                print(f"  {key}: {value_str}")

if __name__ == "__main__":
    asyncio.run(verificar_geometrias_firebase())
