from database.firebase_config import get_firestore_client

db = get_firestore_client()

# Buscar diferentes tipos de geometrías unificadas
multi_types = ['MultiPoint', 'MultiLineString', 'MultiPolygon', 'GeometryCollection']

print('🔍 Buscando geometrías unificadas...\n')

for geom_type in multi_types:
    docs = list(db.collection('unidades_proyecto').where('geometry_type', '==', geom_type).limit(5).stream())
    
    print(f'� {geom_type}: {len(docs)} encontrados')
    
    for doc in docs[:3]:  # Mostrar solo los primeros 3
        data = doc.to_dict()
        print(f'  - {doc.id}: {data.get("nombre_up")}')
