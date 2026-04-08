# Configuración HTTP/2 para Gestor Proyecto API

## Estado Actual

**uvicorn[standard]** ya instalado incluye soporte HTTP/2 a través de `httptools` y `h11`.

## Habilitar HTTP/2

### Opción 1: Uvicorn con SSL (Recomendado para Producción)

HTTP/2 require SSL/TLS. Para habilitar:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --ssl-keyfile=./key.pem --ssl-certfile=./cert.pem
```

### Opción 2: Usar Reverse Proxy (Railway, Nginx, Caddy)

En producción (Railway), el reverse proxy ya maneja HTTP/2:

- **Railway**: Automáticamente habilita HTTP/2/3 sobre HTTPS
- **Nginx**: Configurar `listen 443 ssl http2;`
- **Caddy**: HTTP/2 habilitado por defecto

## Configuración Actual

El servidor está optimizado con:

✅ **GZip Compression**: Respuestas > 1KB  
✅ **Rate Limiting**: 30-60 requests/min en endpoints pesados  
✅ **APM Monitoring**: Métricas de Prometheus en `/metrics`  
✅ **Cache**: TTL de 5 minutos en endpoints costosos  
✅ **Timing Middleware**: Header `X-Response-Time` en todas las respuestas

## Verificar HTTP/2

```bash
# Con curl
curl -I --http2 ${API_BASE_URL}/

# Con browser DevTools
# Network tab → Protocol column debe mostrar "h2"
```

## Beneficios HTTP/2

- **Multiplexing**: Múltiples requests en una conexión
- **Server Push**: Envío proactivo de recursos
- **Header Compression**: Reducción de overhead
- **Binary Protocol**: Más eficiente que HTTP/1.1

## Notas

- HTTP/2 **requiere HTTPS** (TLS)
- Railway automáticamente proporciona HTTPS + HTTP/2
- En desarrollo local, HTTP/1.1 es suficiente
- Para testing con HTTP/2 local, usar certificados self-signed
