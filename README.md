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

## Correo para verificar reservas

En desarrollo, el código de verificación se imprime en la consola del servidor
Django. Para enviarlo por correo real, configura las siguientes variables de
entorno con las credenciales de un proveedor SMTP (no las guardes en el código):

```powershell
$env:EMAIL_HOST = "smtp.example.com"
$env:EMAIL_PORT = "587"
$env:EMAIL_HOST_USER = "cuenta@example.com"
$env:EMAIL_HOST_PASSWORD = "contraseña-del-proveedor"
$env:EMAIL_USE_TLS = "true"
$env:EMAIL_USE_SSL = "false"
$env:DEFAULT_FROM_EMAIL = "Hotel Taroa <cuenta@example.com>"
```

La verificación del correo no procesa ni confirma pagos: la solicitud queda
pendiente de pago real y revisión de recepción.

## Funcionalidades

- Roles de Administrador, Recepcionista, Gerente y Cliente.
- Gestión de alojamiento, tipos de habitación, habitaciones, huéspedes,
  servicios, reservas y pagos.
- Disponibilidad por rango de fechas, capacidad y mantenimiento.
- Confirmación, check-in y check-out con sincronización del estado de habitación.
- Servicios asociados a reservas, valor total, pagos parciales y saldo.
- Solicitudes de cancelación para clientes y decisión desde recepción.
- Verificación por correo antes de enviar una solicitud de reserva.
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
