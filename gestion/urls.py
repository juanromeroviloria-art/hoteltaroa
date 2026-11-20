from django.urls import path
from . import views

urlpatterns = [
    
    path("", views.inicio, name="inicio"),
path("login/", views.login_usuario, name="login"),
    path("panel/", views.panel, name="panel"),
    path("perfil/", views.perfil, name="perfil"),
    path(
        "alojamiento/configurar/",
        views.alojamiento_configurar,
        name="alojamiento_configurar",
    ),
    path("cerrar-sesion/", views.cerrar_sesion, name="cerrar_sesion"),

    # Usuarios
    path("usuarios/", views.usuarios, name="usuarios"),
    path("usuarios/crear/", views.usuario_crear, name="usuario_crear"),
    path("usuarios/<int:usuario_id>/editar/", views.usuario_editar, name="usuario_editar"),
    path("usuarios/<int:usuario_id>/estado/", views.usuario_estado, name="usuario_estado"),
    path("usuarios/<int:usuario_id>/eliminar/", views.usuario_eliminar, name="usuario_eliminar"),

    # Roles
    path("roles/", views.roles, name="roles"),
    path("roles/crear/", views.rol_crear, name="rol_crear"),
    path("roles/<int:rol_id>/editar/", views.rol_editar, name="rol_editar"),
    path("roles/<int:rol_id>/eliminar/", views.rol_eliminar, name="rol_eliminar"),

    # Habitaciones
    path("habitaciones/", views.habitaciones, name="habitaciones"),
    path("habitaciones/crear/", views.habitacion_crear, name="habitacion_crear"),
    path("habitaciones/<int:habitacion_id>/editar/", views.habitacion_editar, name="habitacion_editar"),
    path("habitaciones/<int:habitacion_id>/eliminar/", views.habitacion_eliminar, name="habitacion_eliminar"),

    # Tipos de habitación
    path("tipos-habitacion/", views.tipos_habitacion, name="tipos_habitacion"),
    path("tipos-habitacion/crear/", views.tipo_habitacion_crear, name="tipo_habitacion_crear"),
    path("tipos-habitacion/<int:tipo_id>/editar/", views.tipo_habitacion_editar, name="tipo_habitacion_editar"),
    path("tipos-habitacion/<int:tipo_id>/eliminar/", views.tipo_habitacion_eliminar, name="tipo_habitacion_eliminar"),

    # Servicios
    path("servicios/", views.servicios, name="servicios"),
    path("servicios/crear/", views.servicio_crear, name="servicio_crear"),
    path("servicios/<int:servicio_id>/editar/", views.servicio_editar, name="servicio_editar"),
    path("servicios/<int:servicio_id>/eliminar/", views.servicio_eliminar, name="servicio_eliminar"),

    # Huéspedes
    path("huespedes/", views.huespedes, name="huespedes"),
    path("huespedes/crear/", views.huesped_crear, name="huesped_crear"),
    path("huespedes/<int:huesped_id>/editar/", views.huesped_editar, name="huesped_editar"),
    path("huespedes/<int:huesped_id>/eliminar/", views.huesped_eliminar, name="huesped_eliminar"),


        # Reservas
    path("reservas/", views.reservas, name="reservas"),
    path("reservas/crear/", views.reserva_crear, name="reserva_crear"),
    path("reservas/<int:reserva_id>/editar/", views.reserva_editar, name="reserva_editar"),
    path("reservas/<int:reserva_id>/eliminar/", views.reserva_eliminar, name="reserva_eliminar"),
    path(
        "reservas/<int:reserva_id>/confirmar/",
        views.reserva_confirmar,
        name="reserva_confirmar",
    ),
    path(
        "reservas/<int:reserva_id>/cancelar/",
        views.reserva_cancelar,
        name="reserva_cancelar",
    ),
    path(
        "reservas/<int:reserva_id>/check-in/",
        views.reserva_check_in,
        name="reserva_check_in",
    ),
    path(
        "reservas/<int:reserva_id>/check-out/",
        views.reserva_check_out,
        name="reserva_check_out",
    ),
    path(
        "reservas/<int:reserva_id>/factura/",
        views.reserva_factura,
        name="reserva_factura",
    ),
    path(
        "reservas/<int:reserva_id>/servicios/",
        views.reserva_servicio,
        name="reserva_servicio",
    ),
    path(
        "solicitudes-cancelacion/<int:solicitud_id>/resolver/",
        views.resolver_solicitud_cancelacion,
        name="resolver_solicitud_cancelacion",
    ),
    path("pagos/", views.pagos, name="pagos"),
    path("pagos/crear/", views.pago_crear, name="pago_crear"),
    path("pagos/<int:pago_id>/editar/", views.pago_editar, name="pago_editar"),
    path("pagos/<int:pago_id>/eliminar/", views.pago_eliminar, name="pago_eliminar"),
    path("consumos/", views.consumos, name="consumos"),
    path("reportes/", views.reportes, name="reportes"),

         # Vista del cliente
    path(
        "cliente/registro/",
        views.registro_cliente,
        name="registro_cliente"
    ),
    path(
        "cliente/login/",
        views.login_cliente,
        name="login_cliente"
    ),
    path(
        "cliente/habitaciones/",
        views.habitaciones_cliente,
        name="habitaciones_cliente"
    ),
    path(
        "cliente/reservar/",
        views.reserva_cliente,
        name="reserva_cliente"
    ),
    path(
        "cliente/mis-reservas/",
        views.mis_reservas,
        name="mis_reservas"
    ),
    path(
        "cliente/historial/",
        views.historial_reservas,
        name="historial_reservas"
    ),
    path(
        "cliente/reservas/<int:reserva_id>/cancelar/",
        views.solicitar_cancelacion,
        name="solicitar_cancelacion"
    ),

    
]
