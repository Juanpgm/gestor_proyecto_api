# 🔑 Script rápido para codificar Service Account

## PowerShell (Windows):

```powershell
# Reemplaza la ruta con tu archivo descargado
$jsonPath = "C:\path\to\your\service-account-key.json"
$jsonContent = Get-Content $jsonPath -Raw
$bytes = [System.Text.Encoding]::UTF8.GetBytes($jsonContent)
$base64 = [System.Convert]::ToBase64String($bytes)

# Mostrar resultado (copia este string completo)
Write-Host "🔐 Copia este valor para FIREBASE_SERVICE_ACCOUNT_KEY:"
Write-Host $base64

# También guardarlo en un archivo temporal para facilitar copia
$base64 | Out-File -FilePath "service-account-base64.txt" -Encoding UTF8
Write-Host "✅ También guardado en: service-account-base64.txt"
```

## O manualmente:

```powershell
# Si tienes el archivo en tu directorio actual
[Convert]::ToBase64String([System.IO.File]::ReadAllBytes("service-account-key.json"))
```
