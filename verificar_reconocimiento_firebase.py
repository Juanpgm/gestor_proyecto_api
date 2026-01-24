#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para verificar el registro guardado en Firebase
"""

import asyncio
import sys
import json
from datetime import datetime

# Agregar el path del proyecto
sys.path.insert(0, '.')

from database.firebase_config import get_firestore_client

async def verificar_ultimo_reconocimiento():
    """
    Verificar el último reconocimiento guardado en Firebase
    """
    print("=" * 80)
    print("🔍 VERIFICACIÓN: Último reconocimiento DAGMA en Firebase")
    print("=" * 80)
    
    try:
        # Conectar a Firestore
        db = get_firestore_client()
        if db is None:
            print("❌ No se pudo conectar a Firestore")
            return
        
        print("\n✅ Conectado a Firestore")
        
        # Consultar la colección reconocimientos_dagma
        print("\n📊 Consultando colección: reconocimientos_dagma")
        
        query = db.collection('reconocimientos_dagma').order_by(
            'timestamp', direction='DESCENDING'
        ).limit(1)
        
        docs = query.stream()
        
        encontrado = False
        for doc in docs:
            encontrado = True
            doc_data = doc.to_dict()
            
            print(f"\n✅ Reconocimiento encontrado:")
            print(f"   Document ID: {doc.id}")
            print(f"   ID: {doc_data.get('id')}")
            print(f"   Timestamp: {doc_data.get('timestamp')}")
            
            print(f"\n📋 Datos de la intervención:")
            print(f"   Tipo: {doc_data.get('tipo_intervencion')}")
            print(f"   Descripción: {doc_data.get('descripcion_intervencion')}")
            print(f"   Dirección: {doc_data.get('direccion')}")
            print(f"   Observaciones: {doc_data.get('observaciones')}")
            
            print(f"\n📍 Coordenadas GPS:")
            coords = doc_data.get('coordinates', {})
            print(f"   Tipo: {coords.get('type')}")
            print(f"   Coordenadas: {coords.get('coordinates')}")
            
            print(f"\n📸 Fotos:")
            photos = doc_data.get('photosUrl', [])
            print(f"   Total subidas: {doc_data.get('photos_uploaded_count', 0)}")
            print(f"   Total fallidas: {doc_data.get('photos_failed_count', 0)}")
            
            if photos:
                print(f"\n   URLs de fotos en S3:")
                for idx, url in enumerate(photos, 1):
                    print(f"   {idx}. {url}")
            
            # Fotos fallidas (si hay)
            photos_failed = doc_data.get('photos_failed')
            if photos_failed:
                print(f"\n   ⚠️  Fotos fallidas:")
                for photo in photos_failed:
                    print(f"      • {photo.get('filename')}: {photo.get('error')}")
            
            print(f"\n📄 Documento completo:")
            print(json.dumps(doc_data, indent=2, ensure_ascii=False, default=str))
        
        if not encontrado:
            print("\n⚠️  No se encontraron reconocimientos en la colección")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verificar_ultimo_reconocimiento())
