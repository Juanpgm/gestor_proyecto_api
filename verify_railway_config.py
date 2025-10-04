#!/usr/bin/env python3
"""
Script de verificación de configuración para Railway
Verifica que todas las variables de entorno estén correctamente configuradas
"""

import os
import json
import base64
from typing import Dict, List, Tuple

def check_environment_variables() -> Dict[str, any]:
    """Verificar variables de entorno requeridas"""
    results = {
        "status": "checking",
        "errors": [],
        "warnings": [],
        "success": []
    }
    
    # Variables obligatorias
    required_vars = {
        "ENVIRONMENT": "Entorno de ejecución"
    }
    
    # Variables opcionales pero recomendadas
    recommended_vars = {
        "FIREBASE_PROJECT_ID": "ID del proyecto Firebase (WIF puede detectarlo automáticamente)"
    }
    
    # Variables de autenticación (al menos una debe estar presente, WIF prioritario)
    auth_vars = {
        "GOOGLE_APPLICATION_CREDENTIALS_JSON": "Credenciales Workload Identity (RECOMENDADO)",
        "FIREBASE_SERVICE_ACCOUNT_KEY": "Service Account Key en base64 (FALLBACK)"
    }
    
    # Variables opcionales pero recomendadas
    optional_vars = {
        "FRONTEND_URL": "URL del frontend",
        "CORS_ORIGINS": "Orígenes CORS adicionales",
        "PORT": "Puerto del servidor",
        "LOG_LEVEL": "Nivel de logging"
    }
    
    # Verificar variables obligatorias
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            results["success"].append(f"✅ {var}: {description}")
        else:
            results["errors"].append(f"❌ {var}: {description} (REQUERIDO)")
    
    # Verificar variables recomendadas
    for var, description in recommended_vars.items():
        value = os.getenv(var)
        if value:
            results["success"].append(f"✅ {var}: {description}")
        else:
            results["warnings"].append(f"⚠️ {var}: {description} (RECOMENDADO)")
    
    # Verificar variables de autenticación (priorizar WIF)
    auth_configured = False
    wif_configured = False
    
    # Verificar WIF primero (prioritario)
    wif_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if wif_creds:
        results["success"].append(f"🔐 GOOGLE_APPLICATION_CREDENTIALS_JSON: Credenciales Workload Identity (RECOMENDADO)")
        auth_configured = True
        wif_configured = True
        
        try:
            creds = json.loads(wif_creds)
            if creds.get("type") == "external_account":
                results["success"].append(f"  ✅ Workload Identity válido - Configuración óptima")
            else:
                results["warnings"].append(f"  ⚠️ Workload Identity type no reconocido")
        except Exception as e:
            results["errors"].append(f"  ❌ Workload Identity JSON inválido: {str(e)}")
    
    # Verificar Service Account Key (fallback)
    sa_key = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")
    if sa_key:
        if wif_configured:
            results["warnings"].append(f"⚠️ FIREBASE_SERVICE_ACCOUNT_KEY: Configurado pero WIF toma prioridad")
        else:
            results["success"].append(f"✅ FIREBASE_SERVICE_ACCOUNT_KEY: Service Account Key en base64 (FALLBACK)")
            auth_configured = True
            
            # Validar formato específico
            if True:  # Always validate SA key format
                try:
                    decoded = base64.b64decode(sa_key).decode('utf-8')
                    creds = json.loads(decoded)
                    if creds.get("type") == "service_account":
                        results["success"].append(f"  📋 Service Account válido: {creds.get('client_email', 'N/A')}")
                    else:
                        results["warnings"].append(f"  ⚠️ Service Account type no reconocido")
                except Exception as e:
                    results["errors"].append(f"  ❌ Service Account Key inválido: {str(e)}")
    
    if not auth_configured:
        results["errors"].append("❌ Al menos una variable de autenticación es requerida:")
        results["errors"].append(f"   PRIORITARIO: GOOGLE_APPLICATION_CREDENTIALS_JSON (Workload Identity)")
        results["errors"].append(f"   FALLBACK: FIREBASE_SERVICE_ACCOUNT_KEY (Service Account Key)")
    
    # Verificar variables opcionales
    for var, description in optional_vars.items():
        value = os.getenv(var)
        if value:
            results["success"].append(f"✅ {var}: {description}")
        else:
            results["warnings"].append(f"⚠️ {var}: {description} (OPCIONAL)")
    
    # Determinar status final
    if results["errors"]:
        results["status"] = "failed"
    elif results["warnings"]:
        results["status"] = "warning"
    else:
        results["status"] = "success"
    
    return results

