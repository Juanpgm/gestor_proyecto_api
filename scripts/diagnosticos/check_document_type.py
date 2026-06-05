#!/usr/bin/env python3
"""
Script simple para verificar el tipo de documento
"""

import requests

def check_new_document():
    sheet_id = "1_86MibGyUiKQeYpSS2l7O7t_TyZ6yAUk"
    print(f"🔍 Verificando documento: {sheet_id}")
    
    # Probar descarga como Excel
    excel_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
    print(f"🧪 Probando descarga Excel...")
    
    try:
        response = requests.get(excel_url, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            size = len(response.content)
            print(f"✅ Descarga exitosa!")
            print(f"Content-Type: {content_type}")
            print(f"Tamaño: {size} bytes")
            return True
        else:
            print(f"❌ Error en descarga: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    check_new_document()