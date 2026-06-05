"""
Script de demostración del comportamiento de sobreescritura de documentos
"""

import os
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

from api.utils.s3_document_manager import S3DocumentManager


def test_overwrite_behavior():
    """
    Demostrar comportamiento de sobreescritura:
    1. Subir documento con nombre "contrato.pdf"
    2. Subir otro documento con el mismo nombre -> se sobreescribe
    3. Subir documento con nombre diferente "anexo.pdf" -> se adiciona
    """
    print("=" * 80)
    print("🧪 DEMO: Comportamiento de Sobreescritura y Adición")
    print("=" * 80)
    
    try:
        s3_manager = S3DocumentManager()
        test_referencia = "CONT-DEMO-001"
        
        # PASO 1: Subir primer documento
        print("\n📤 PASO 1: Subiendo 'contrato.pdf' (versión 1)")
        result1 = s3_manager.upload_document(
            file_content=b"Contenido del contrato - Version 1",
            filename="contrato.pdf",
            referencia_contrato=test_referencia,
            document_type='rpc',
            content_type='application/pdf',
            metadata={'numero_rpc': 'RPC-001'},
            use_timestamp=False  # SIN timestamp - permite sobreescritura
        )
        
        if result1['success']:
            print(f"✅ Subido: {result1['s3_key']}")
            print(f"   Tamaño: {result1['size']} bytes")
        
        # Listar documentos después del paso 1
        docs = s3_manager.list_documents(test_referencia, 'rpc')
        print(f"\n📋 Documentos en carpeta (después de paso 1): {len(docs)}")
        for doc in docs:
            print(f"   - {Path(doc['s3_key']).name} ({doc['size']} bytes)")
        
        # PASO 2: Subir mismo documento con contenido actualizado
        print("\n📤 PASO 2: Subiendo 'contrato.pdf' (versión 2 - SOBREESCRIBE)")
        result2 = s3_manager.upload_document(
            file_content=b"Contenido del contrato - Version 2 ACTUALIZADA con mas contenido",
            filename="contrato.pdf",
            referencia_contrato=test_referencia,
            document_type='rpc',
            content_type='application/pdf',
            metadata={'numero_rpc': 'RPC-001'},
            use_timestamp=False  # SIN timestamp - sobreescribe el anterior
        )
        
        if result2['success']:
            print(f"✅ Actualizado: {result2['s3_key']}")
            print(f"   Tamaño nuevo: {result2['size']} bytes (era {result1['size']} bytes)")
        
        # Listar documentos después del paso 2
        docs = s3_manager.list_documents(test_referencia, 'rpc')
        print(f"\n📋 Documentos en carpeta (después de paso 2): {len(docs)}")
        for doc in docs:
            print(f"   - {Path(doc['s3_key']).name} ({doc['size']} bytes)")
        
        # PASO 3: Subir documento diferente
        print("\n📤 PASO 3: Subiendo 'anexo_tecnico.pdf' (documento nuevo - SE ADICIONA)")
        result3 = s3_manager.upload_document(
            file_content=b"Contenido del anexo tecnico del contrato",
            filename="anexo_tecnico.pdf",
            referencia_contrato=test_referencia,
            document_type='rpc',
            content_type='application/pdf',
            metadata={'numero_rpc': 'RPC-001'},
            use_timestamp=False
        )
        
        if result3['success']:
            print(f"✅ Adicionado: {result3['s3_key']}")
            print(f"   Tamaño: {result3['size']} bytes")
        
        # Listar documentos después del paso 3
        docs = s3_manager.list_documents(test_referencia, 'rpc')
        print(f"\n📋 Documentos en carpeta (después de paso 3): {len(docs)}")
        for doc in docs:
            print(f"   - {Path(doc['s3_key']).name} ({doc['size']} bytes)")
        
        # PASO 4: Subir otro documento más
        print("\n📤 PASO 4: Subiendo 'presupuesto.xlsx' (documento nuevo - SE ADICIONA)")
        result4 = s3_manager.upload_document(
            file_content=b"Contenido del presupuesto en formato Excel",
            filename="presupuesto.xlsx",
            referencia_contrato=test_referencia,
            document_type='rpc',
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            metadata={'numero_rpc': 'RPC-001'},
            use_timestamp=False
        )
        
        if result4['success']:
            print(f"✅ Adicionado: {result4['s3_key']}")
            print(f"   Tamaño: {result4['size']} bytes")
        
        # Listar documentos final
        docs = s3_manager.list_documents(test_referencia, 'rpc')
        print(f"\n📋 Documentos FINALES en carpeta: {len(docs)}")
        for doc in docs:
            print(f"   - {Path(doc['s3_key']).name} ({doc['size']} bytes)")
        
        # PASO 5: Volver a actualizar el contrato
        print("\n📤 PASO 5: Subiendo 'contrato.pdf' (versión 3 - SOBREESCRIBE nuevamente)")
        result5 = s3_manager.upload_document(
            file_content=b"Contenido del contrato - Version 3 FINAL APROBADA",
            filename="contrato.pdf",
            referencia_contrato=test_referencia,
            document_type='rpc',
            content_type='application/pdf',
            metadata={'numero_rpc': 'RPC-001'},
            use_timestamp=False
        )
        
        if result5['success']:
            print(f"✅ Actualizado: {result5['s3_key']}")
            print(f"   Tamaño nuevo: {result5['size']} bytes")
        
        # Listar documentos final
        docs = s3_manager.list_documents(test_referencia, 'rpc')
        print(f"\n📋 Documentos FINALES en carpeta: {len(docs)}")
        print(f"   (Sigue siendo {len(docs)} porque 'contrato.pdf' se sobreescribió)")
        for doc in docs:
            print(f"   - {Path(doc['s3_key']).name} ({doc['size']} bytes)")
        
        # Resumen
        print("\n" + "=" * 80)
        print("📊 RESUMEN DEL COMPORTAMIENTO")
        print("=" * 80)
        print("✅ Documentos con MISMO NOMBRE → Se SOBREESCRIBEN")
        print("✅ Documentos con NOMBRE DIFERENTE → Se ADICIONAN a la carpeta")
        print(f"✅ Todos los documentos del contrato '{test_referencia}' están en una sola carpeta")
        print(f"✅ Estructura: contratos-rpc-docs/{test_referencia}/[archivos]")
        
        # Limpieza
        print("\n🗑️ Limpiando documentos de demostración...")
        for doc in docs:
            s3_manager.delete_document(doc['s3_key'])
        print(f"✅ {len(docs)} documentos eliminados")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en demostración: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = test_overwrite_behavior()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Demo interrumpida")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
