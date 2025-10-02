# 🔧 Script para codificar Service Account en base64

## En Windows PowerShell:
```powershell
# Reemplaza la ruta con tu archivo descargado
$json = Get-Content "C:\path\to\service-account.json" -Raw
$bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
$base64 = [System.Convert]::ToBase64String($bytes)
Write-Output $base64
```

## En Linux/Mac:
```bash
base64 -i /path/to/service-account.json
```

## En Railway:
- Variable: `FIREBASE_SERVICE_ACCOUNT_KEY`
- Valor: El string base64 completo (sin saltos de línea)

## ⚠️ Importante:
- El base64 debe ser UNA sola línea
- No incluyas espacios ni saltos de línea
- Copia todo el string completo