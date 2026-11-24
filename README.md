# SysHSENA · Hotel Taroa

Sistema web Django para administrar alojamientos, habitaciones, huéspedes,
reservas, pagos y servicios turísticos en La Guajira.

## Requisitos

- Python 3.12 o posterior.
- MySQL 8 para despliegue (opcional para desarrollo local).
- Dependencias de `requirements.txt`.

## Instalación local

En Windows PowerShell, desde la raíz del proyecto:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

La configuración local usa SQLite por defecto. El primer usuario creado como
superusuario puede acceder a todas las funciones y asignar los roles desde
Usuarios.

## Configuración MySQL

Configura estas variables de entorno antes de ejecutar migraciones o iniciar
el servidor:

```powershell
$env:DB_ENGINE = "mysql"
$env:DB_NAME = "hotel_taroa"
$env:DB_USER = "usuario_mysql"
$env:DB_PASSWORD = "contraseña"
$env:DB_HOST = "127.0.0.1"
$env:DB_PORT = "3306"
$env:DJANGO_SECRET_KEY = "una-clave-aleatoria-larga"
$env:DJANGO_DEBUG = "false"
$env:DJANGO_ALLOWED_HOSTS = "midominio.com"
$env:SECURE_SSL_REDIRECT = "true"
$env:SECURE_HSTS_SECONDS = "31536000"
```

No uses la clave de desarrollo ni `DEBUG=true` en un despliegue público.
La configuración de producción redirige a HTTPS y usa cookies seguras y HSTS;
actívala únicamente cuando el dominio ya esté servido correctamente por HTTPS.

## Funcionalidades

- Roles de Administrador, Recepcionista, Gerente y Cliente.
- Gestión de alojamiento, tipos de habitación, habitaciones, huéspedes,
  servicios, reservas y pagos.
- Disponibilidad por rango de fechas, capacidad y mantenimiento.
- Confirmación, check-in y check-out con sincronización del estado de habitación.
- Abono automático del 50% al confirmar y registro del saldo restante al hacer
  check-in, además de pagos parciales de servicios y consumos.
- Solicitudes de cancelación para clientes y decisión desde recepción.
- Indicadores, filtros y reportes de reservas, ocupación, ingresos, huéspedes y
  servicios vendidos.
- Configuración regional del alojamiento, fotografía por URL y sitios turísticos
  cercanos.
- Carga de fotografías locales del alojamiento y habitaciones, además de URL
  externas.
- Indicador gráfico y accesible de ocupación en el dashboard.

Consulta el [manual de usuario](MANUAL_USUARIO.md) para los flujos por rol.
La arquitectura, el modelo de datos y los requerimientos están en la
[documentación técnica](DOCUMENTACION_TECNICA.md).
La entrega de análisis, historias de usuario, casos de uso, modelo de datos y
trazabilidad con la guía se encuentra en [Análisis y diseño](ANALISIS_Y_DISENO.md).
El guion sugerido para la sustentación está en [Presentación final](PRESENTACION_FINAL.md).
