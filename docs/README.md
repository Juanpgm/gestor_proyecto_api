# 📚 Documentación API - Gestión de Proyectos

## 📖 Guías Disponibles

### 🐍 [Virtual Environment Setup](api_setup_docs/virtual_environment_setup.md)

**Guía completa paso a paso** para configurar la API en entornos virtuales.

- Configuración de entorno virtual
- Configuración de Firebase y base de datos de prueba
- Variables de entorno
- Instalación de dependencias
- Pruebas y verificación
- Solución de problemas

### ⚡ [Quick Reference](api_setup_docs/quick_reference.md)

**Comandos rápidos y referencia** para desarrolladores experimentados.

- Setup en 5 minutos
- Comandos de desarrollo más usados
- Troubleshooting rápido
- Checklist de verificación

---

## 🎯 Para Nuevos Desarrolladores

Si es tu primera vez configurando esta API:

1. **Lee primero**: [Virtual Environment Setup](api_setup_docs/virtual_environment_setup.md)
2. **Ten a mano**: [Quick Reference](api_setup_docs/quick_reference.md)

## 🚀 Para Desarrolladores Experimentados

Si ya tienes experiencia con Python y Firebase:

1. **Usa**: [Quick Reference](api_setup_docs/quick_reference.md)
2. **Consulta si hay problemas**: [Virtual Environment Setup - Troubleshooting](api_setup_docs/virtual_environment_setup.md#-solución-de-problemas)

---

## 🔧 Estructura de la API

```
gestor_proyecto_api/
├── api/
│   └── scripts/           # Operaciones de business logic
├── database/              # Configuración de Firebase
├── docs/                  # Documentación (esta carpeta)
├── main.py               # Punto de entrada de la API
└── requirements.txt      # Dependencias Python
```

## 🎯 Endpoints Principales

- **Health Check**: `GET /health`
- **Contratos**: `GET /contratos/init_contratos_seguimiento`
- **Documentación**: `GET /docs`

## 🔗 Enlaces Útiles

- [Repositorio GitHub](https://github.com/Juanpgm/gestor_proyecto_api)
- [Firebase Console](https://console.firebase.google.com/)
- [Google Cloud Console](https://console.cloud.google.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

**¿Necesitas ayuda?** Revisa las guías de setup o contacta al equipo de desarrollo.
