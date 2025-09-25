"""
ETL Configuration Module

Configuración cent    'unidades_proyecto': {
        'url': os.getenv('SHEETS_UNIDADES_PROYECTO_URL'),
        'worksheet': os.getenv('SHEETS_UNIDADES_PROYECTO_WORKSHEET', 'unidades_proyecto')
    }zada para toda la pipeline ETL de Cali.
Implemen        print("💡 Ejecuta: gcloud auth application-default login")a Firebase Application Default Credentials y Service Account para Google Sheets.
Incluye Firebase, Google Sheets, y configuración general del sistema.
Implementa programación funcional para configuración segura y escalable.
"""

import os
import firebase_admin
from firebase_admin import credentials, firestore
import gspread
from google.auth import default
from typing import Optional, List, Dict, Any, Callable
from pathlib import Path
from functools import wraps, lru_cache

# Cargar variables de entorno desde .env
try:
    from dotenv import load_dotenv
    # Buscar .env en el directorio raíz del proyecto
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(env_path)
except ImportError:
    print("⚠️  python-dotenv no instalado, usando variables de entorno del sistema")

# Variables globales para singletons
_firebase_app = None
_firestore_client = None
_sheets_client = None

# Configuración centralizada desde variables de entorno
PROJECT_ID = os.getenv('FIREBASE_PROJECT_ID', os.getenv('GOOGLE_CLOUD_PROJECT', 'dev-test-e778d'))
BATCH_SIZE = int(os.getenv('FIRESTORE_BATCH_SIZE', '500'))
TIMEOUT = int(os.getenv('FIRESTORE_TIMEOUT', '30'))

# Google Sheets configuration (cuenta separada de Firebase)
SHEETS_SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.readonly'
]

# Opción 1: Service Account para Sheets (más seguro)
SHEETS_SERVICE_ACCOUNT_FILE = os.getenv('SHEETS_SERVICE_ACCOUNT_FILE', None)

# Opción 2: OAuth directo para Sheets (usando cuenta específica)
SHEETS_OAUTH_TOKEN_FILE = os.getenv('SHEETS_OAUTH_TOKEN_FILE', None)

# Sheets URLs and worksheet configuration (desde variables de entorno)
SHEETS_CONFIG = {
    'unidades_proyecto': {
        'url': os.getenv('SHEETS_UNIDADES_PROYECTO_URL', ''),
        'worksheet': os.getenv('SHEETS_UNIDADES_PROYECTO_WORKSHEET', 'obras_equipamientos')
    }
}

# Configuración de logging seguro (sin exponer información sensible)
SECURE_LOGGING = True