def check_firebase_project_consistency() -> Dict[str, any]:
    """Verificar consistencia del proyecto Firebase"""
    results = {
        "status": "checking",
        "errors": [],
        "warnings": [],
        "success": []
    }
    
    project_id = os.getenv("FIREBASE_PROJECT_ID")
    google_project = os.getenv("GOOGLE_CLOUD_PROJECT")
    
    if project_id:
        results["success"].append(f"✅ FIREBASE_PROJECT_ID: {project_id}")
        
        if google_project:
            if project_id == google_project:
                results["success"].append(f"✅ GOOGLE_CLOUD_PROJECT coincide")
            else:
                results["warnings"].append(f"⚠️ GOOGLE_CLOUD_PROJECT ({google_project}) != FIREBASE_PROJECT_ID ({project_id})")
        
        # Verificar Service Account si está configurado
        sa_key = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")
        if sa_key:
            try:
                decoded = base64.b64decode(sa_key).decode('utf-8')
                creds = json.loads(decoded)
                sa_project = creds.get("project_id")
                
                if sa_project == project_id:
                    results["success"].append(f"✅ Service Account project_id coincide")
                else:
                    results["errors"].append(f"❌ Service Account project_id ({sa_project}) != FIREBASE_PROJECT_ID ({project_id})")
            except Exception as e:
                results["errors"].append(f"❌ Error verificando Service Account: {str(e)}")
    
    # Determinar status
    if results["errors"]:
        results["status"] = "failed"
    elif results["warnings"]:
        results["status"] = "warning"
    else:
        results["status"] = "success"
    
    return results

def check_cors_configuration() -> Dict[str, any]:
    """Verificar configuración CORS"""
    results = {
        "status": "checking",
        "errors": [],
        "warnings": [],
        "success": []
    }
    
    frontend_url = os.getenv("FRONTEND_URL")
    cors_origins = os.getenv("CORS_ORIGINS")
    environment = os.getenv("ENVIRONMENT", "development")
    
    if environment == "production":
        if frontend_url:
            if frontend_url.startswith("https://"):
                results["success"].append(f"✅ FRONTEND_URL configurado: {frontend_url}")
            else:
                results["warnings"].append(f"⚠️ FRONTEND_URL debe usar HTTPS en producción: {frontend_url}")
        else:
            results["warnings"].append(f"⚠️ FRONTEND_URL recomendado en producción")
        
        if cors_origins:
            origins = [origin.strip() for origin in cors_origins.split(",")]
            https_origins = [origin for origin in origins if origin.startswith("https://")]
            
            if len(https_origins) == len(origins):
                results["success"].append(f"✅ CORS_ORIGINS configurado con HTTPS: {len(origins)} orígenes")
            else:
                results["warnings"].append(f"⚠️ Algunos CORS_ORIGINS no usan HTTPS: {origins}")
    else:
        results["success"].append(f"✅ Modo desarrollo - CORS flexible permitido")
    
    if results["errors"]:
        results["status"] = "failed"
    elif results["warnings"]:
        results["status"] = "warning"
    else:
        results["status"] = "success"
    
    return results

