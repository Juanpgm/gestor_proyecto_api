#!/usr/bin/env python3
"""
Script de verificación de seguridad para credenciales AWS
Asegura que las credenciales están protegidas y no se subirán a GitHub
"""

import os
import sys
import subprocess

def print_header(text, emoji="🔐"):
    """Imprimir encabezado formateado"""
    print("\n" + "="*80)
    print(f"  {emoji} {text}")
    print("="*80 + "\n")

def check_gitignore():
    """Verificar que .gitignore protege las credenciales"""
    print_header("VERIFICACIÓN DE .GITIGNORE", "🛡️")
    
    if not os.path.exists('.gitignore'):
        print("❌ Archivo .gitignore no encontrado")
        return False
    
    with open('.gitignore', 'r') as f:
        content = f.read()
    
    patterns = [
        'credentials/',
        'context/',
        '*.json'
    ]
    
    found = []
    missing = []
    
    for pattern in patterns:
        if pattern in content:
            found.append(pattern)
            print(f"✅ Patrón protegido: {pattern}")
        else:
            missing.append(pattern)
            print(f"⚠️  Patrón faltante: {pattern}")
    
    if missing:
        print(f"\n⚠️  Algunos patrones no están en .gitignore")
        print(f"   Se recomienda agregar: {', '.join(missing)}")
        return False
    
    print(f"\n✅ .gitignore está correctamente configurado")
    return True

