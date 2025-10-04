import os
import sys

def sanitize_file(filepath):
    """Sanitizar archivo eliminando datos sensibles"""
    if not os.path.exists(filepath):
        return
    
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Reemplazar project IDs sensibles
    content = content.replace('dev-test-e778d', 'your-project-id')
    content = content.replace('unidad-cumplimiento-aa245', 'your-project-id')
    
    # Escribir contenido sanitizado
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else 'setup_railway_credentials.py'
    sanitize_file(filepath)