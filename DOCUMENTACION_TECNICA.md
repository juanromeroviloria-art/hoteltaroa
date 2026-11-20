# Documentación técnica — SysHSENA

## Propósito y alcance

SysHSENA centraliza la operación de alojamientos de La Guajira: catálogo del
alojamiento y sus habitaciones, huéspedes, reservas, pagos y servicios. Las
reglas de negocio se validan en formularios y operaciones de Django; las
plantillas HTML presentan paneles, formularios, búsquedas, filtros y reportes.

## Arquitectura

- **Presentación:** Django Templates, HTML5, CSS propio y Bootstrap 5.
- **Aplicación:** Python y Django; las vistas exponen los flujos y los módulos
  `gestion/operations.py` gestionan transiciones transaccionales.
- **Autorización:** roles de la aplicación consultados desde el perfil de
  usuario; `gestion/permissions.py` centraliza las comprobaciones.
- **Persistencia:** Django ORM y migraciones. SQLite es el valor predeterminado
  de desarrollo; MySQL se habilita mediante `DB_ENGINE=mysql`.
- **Archivos multimedia:** las fotos del alojamiento y habitaciones se cargan
  al almacenamiento configurado en `MEDIA_ROOT`; en desarrollo se sirven bajo
  `MEDIA_URL`, y en producción deben servirse desde un almacenamiento/web server
  configurado para medios.
- **Pruebas:** `gestion/tests.py` cubre reservas, disponibilidad, estados
  operativos, saldos y permisos.

## Modelo de datos

| Entidad | Responsabilidad y relaciones |
|---|---|
| `User` | Cuenta autenticable de Django. |
| `Rol` | Administrador, Recepcionista, Gerente o Cliente. |
| `Usuario` | Perfil de acceso; uno a uno con `User`, muchos perfiles pertenecen a un rol. |
| `Alojamiento` | Datos de contacto y ubicación, foto cargada o por URL, servicios disponibles y sitios turísticos. |
| `TipoHabitacion` | Tipo y capacidad máxima. |
| `Habitacion` | Número, piso, precio, estado y foto cargada o por URL; pertenece a un alojamiento y tipo. |
| `Huesped` | Identidad y contacto; opcionalmente vinculado uno a uno con una cuenta. |
| `Reserva` | Huésped, habitación, fechas, cantidad, estado, usuario creador y tarifa nocturna congelada. |
| `Pago` | Abonos de una reserva, método, fecha y referencia. |
| `Servicio` | Catálogo de servicios con precio y estado activo. |
| `ServicioReserva` | Servicio, cantidad y precio unitario histórico de una reserva. |
| `SolicitudCancelacion` | Motivo y decisión de la solicitud de cancelación de un huésped. |

Relaciones centrales: un huésped y una habitación pueden tener varias reservas;
una reserva puede tener varios pagos y servicios; un alojamiento ofrece varios
servicios y contiene habitaciones. El número de habitación es único dentro de
cada alojamiento.

## Reglas de negocio implementadas

1. No se crean ni editan reservas que se crucen con reservas pendientes,
   confirmadas o en curso de la misma habitación. Las solicitudes se validan
   bajo bloqueo de la habitación para evitar conflictos concurrentes.
2. La salida debe ser posterior a la entrada y el número de huéspedes no puede
   superar la capacidad del tipo.
3. Las habitaciones en mantenimiento no se publican ni reservan.
4. Solo una reserva confirmada admite check-in; este marca la reserva en curso
   y la habitación ocupada.
5. Solo una reserva en curso admite check-out; este la finaliza y libera la
   habitación. Una reserva en curso no se puede cancelar ni eliminar.
6. El total conserva la tarifa nocturna vigente al reservar y suma los
   servicios asociados. Los pagos son abonos y no superan el saldo pendiente.
7. El cliente solo consulta y solicita la cancelación de sus propias reservas;
   recepción resuelve la solicitud.
8. Las rutas administrativas y operativas se restringen por rol y las acciones
   que modifican datos requieren POST y protección CSRF.

## Requerimientos funcionales

- **RF-001:** crear cuentas e iniciar/cerrar sesión.
- **RF-002:** actualizar el perfil y administrar roles y usuarios.
- **RF-003:** configurar alojamiento, servicios y habitaciones.
- **RF-004:** registrar y consultar huéspedes.
- **RF-005:** consultar disponibilidad por fechas y capacidad.
- **RF-006:** crear, consultar, modificar y cancelar reservas sin conflictos.
- **RF-007:** confirmar reservas y registrar check-in/check-out.
- **RF-008:** asociar servicios y calcular totales.
- **RF-009:** registrar pagos parciales, historial y saldo.
- **RF-010:** consultar indicadores del establecimiento.
- **RF-011:** filtrar reportes de reservas, ingresos, ocupación y huéspedes.
- **RF-012:** consultar servicios vendidos y el historial de reservas.

## Requerimientos no funcionales

- **RNF-001 Seguridad:** autenticación, permisos por rol, CSRF, contraseñas de
  Django y configuración de secretos mediante entorno.
- **RNF-002 Usabilidad:** navegación en español, mensajes de validación y
  formularios etiquetados.
- **RNF-003 Responsive:** grillas adaptables y tablas desplazables en móvil.
- **RNF-004 Integridad:** claves foráneas, restricciones, transacciones y
  validación de reglas de negocio.
- **RNF-005 Rendimiento:** ORM, `select_related`, `prefetch_related`, agregados,
  filtros y paginación en listados.
- **RNF-006 Mantenibilidad:** separación de modelos, formularios, permisos,
  operaciones, vistas, plantillas y migraciones.
- **RNF-007 Control de versiones:** Git; `.gitignore` excluye entornos, bases
  locales, medios y secretos.

## Puesta en marcha y operación

1. Instala `requirements.txt` y ejecuta `python manage.py migrate`.
2. Crea el primer administrador con `python manage.py createsuperuser`.
3. Inicia el servidor con `python manage.py runserver`.
4. Para MySQL configura `DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`,
   `DB_HOST` y `DB_PORT`. En despliegues configura además `DJANGO_SECRET_KEY`,
   `DJANGO_DEBUG=false` y `DJANGO_ALLOWED_HOSTS`.
5. Ejecuta las pruebas con `python manage.py test gestion` y los chequeos con
   `python manage.py check`.

La configuración local no sustituye la configuración de producción. En
producción deben usarse una clave secreta propia, hosts explícitos, HTTPS,
copias de seguridad y credenciales de base de datos con privilegios limitados.
