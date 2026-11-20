
from django.contrib import admin
from .forms import PagoForm, ReservaForm
from .models import (
    Rol,
    Usuario,
    Alojamiento,
    TipoHabitacion,
    Habitacion,
    Huesped,
    Reserva,
    Pago,
    Servicio,
    ServicioReserva,
    SolicitudCancelacion,
)

admin.site.register(Rol)
admin.site.register(Usuario)
admin.site.register(Alojamiento)
admin.site.register(TipoHabitacion)
admin.site.register(Habitacion)
admin.site.register(Huesped)
@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    form = ReservaForm
    list_display = (
        "id",
        "huesped",
        "habitacion",
        "fecha_entrada",
        "fecha_salida",
        "estado",
    )
    readonly_fields = (
        "estado",
        "usuario",
        "precio_noche",
        "fecha_registro",
        "fecha_check_in",
        "fecha_check_out",
    )
    fields = (
        "huesped",
        "habitacion",
        "fecha_entrada",
        "fecha_salida",
        "cantidad_huespedes",
        "estado",
        "usuario",
        "precio_noche",
        "fecha_registro",
        "fecha_check_in",
        "fecha_check_out",
    )

    def save_model(self, request, obj, form, change):
        if not obj.usuario_id:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    form = PagoForm
admin.site.register(Servicio)
admin.site.register(ServicioReserva)
admin.site.register(SolicitudCancelacion)