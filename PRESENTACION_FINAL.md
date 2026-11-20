# Guion para la sustentación final

Este guion organiza una presentación breve del proyecto SysHSENA. Completa los
datos del equipo, instructor, fecha y capturas reales antes de exponer.

## Diapositiva 1 — Portada

- SysHSENA: sistema web para alojamientos de La Guajira.
- Integrantes, programa de formación, instructor y fecha.

## Diapositiva 2 — Problema y contexto

- Registros separados de habitaciones, huéspedes, reservas y pagos.
- Riesgos de duplicidad, cruces de fechas y pérdida de control de saldos.
- Contexto regional de hoteles y posadas turísticas.

## Diapositiva 3 — Objetivos y alcance

- Centralizar el ciclo de gestión hotelera.
- Actores: administrador, recepcionista, gerente y cliente.
- Módulos incluidos y límites: no se integra pasarela de pago ni facturación
  electrónica.

## Diapositiva 4 — Diseño y tecnologías

- Python, Django, Django ORM, HTML5, CSS3 y Bootstrap.
- SQLite para demostración local; MySQL configurable para despliegue.
- Presentar el diagrama entidad-relación de
  [Análisis y diseño](./ANALISIS_Y_DISENO.md#10-modelo-entidad-relación).

## Diapositiva 5 — Demostración del cliente

- Registro e inicio de sesión.
- Catálogo con fotos y búsqueda por fechas/capacidad.
- Reserva con servicios opcionales y visualización del total estimado.
- Consulta de reservas e historial.

## Diapositiva 6 — Demostración operativa

- Administración de huéspedes, habitaciones y servicios.
- Confirmar reserva, registrar check-in y check-out.
- Registrar abonos, validar saldo y revisar pagos.

## Diapositiva 7 — Dashboard, reportes y calidad

- Mostrar habitaciones, ocupación, reservas, huéspedes e ingresos.
- Mostrar filtros, reservas, pagos, saldos e historial.
- Ejecutar `python manage.py test` y `python manage.py check`.
- Mencionar controles por rol y pruebas de reglas de negocio.

## Diapositiva 8 — Conclusiones y mejoras futuras

- Beneficios de centralizar la operación y la trazabilidad.
- Mejoras futuras posibles: pasarela de pagos, facturación electrónica,
  notificaciones y canales externos.
- Cierre y preguntas.
