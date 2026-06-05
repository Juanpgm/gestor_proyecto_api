#!/usr/bin/env python3
"""
Script de configuración rápida para AWS S3
Guía al usuario para crear el archivo de credenciales
"""

import os
import json
import sys

def print_header(text):
    """Imprimir encabezado formateado"""
    print("\n" + "="*80)
    print(f"  {text}")
    print("="*80 + "\n")

def check_credentials_file():
    """Verificar si el archivo de credenciales existe"""
    creds_path = "context/aws_credentials.json"
    
    if os.path.exists(creds_path):
        print(f"✅ Archivo de credenciales encontrado: {creds_path}")
        return True
    else:
        print(f"❌ Archivo de credenciales NO encontrado: {creds_path}")
        return False

def create_credentials_file():
    """Crear el archivo de credenciales interactivamente"""
    print_header("CONFIGURACIÓN DE CREDENCIALES AWS S3")
    
    print("Este asistente te ayudará a crear el archivo de credenciales AWS.")
    print("\nNecesitas tener a mano:")
    print("  1. AWS Access Key ID")
    print("  2. AWS Secret Access Key")
    print("  3. Región de AWS (por defecto: us-east-1)")
    print("\n⚠️  IMPORTANTE: Estas credenciales son CONFIDENCIALES")
    print("   Nunca las compartas o las subas a control de versiones\n")
    
    proceed = input("¿Deseas continuar? (s/n): ").lower().strip()
    
    if proceed != 's':
        print("\n❌ Configuración cancelada")
        return False
    
    # Recopilar credenciales
    print("\n" + "-"*80)
    print("Ingresa tus credenciales AWS:")
    print("-"*80)
    
    access_key = input("\n1. AWS Access Key ID: ").strip()
    if not access_key:
        print("❌ Access Key ID es obligatorio")
        return False
    
    secret_key = input("2. AWS Secret Access Key: ").strip()
    if not secret_key:
        print("❌ Secret Access Key es obligatorio")
        return False
    
    region = input("3. AWS Region [us-east-1]: ").strip() or "us-east-1"
    
    bucket_emprestito = input("4. Bucket de Empréstito [contratos-emprestito]: ").strip() or "contratos-emprestito"
    
    bucket_general = input("5. Bucket General [unidades-proyecto-documents]: ").strip() or "unidades-proyecto-documents"
    
    # Crear estructura de credenciales
    credentials = {
        "aws_access_key_id": access_key,
        "aws_secret_access_key": secret_key,
        "aws_region": region,
        "bucket_name": bucket_general,
        "bucket_name_emprestito": bucket_emprestito
    }
    
    # Crear directorio si no existe
    os.makedirs("context", exist_ok=True)
    
    # Guardar archivo
    creds_path = "context/aws_credentials.json"
    
    try:
        with open(creds_path, 'w') as f:
            json.dump(credentials, f, indent=2)
        
        print(f"\n✅ Archivo de credenciales creado exitosamente: {creds_path}")
        print("\n📋 Resumen de configuración:")
        print(f"   - Región: {region}")
        print(f"   - Bucket Empréstito: {bucket_emprestito}")
        print(f"   - Bucket General: {bucket_general}")
        print(f"   - Access Key: {access_key[:10]}...")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error creando archivo: {e}")
        return False

def verify_gitignore():
    """Verificar que el archivo de credenciales está en .gitignore"""
    print_header("VERIFICACIÓN DE SEGURIDAD")
    
    gitignore_path = ".gitignore"
    
    if not os.path.exists(gitignore_path):
        print("⚠️  Archivo .gitignore no encontrado")
        return False
    
    with open(gitignore_path, 'r') as f:
        content = f.read()
    
    # Verificar que context/ o aws_credentials.json están ignorados
    if 'context/' in content or 'aws_credentials.json' in content or '*.json' in content:
        print("✅ Archivo de credenciales protegido por .gitignore")
        return True
    else:
        print("⚠️  Archivo de credenciales podría no estar protegido")
        print("   Se recomienda agregar 'context/' o 'aws_credentials.json' al .gitignore")
        return False

def check_boto3():
    """Verificar si boto3 está instalado"""
    print_header("VERIFICACIÓN DE DEPENDENCIAS")
    
    try:
        import boto3
        print(f"✅ boto3 instalado - Versión: {boto3.__version__}")
        return True
    except ImportError:
        print("❌ boto3 NO está instalado")
        print("\n   Para instalar:")
        print("   pip install boto3")
        return False

def run_connection_test():
    """Ejecutar test de conexión si es posible"""
    print_header("PRUEBA DE CONEXIÓN")
    
    try:
        from api.utils.s3_document_manager import S3DocumentManager
        
        print("Inicializando S3DocumentManager...")
        manager = S3DocumentManager()
        
        print(f"✅ Manager inicializado")
        print(f"   - Bucket: {manager.bucket_name}")
        print(f"   - Región: {manager.region}")
        
        print("\nVerificando acceso al bucket...")
        if manager.verify_bucket_exists():
            print(f"✅ Bucket '{manager.bucket_name}' accesible")
            return True
        else:
            print(f"❌ Bucket '{manager.bucket_name}' no accesible")
            print("\n   Posibles causas:")
            print("   - El bucket no existe en AWS")
            print("   - No tienes permisos para acceder al bucket")
            print("   - Las credenciales son incorrectas")
            return False
            
    except Exception as e:
        print(f"❌ Error durante la prueba: {e}")
        return False

def main():
    """Función principal"""
    print_header("🔧 CONFIGURADOR AWS S3 - SISTEMA DE EMPRÉSTITO")
    
    print("Este script te ayudará a configurar las credenciales AWS S3")
    print("para el sistema de gestión de documentos de empréstito.\n")
    
    # Paso 1: Verificar si ya existe el archivo
    if check_credentials_file():
        overwrite = input("\n¿Deseas sobrescribir las credenciales existentes? (s/n): ").lower().strip()
        if overwrite != 's':
            print("\nUsando credenciales existentes...")
        else:
            if not create_credentials_file():
                sys.exit(1)
    else:
        # Crear archivo de credenciales
        if not create_credentials_file():
            sys.exit(1)
    
    # Paso 2: Verificar .gitignore
    verify_gitignore()
    
    # Paso 3: Verificar boto3
    if not check_boto3():
        print("\n⚠️  Instala boto3 antes de continuar")
        sys.exit(1)
    
    # Paso 4: Probar conexión
    print("\n")
    test_connection = input("¿Deseas probar la conexión a S3? (s/n): ").lower().strip()
    
    if test_connection == 's':
        success = run_connection_test()
        
        if success:
            print_header("🎉 ¡CONFIGURACIÓN COMPLETADA EXITOSAMENTE!")
            print("El sistema está listo para subir documentos a S3")
        else:
            print_header("⚠️  CONFIGURACIÓN COMPLETADA CON ADVERTENCIAS")
            print("Verifica la configuración de AWS antes de continuar")
    else:
        print_header("✅ CONFIGURACIÓN GUARDADA")
        print("Para probar la conexión, ejecuta:")
        print("  python test_s3_connection.py")
    
    print("\n📖 Para más información, consulta:")
    print("   - SOLUCION_ERROR_S3.md")
    print("   - SETUP_S3_EMPRESTITO.md")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Configuración cancelada por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