def check_git_tracking():
    """Verificar que las credenciales NO están siendo trackeadas por git"""
    print_header("VERIFICACIÓN DE GIT TRACKING", "📊")
    
    try:
        # Verificar archivos en staging/tracking
        result = subprocess.run(
            ['git', 'ls-files'],
            capture_output=True,
            text=True,
            check=True
        )
        
        tracked_files = result.stdout.split('\n')
        sensitive_files = [
            'credentials/aws_credentials.json',
            'context/aws_credentials.json',
            '.env.production'
        ]
        
        found_sensitive = []
        for file in sensitive_files:
            if file in tracked_files:
                found_sensitive.append(file)
                print(f"❌ ALERTA: {file} está siendo trackeado por git")
        
        if found_sensitive:
            print(f"\n⚠️  CRÍTICO: Archivos sensibles en git!")
            print(f"   Ejecutar: git rm --cached {' '.join(found_sensitive)}")
            return False
        
        print("✅ Ningún archivo sensible está siendo trackeado")
        
        # Verificar con git check-ignore
        files_to_check = [
            'credentials/aws_credentials.json',
            'context/aws_credentials.json'
        ]
        
        for file in files_to_check:
            if os.path.exists(file):
                result = subprocess.run(
                    ['git', 'check-ignore', '-v', file],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    print(f"✅ {file} está correctamente ignorado")
                else:
                    print(f"⚠️  {file} podría no estar protegido")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Error ejecutando git: {e}")
        return False
    except FileNotFoundError:
        print("⚠️  Git no está instalado o no es un repositorio git")
        return False

def check_credentials_exist():
    """Verificar que los archivos de credenciales existen"""
    print_header("VERIFICACIÓN DE ARCHIVOS DE CREDENCIALES", "📁")
    
    files = {
        'credentials/aws_credentials.json': 'Credenciales reales (PRIVADO)',
        'credentials/aws_credentials.json.example': 'Plantilla de ejemplo (PÚBLICO)',
        'context/aws_credentials.json': 'Copia de compatibilidad (PRIVADO)'
    }
    
    all_ok = True
    for file, description in files.items():
        if os.path.exists(file):
            print(f"✅ {file}")
            print(f"   → {description}")
        else:
            print(f"⚠️  {file} NO EXISTE")
            print(f"   → {description}")
            if 'example' not in file:
                all_ok = False
    
    return all_ok

def check_env_variables():
    """Verificar configuración de variables de entorno (opcional)"""
    print_header("VERIFICACIÓN DE VARIABLES DE ENTORNO", "🌐")
    
    env_vars = [
        'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY',
        'AWS_REGION',
        'S3_BUCKET_EMPRESTITO'
    ]
    
    found_vars = []
    missing_vars = []
    
    for var in env_vars:
        if os.getenv(var):
            found_vars.append(var)
            value = os.getenv(var)
            # Mostrar solo primeros caracteres por seguridad
            masked = value[:8] + '...' if len(value) > 8 else '***'
            print(f"✅ {var} = {masked}")
        else:
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n⚠️  Variables de entorno no configuradas: {', '.join(missing_vars)}")
        print("   (Normal en desarrollo - se usan archivos locales)")
    
    if found_vars:
        print(f"\n✅ Variables de entorno configuradas para producción")
        return True
    else:
        print(f"\n📝 Usando archivos locales (desarrollo)")
        return None  # No es error, es esperado en desarrollo

def check_git_history():
    """Verificar que no hay credenciales en el historial de git"""
    print_header("VERIFICACIÓN DE HISTORIAL GIT", "📜")
    
    try:
        # Buscar en el historial
        result = subprocess.run(
            ['git', 'log', '--all', '--full-history', '--', '**/aws_credentials.json'],
            capture_output=True,
            text=True,
            check=True
        )
        
        if result.stdout.strip():
            print("⚠️  Se encontraron credenciales en el historial de git")
            print("   Esto puede ser un riesgo de seguridad")
            print("\n   Para limpiar el historial:")
            print("   1. Usar BFG Repo-Cleaner: https://rtyley.github.io/bfg-repo-cleaner/")
            print("   2. O usar git-filter-repo")
            return False
        else:
            print("✅ No se encontraron credenciales en el historial de git")
            return True
            
    except subprocess.CalledProcessError:
        print("⚠️  No se pudo verificar el historial de git")
        return None
    except FileNotFoundError:
        print("⚠️  Git no está disponible")
        return None

def generate_security_report():
    """Generar reporte de seguridad completo"""
    print_header("REPORTE DE SEGURIDAD AWS S3", "🔐")
    
    results = {
        'gitignore': check_gitignore(),
        'tracking': check_git_tracking(),
        'files': check_credentials_exist(),
        'env': check_env_variables(),
        'history': check_git_history()
    }
    
    print_header("RESUMEN DEL ANÁLISIS", "📊")
    
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)
    
    print(f"✅ Verificaciones exitosas: {passed}")
    print(f"❌ Verificaciones fallidas: {failed}")
    print(f"⚠️  Verificaciones omitidas: {skipped}")
    
    if failed > 0:
        print("\n❌ ATENCIÓN: Hay problemas de seguridad que deben resolverse")
        print("\n📝 Acciones recomendadas:")
        
        if not results['gitignore']:
            print("   1. Actualizar .gitignore con patrones de protección")
        
        if not results['tracking']:
            print("   2. Remover archivos sensibles de git tracking")
            print("      Ejecutar: git rm --cached credentials/aws_credentials.json")
        
        if not results['files']:
            print("   3. Crear archivo de credenciales en credentials/")
        
        if results['history'] is False:
            print("   4. Limpiar historial de git con BFG Repo-Cleaner")
        
        return False
    
    elif passed >= 3:
        print("\n✅ SEGURIDAD VERIFICADA")
        print("   Las credenciales AWS están correctamente protegidas")
        print("   Es seguro trabajar con el repositorio")
        return True
    
    else:
        print("\n⚠️  Verificación parcial")
        print("   Algunas comprobaciones no pudieron completarse")
        return None

def main():
    """Función principal"""
    print("\n" + "🔐 " + "="*78)
    print("  VERIFICADOR DE SEGURIDAD DE CREDENCIALES AWS S3")
    print("  " + "="*78)
    
    try:
        result = generate_security_report()
        
        print("\n" + "="*80)
        if result is True:
            print("  🎉 ¡TODO CORRECTO! Credenciales protegidas")
        elif result is False:
            print("  ⚠️  REQUIERE ATENCIÓN - Ver acciones recomendadas arriba")
            sys.exit(1)
        else:
            print("  📝 Verificación completada con advertencias")
        print("="*80 + "\n")
        
        print("📚 Para más información:")
        print("   - CONFIGURACION_PRODUCCION_S3.md")
        print("   - README_SOLUCION_S3.md")
        
    except KeyboardInterrupt:
        print("\n\n❌ Verificación cancelada por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