def generate_railway_config_summary() -> str:
    """Generar resumen de configuración para Railway Dashboard"""
    summary = []
    summary.append("# 🚄 CONFIGURACIÓN PARA RAILWAY DASHBOARD")
    summary.append("# Copia estas variables a tu proyecto Railway")
    summary.append("")
    
    # Variables básicas
    summary.append("# === BÁSICAS (OBLIGATORIAS) ===")
    summary.append(f"ENVIRONMENT=production")
    
    # Variables de autenticación (priorizar WIF)
    summary.append("")
    summary.append("# === AUTENTICACIÓN - MÉTODO 1: WORKLOAD IDENTITY (RECOMENDADO) ===")
    
    wif_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if wif_creds:
        summary.append(f"GOOGLE_APPLICATION_CREDENTIALS_JSON={wif_creds[:50]}...")
        summary.append("# FIREBASE_PROJECT_ID=opcional_con_wif  # WIF puede detectarlo automáticamente")
    else:
        summary.append("# Configurar con: .\\setup_workload_identity.ps1")
        summary.append("# GOOGLE_APPLICATION_CREDENTIALS_JSON=tu_workload_identity_json_completo")
        summary.append("# FIREBASE_PROJECT_ID=tu_proyecto_id  # Opcional con WIF")
    
    summary.append("")
    summary.append("# === AUTENTICACIÓN - MÉTODO 2: SERVICE ACCOUNT (FALLBACK) ===")
    
    sa_key = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")
    if sa_key and not wif_creds:
        summary.append(f"FIREBASE_PROJECT_ID={os.getenv('FIREBASE_PROJECT_ID', 'TU_PROYECTO_ID')}")
        summary.append(f"FIREBASE_SERVICE_ACCOUNT_KEY={sa_key[:50]}...")
    else:
        summary.append("# Solo usar si WIF no está disponible")
        summary.append("# FIREBASE_PROJECT_ID=tu_proyecto_id")
        summary.append("# FIREBASE_SERVICE_ACCOUNT_KEY=tu_service_account_key_base64")
    
    # Variables opcionales
    summary.append("")
    summary.append("# === OPCIONALES PERO RECOMENDADAS ===")
    
    frontend_url = os.getenv("FRONTEND_URL", "https://tu-frontend.vercel.app")
    summary.append(f"FRONTEND_URL={frontend_url}")
    
    cors_origins = os.getenv("CORS_ORIGINS", "")
    if cors_origins:
        summary.append(f"CORS_ORIGINS={cors_origins}")
    else:
        summary.append("# CORS_ORIGINS=https://otro-dominio.com,https://app2.com")
    
    return "\n".join(summary)

def main():
    """Función principal de verificación"""
    print("🔍 VERIFICADOR DE CONFIGURACIÓN PARA RAILWAY")
    print("=" * 60)
    
    # Verificar variables de entorno
    print("\n📋 Verificando variables de entorno...")
    env_check = check_environment_variables()
    
    # Mostrar resultados
    for success in env_check["success"]:
        print(success)
    
    for warning in env_check["warnings"]:
        print(warning)
    
    for error in env_check["errors"]:
        print(error)
    
    # Verificar consistencia del proyecto
    print("\n🔗 Verificando consistencia del proyecto...")
    project_check = check_firebase_project_consistency()
    
    for success in project_check["success"]:
        print(success)
    
    for warning in project_check["warnings"]:
        print(warning)
    
    for error in project_check["errors"]:
        print(error)
    
    # Verificar CORS
    print("\n🌐 Verificando configuración CORS...")
    cors_check = check_cors_configuration()
    
    for success in cors_check["success"]:
        print(success)
    
    for warning in cors_check["warnings"]:
        print(warning)
    
    for error in cors_check["errors"]:
        print(error)
    
    # Resumen final
    print("\n" + "=" * 60)
    
    total_errors = len(env_check["errors"]) + len(project_check["errors"]) + len(cors_check["errors"])
    total_warnings = len(env_check["warnings"]) + len(project_check["warnings"]) + len(cors_check["warnings"])
    
    if total_errors > 0:
        print(f"❌ CONFIGURACIÓN INCOMPLETA: {total_errors} errores, {total_warnings} advertencias")
        print("🔧 Corrige los errores antes de desplegar en Railway")
    elif total_warnings > 0:
        print(f"⚠️ CONFIGURACIÓN VÁLIDA CON ADVERTENCIAS: {total_warnings} advertencias")
        print("🚀 Puedes desplegar, pero revisa las advertencias")
    else:
        print("✅ CONFIGURACIÓN PERFECTA - Lista para Railway")
        print("🚀 ¡Despliega con confianza!")
    
    # Generar resumen para Railway
    print("\n📋 RESUMEN PARA RAILWAY DASHBOARD:")
    print("-" * 40)
    config_summary = generate_railway_config_summary()
    print(config_summary)
    
    # Guardar resumen en archivo
    with open("railway-config-summary.txt", "w", encoding="utf-8") as f:
        f.write(config_summary)
    
    print(f"\n💾 Resumen guardado en: railway-config-summary.txt")

if __name__ == "__main__":
    main()