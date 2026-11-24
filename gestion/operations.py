from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Habitacion, Pago, Reserva


def sincronizar_estado_habitacion(habitacion_id):
    habitacion = Habitacion.objects.select_for_update().get(pk=habitacion_id)
    if habitacion.estado == "MANTENIMIENTO":
        return habitacion

    tiene_reservas_activas = Reserva.objects.filter(
        habitacion_id=habitacion_id,
        estado__in=["PENDIENTE", "CONFIRMADA", "EN_CURSO"],
    ).exists()
    estado = "OCUPADA" if tiene_reservas_activas else "DISPONIBLE"
    if habitacion.estado != estado:
        habitacion.estado = estado
        habitacion.save(update_fields=["estado"])
    return habitacion


@transaction.atomic
def confirmar_reserva(reserva_id, registrado_por=None):
    reserva = Reserva.objects.select_for_update().select_related(
        "habitacion"
    ).get(pk=reserva_id)
    if reserva.estado != "PENDIENTE":
        raise ValidationError("Solo se pueden confirmar reservas pendientes.")
    if reserva.habitacion.estado == "MANTENIMIENTO":
        raise ValidationError("La habitación está en mantenimiento.")

    abono_objetivo = (
        Decimal(str(reserva.valor_total)) / Decimal("2")
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    abono = max(
        abono_objetivo - Decimal(str(reserva.valor_pagado)),
        Decimal("0.00"),
    )
    if abono:
        Pago.objects.create(
            reserva=reserva,
            valor=abono,
            metodo="Abono automático",
            referencia="Abono del 50% al confirmar la reserva",
            registrado_por=registrado_por,
        )

    reserva.estado = "CONFIRMADA"
    reserva.save(update_fields=["estado"])
    sincronizar_estado_habitacion(reserva.habitacion_id)
    return reserva


@transaction.atomic
def cancelar_reserva(reserva_id):
    reserva = Reserva.objects.select_for_update().get(pk=reserva_id)
    if reserva.estado not in ["PENDIENTE", "CONFIRMADA"]:
        raise ValidationError(
            "Solo se pueden cancelar reservas pendientes o confirmadas."
        )
    reserva.estado = "CANCELADA"
    reserva.save(update_fields=["estado"])
    sincronizar_estado_habitacion(reserva.habitacion_id)
    return reserva


@transaction.atomic
def registrar_check_in(reserva_id, registrado_por=None):
    reserva = Reserva.objects.select_for_update().select_related(
        "habitacion"
    ).get(pk=reserva_id)
    if reserva.estado == "CANCELADA":
        raise ValidationError(
            "No se puede hacer check-in de una reserva cancelada."
        )
    if reserva.estado != "CONFIRMADA":
        raise ValidationError(
            "Solo se puede hacer check-in de reservas confirmadas."
        )
    if reserva.habitacion.estado == "MANTENIMIENTO":
        raise ValidationError("La habitación está en mantenimiento.")

    saldo_pendiente = Decimal(str(reserva.saldo_pendiente)).quantize(
        Decimal("0.01")
    )
    if saldo_pendiente:
        Pago.objects.create(
            reserva=reserva,
            valor=saldo_pendiente,
            metodo="Saldo automático",
            referencia="Saldo restante al hacer check-in",
            registrado_por=registrado_por,
        )

    reserva.estado = "EN_CURSO"
    reserva.fecha_check_in = timezone.now()
    reserva.save(update_fields=["estado", "fecha_check_in"])
    sincronizar_estado_habitacion(reserva.habitacion_id)
    return reserva


@transaction.atomic
def registrar_check_out(reserva_id):
    reserva = Reserva.objects.select_for_update().select_related(
        "habitacion"
    ).get(pk=reserva_id)
    if reserva.estado != "EN_CURSO" or not reserva.fecha_check_in:
        raise ValidationError(
            "Solo se puede hacer check-out después del check-in."
        )

    reserva.estado = "FINALIZADA"
    reserva.fecha_check_out = timezone.now()
    reserva.save(update_fields=["estado", "fecha_check_out"])
    sincronizar_estado_habitacion(reserva.habitacion_id)
    return reserva