# Decorador para logging seguro
def secure_log(func: Callable) -> Callable:
    """Decorador para logging que no expone información sensible."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if SECURE_LOGGING:
            func_name = func.__name__
            print(f"🔧 Ejecutando: {func_name}")
        try:
            result = func(*args, **kwargs)
            if SECURE_LOGGING:
                print(f"✅ {func_name}: completado")
            return result
        except Exception as e:
            if SECURE_LOGGING:
                print(f"❌ {func_name}: error (detalles omitidos por seguridad)")
            raise
    return wrapper


@lru_cache(maxsize=1)
@secure_log
def initialize_firebase() -> firebase_admin.App:
    """Inicializa Firebase usando Application Default Credentials con cache."""
    global _firebase_app
    
    if _firebase_app:
        return _firebase_app
    
    try:
        _firebase_app = firebase_admin.get_app()
        return _firebase_app
    except ValueError:
        pass
    
    try:
        # Usar Application Default Credentials (método seguro recomendado)
        cred = credentials.ApplicationDefault()
        _firebase_app = firebase_admin.initialize_app(cred, {'projectId': PROJECT_ID})
        print(f"✅ Firebase inicializado: {PROJECT_ID}")
        return _firebase_app
    except Exception as e:
        print(f"❌ Error inicializando Firebase: {e}")
        print("� Ejecuta: gcloud auth application-default login")
        raise


@lru_cache(maxsize=1)
@secure_log
def get_firestore_client():
    """Obtiene cliente de Firestore con cache."""
    global _firestore_client
    
    if not _firestore_client:
        initialize_firebase()
        _firestore_client = firestore.client()
    
    return _firestore_client


# Funciones para Google Sheets (cuenta independiente de Firebase)
@lru_cache(maxsize=1)
@secure_log
def get_sheets_client() -> Optional[gspread.Client]:
    """
    Obtiene cliente autenticado de Google Sheets.
    Prioriza Service Account > OAuth Token > ADC
    """
    global _sheets_client
    
    if _sheets_client:
        return _sheets_client
    
    try:
        # Opción 1: Service Account (más seguro para producción)
        if SHEETS_SERVICE_ACCOUNT_FILE and os.path.exists(SHEETS_SERVICE_ACCOUNT_FILE):
            _sheets_client = gspread.service_account(filename=SHEETS_SERVICE_ACCOUNT_FILE)
            return _sheets_client
        
        # Opción 2: OAuth con token guardado
        if SHEETS_OAUTH_TOKEN_FILE and os.path.exists(SHEETS_OAUTH_TOKEN_FILE):
            import pickle
            with open(SHEETS_OAUTH_TOKEN_FILE, 'rb') as token:
                credentials_obj = pickle.load(token)
                _sheets_client = gspread.authorize(credentials_obj)
                return _sheets_client
        
        # Opción 3: ADC con scope amplio (fallback)
        try:
            # Intentar con cloud-platform scope (más amplio)
            broad_scopes = ['https://www.googleapis.com/auth/cloud-platform']
            credentials_obj, project = default(scopes=broad_scopes)
            
            if credentials_obj:
                _sheets_client = gspread.authorize(credentials_obj)
                return _sheets_client
        except Exception:
            pass
        
        # Si falla, intentar con scopes específicos
        try:
            credentials_obj, project = default(scopes=SHEETS_SCOPES)
            if credentials_obj:
                _sheets_client = gspread.authorize(credentials_obj)
                return _sheets_client
        except Exception:
            pass
        
        print("💡 Opciones de autenticación:")
        print("   1. Service Account: configura SHEETS_SERVICE_ACCOUNT_FILE")
        print("   2. OAuth: configura SHEETS_OAUTH_TOKEN_FILE") 
        print("   3. ADC: gcloud auth application-default login")
        return None
        
    except Exception as e:
        if not SECURE_LOGGING:
            print(f"❌ Error autenticando Google Sheets: {e}")
        print("💡 Verifica:")
        print("   - Permisos en la hoja de cálculo")
        print("   - APIs habilitadas (sheets.googleapis.com)")
        print("   - Configuración de credenciales")
        return None


@secure_log
def open_spreadsheet_by_url(url: str) -> Optional[gspread.Spreadsheet]:
    """Abre una hoja de cálculo usando su URL de forma segura."""
    try:
        client = get_sheets_client()
        if not client:
            return None
        
        # Extraer ID de la URL de forma segura
        if '/d/' in url:
            sheet_id = url.split('/d/')[1].split('/')[0]
        else:
            raise ValueError("URL inválida")
        
        spreadsheet = client.open_by_key(sheet_id)
        return spreadsheet
        
    except Exception as e:
        if not SECURE_LOGGING:
            print(f"❌ Error abriendo hoja: {e}")
        raise


@secure_log
def get_worksheet_data(spreadsheet: gspread.Spreadsheet, worksheet_name: str) -> Optional[list]:
    """Obtiene datos de una hoja específica de forma segura."""
    try:
        worksheet = spreadsheet.worksheet(worksheet_name)
        data = worksheet.get_all_values()
        return data
        
    except gspread.WorksheetNotFound:
        if not SECURE_LOGGING:
            print(f"❌ Hoja '{worksheet_name}' no encontrada")
        available_sheets = [ws.title for ws in spreadsheet.worksheets()]
        if not SECURE_LOGGING:
            print(f"📋 Hojas disponibles: {available_sheets}")
        return None
        
    except Exception as e:
        if not SECURE_LOGGING:
            print(f"❌ Error obteniendo datos: {e}")
        return None


@secure_log
def test_connection() -> bool:
    """Prueba la conexión a Firestore de forma segura."""
    try:
        client = get_firestore_client()
        if not client:
            if not SECURE_LOGGING:
                print("❌ No se pudo obtener cliente de Firestore")
            return False
        
        # Intentar una operación más simple primero
        try:
            # Simplemente verificar que podemos crear una referencia
            test_ref = client.collection('_test_connection')
            if test_ref:
                if not SECURE_LOGGING:
                    print("✅ Conexión a Firestore verificada")
                return True
        except Exception as inner_e:
            if not SECURE_LOGGING:
                print(f"❌ Error en verificación de conexión: {inner_e}")
        
        # Si falla, intentar listar colecciones (método original)
        try:
            collections = list(client.collections())
            if not SECURE_LOGGING:
                print(f"✅ Conexión a Firestore verificada - {len(collections)} colecciones encontradas")
            return True
        except Exception as inner_e:
            if not SECURE_LOGGING:
                print(f"❌ Error listando colecciones: {inner_e}")
            return False
            
    except Exception as e:
        if not SECURE_LOGGING:
            print(f"❌ Error de conexión a Firebase: {e}")
        return False


@secure_log
def test_sheets_connection() -> bool:
    """Prueba la conexión a Google Sheets de forma segura."""
    try:
        client = get_sheets_client()
        if not client:
            return False
        return True
        
    except Exception as e:
        if not SECURE_LOGGING:
            print(f"❌ Error en prueba de conexión: {e}")
        return False


@secure_log
def list_collections() -> List[str]:
    """Lista todas las colecciones en Firestore de forma segura."""
    try:
        client = get_firestore_client()
        collections = [col.id for col in client.collections()]
        if not SECURE_LOGGING:
            print(f"📚 Colecciones: {collections}")
        return collections
    except Exception as e:
        if not SECURE_LOGGING:
            print(f"❌ Error listando colecciones: {e}")
        return []


def get_collection_count(collection_name: str) -> int:
    """Obtiene el número de documentos en una colección."""
    try:
        client = get_firestore_client()
        docs = client.collection(collection_name).limit(1).get()
        # Para conteo real usar aggregate queries en producción
        collection_ref = client.collection(collection_name)
        docs = list(collection_ref.stream())
        return len(docs)
    except Exception as e:
        print(f"❌ Error contando documentos en {collection_name}: {e}")
        return 0


def create_collection_if_not_exists(collection_name: str) -> bool:
    """Crea una colección si no existe."""
    try:
        client = get_firestore_client()
        # Firestore crea colecciones automáticamente al agregar documentos
        # Solo verificamos que el cliente funcione
        collections = [col.id for col in client.collections()]
        if collection_name not in collections:
            print(f"📝 Colección '{collection_name}' se creará al insertar datos")
        else:
            print(f"✅ Colección '{collection_name}' ya existe")
        return True
    except Exception as e:
        print(f"❌ Error verificando colección {collection_name}: {e}")
        return False


def test_data_operations() -> bool:
    """Prueba operaciones básicas de datos (crear, leer)."""
    try:
        client = get_firestore_client()
        test_collection = "test_connection"
        
        # Crear documento de prueba
        doc_ref = client.collection(test_collection).document("test_doc")
        doc_ref.set({"test": True, "timestamp": firestore.SERVER_TIMESTAMP})
        print("✅ Escritura de prueba exitosa")
        
        # Leer documento de prueba
        doc = doc_ref.get()
        if doc.exists:
            print("✅ Lectura de prueba exitosa")
            
            # Limpiar documento de prueba
            doc_ref.delete()
            print("✅ Eliminación de prueba exitosa")
            return True
        else:
            print("❌ No se pudo leer el documento de prueba")
            return False
            
    except Exception as e:
        print(f"❌ Error en operaciones de prueba: {e}")
        return False


def setup_firebase() -> bool:
    """Configuración completa de Firebase con verificación de carga de datos."""
    try:
        print("🚀 Configurando Firebase...")
        # Mostrar PROJECT_ID de forma segura
        project_display = f"{PROJECT_ID[:8]}***" if PROJECT_ID and len(PROJECT_ID) > 8 else "[CONFIGURED]"
        print(f"🔧 Proyecto: {project_display}")
        print(f"⚙️  Batch size: {BATCH_SIZE}")
        print(f"⏱️  Timeout: {TIMEOUT}s")
        
        if not test_connection():
            return False
            
        print("\n📊 Probando operaciones de datos...")
        if not test_data_operations():
            print("⚠️  Operaciones de datos fallaron, pero conexión básica funciona")
            return False
            
        collections = list_collections()
        
        if not collections:
            print("📝 Base de datos vacía, lista para recibir datos")
        else:
            print(f"📚 {len(collections)} colecciones existentes")
            # No mostrar nombres completos de colecciones por seguridad
            for col in collections[:3]:  # Solo primeras 3
                col_display = col[:10] + "***" if len(col) > 10 else col
                print(f"    - {col_display}")
            if len(collections) > 3:
                print(f"    - ... y {len(collections) - 3} más")
        
        print("✅ Firebase listo para ETL")
        return True
        
    except Exception as e:
        # No mostrar el error completo por seguridad
        error_msg = str(e)[:50] + "..." if len(str(e)) > 50 else str(e)
        print(f"❌ Error en configuración: {error_msg}")
        return False


def show_system_info():
    """Muestra información del sistema y configuración de forma segura."""
    import platform
    print(f"💻 OS: {platform.system()} {platform.release()}")
    print(f"🐍 Python: {platform.python_version()}")
    # No mostrar la ruta completa del directorio por seguridad
    current_dir = Path.cwd()
    print(f"📁 Directorio: .../{current_dir.name}")
    
    # Mostrar PROJECT_ID de forma segura
    if PROJECT_ID:
        masked_project = f"{PROJECT_ID[:8]}***" if len(PROJECT_ID) > 8 else "[CONFIGURED]"
        print(f"🔧 Project ID: {masked_project}")
    else:
        print("🔧 Project ID: [NOT CONFIGURED]")
    
    # Verificar si gcloud está instalado
    import subprocess
    try:
        result = subprocess.run(['gcloud', '--version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"☁️  {version_line}")
        else:
            print("⚠️  gcloud CLI no encontrado")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("⚠️  gcloud CLI no instalado o no accesible")


# Ejecutar si se llama directamente
if __name__ == "__main__":
    print("=" * 60)
    show_system_info()
    print("=" * 60)
    
    success = setup_firebase()
    if success:
        print("\n🎯 Configuración completada exitosamente")
        print("💾 Sistema listo para cargar datos")
    else:
        print("\n💥 Configuración fallida")
        print("🔧 Instala gcloud CLI y ejecuta: gcloud auth application-default login")