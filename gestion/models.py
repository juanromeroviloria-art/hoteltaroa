from django.db import models
from django.contrib.auth.models import User


class Rol(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField(blank=True)

    def __str__(self):
        return self.nombre


class Usuario(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT)

    def __str__(self):
        return self.usuario.username


class Alojamiento(models.Model):
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField()
    direccion = models.CharField(max_length=200)
    municipio = models.CharField(max_length=100, default="Riohacha")
    telefono = models.CharField(max_length=20)
    correo = models.EmailField()
    foto = models.ImageField(
        "Fotografía del alojamiento",
        upload_to="alojamientos/",
        blank=True,
        help_text="Sube una imagen JPG, PNG o WebP del establecimiento.",
    )
    foto_url = models.URLField(blank=True)
    sitios_turisticos = models.TextField(blank=True)
    servicios_disponibles = models.ManyToManyField(
        "Servicio",
        blank=True,
        related_name="alojamientos",
    )

    def __str__(self):
        return self.nombre


class TipoHabitacion(models.Model):
    nombre = models.CharField(max_length=80)
    descripcion = models.TextField(blank=True)
    capacidad = models.PositiveIntegerField(default=2)

    def __str__(self):
        return self.nombre


class Habitacion(models.Model):
    ESTADOS = [
        ('DISPONIBLE', 'Disponible'),
        ('OCUPADA', 'Ocupada'),
        ('MANTENIMIENTO', 'Mantenimiento'),
    ]

    alojamiento = models.ForeignKey(
        Alojamiento, on_delete=models.CASCADE
    )
    tipo = models.ForeignKey(
        TipoHabitacion, on_delete=models.PROTECT
    )
    numero = models.CharField(max_length=10)
    piso = models.PositiveIntegerField(default=1)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    foto = models.ImageField(
        "Fotografía de la habitación",
        upload_to="habitaciones/",
        blank=True,
        help_text="Sube una imagen JPG, PNG o WebP de esta habitación.",
    )
    foto_url = models.URLField(
        "Foto de la habitación (URL)",
        blank=True,
        help_text="Pega el enlace directo a una imagen de esta habitación.",
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='DISPONIBLE'
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['alojamiento', 'numero'],
                name='habitacion_unica_por_alojamiento'
            )
        ]

    def __str__(self):
        return f"Habitación {self.numero}"


class Huesped(models.Model):
    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="perfil_huesped"
    )

    tipo_documento = models.CharField(max_length=10)
    numero_documento = models.CharField(max_length=30, unique=True)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20)
    correo = models.EmailField(blank=True)
    nacionalidad = models.CharField(
        max_length=60, default="Colombiana"
    )

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"

class Reserva(models.Model):
    ESTADOS = [
        ('PENDIENTE', 'Pendiente'),
        ('CONFIRMADA', 'Confirmada'),
        ('CANCELADA', 'Cancelada'),
        ('EN_CURSO', 'En curso'),
        ('FINALIZADA', 'Finalizada'),
    ]

    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservas_creadas",
        verbose_name="Usuario que creó la reserva",
    )

    huesped = models.ForeignKey(
        Huesped,
        on_delete=models.PROTECT
    )

    habitacion = models.ForeignKey(
        Habitacion,
        on_delete=models.PROTECT
    )

    fecha_entrada = models.DateField()
    fecha_salida = models.DateField()

    precio_noche = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    cantidad_huespedes = models.PositiveIntegerField(
        default=1,
        verbose_name="Cantidad de adultos"
    )

    cantidad_ninos = models.PositiveIntegerField(
        default=0,
        verbose_name="Cantidad de niños"
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='PENDIENTE',
        verbose_name="Estado de la reserva"
    )

    fecha_registro = models.DateTimeField(auto_now_add=True)
    fecha_check_in = models.DateTimeField(null=True, blank=True)
    fecha_check_out = models.DateTimeField(null=True, blank=True)

    @property
    def noches(self):
        return (self.fecha_salida - self.fecha_entrada).days

    @property
    def valor_total(self):
        servicios = sum(
            (
                linea.cantidad * linea.precio_unitario
                for linea in self.servicios.all()
            ),
            start=0,
        )

        consumos = sum(
            (
                consumo.cantidad * consumo.precio_unitario
                for consumo in self.consumos.all()
            ),
            start=0,
        )

        precio = (
            self.precio_noche
            if self.precio_noche is not None
            else self.habitacion.precio
        )

        return self.noches * precio + servicios + consumos

    @property
    def valor_pagado(self):
        if "pagos" in getattr(self, "_prefetched_objects_cache", {}):
            return sum(
                (pago.valor for pago in self.pagos.all()),
                start=0,
            )

        return self.pagos.aggregate(
            total=models.Sum("valor")
        )["total"] or 0

    @property
    def saldo_pendiente(self):
        return max(self.valor_total - self.valor_pagado, 0)

    def save(self, *args, **kwargs):
        if self.precio_noche is None:
            self.precio_noche = self.habitacion.precio

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Reserva {self.id} - {self.huesped}"
class Pago(models.Model):
    reserva = models.ForeignKey(
        Reserva,
        on_delete=models.PROTECT,
        related_name='pagos'
    )
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    metodo = models.CharField(max_length=30)
    fecha = models.DateTimeField(auto_now_add=True)
    referencia = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"Pago {self.id} - ${self.valor}"


class Servicio(models.Model):
    AREAS = [
        ("RESTAURANTE", "Restaurante"),
        ("BAR", "Bar"),
        ("LAVANDERIA", "Lavandería"),
    ]

    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    activo = models.BooleanField(default=True)
    area = models.CharField(
        max_length=20,
        choices=AREAS,
        default="RESTAURANTE",
    )

    def __str__(self):
        return self.nombre


class Consumo(models.Model):
    AREAS = Servicio.AREAS

    reserva = models.ForeignKey(
        Reserva,
        on_delete=models.PROTECT,
        related_name="consumos",
    )
    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.PROTECT,
        related_name="consumos",
    )
    area = models.CharField(
        max_length=20,
        choices=AREAS,
        default="RESTAURANTE",
    )
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    registrado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consumos_registrados",
    )
    fecha = models.DateTimeField(auto_now_add=True)

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario

    def __str__(self):
        return f"{self.servicio} - Reserva {self.reserva_id}"

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(cantidad__gt=0),
                name="consumo_cantidad_mayor_que_cero",
            )
        ]


class ServicioReserva(models.Model):
    reserva = models.ForeignKey(
        Reserva,
        on_delete=models.CASCADE,
        related_name='servicios'
    )
    servicio = models.ForeignKey(
        Servicio, on_delete=models.PROTECT
    )
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(
        max_digits=10, decimal_places=2
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["reserva", "servicio"],
                name="servicio_unico_por_reserva",
            )
        ]

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario

    def __str__(self):
        return f"{self.servicio} - Reserva {self.reserva_id}"


class SolicitudCancelacion(models.Model):
    ESTADOS = [
        ("PENDIENTE", "Pendiente"),
        ("APROBADA", "Aprobada"),
        ("RECHAZADA", "Rechazada"),
    ]

    reserva = models.ForeignKey(
        Reserva,
        on_delete=models.PROTECT,
        related_name="solicitudes_cancelacion"
    )
    motivo = models.TextField()
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="PENDIENTE"
    )
    fecha_solicitud = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Solicitud {self.id} - Reserva {self.reserva_id}"