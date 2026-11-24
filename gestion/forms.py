
from django import forms
from django.db.models import Sum
from django.utils import timezone
from .models import (
    Alojamiento,
    Consumo,
    Habitacion,
    Huesped,
    Pago,
    Reserva,
    Servicio,
    ServicioReserva,
    TipoHabitacion,
)


class AlojamientoForm(forms.ModelForm):
    class Meta:
        model = Alojamiento
        fields = [
            "nombre",
            "descripcion",
            "direccion",
            "municipio",
            "telefono",
            "correo",
            "foto",
            "sitios_turisticos",
            "servicios_disponibles",
        ]
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 4}),
            "sitios_turisticos": forms.Textarea(attrs={
                "rows": 4,
                "placeholder": "Un sitio turístico por línea",
            }),
            "servicios_disponibles": forms.CheckboxSelectMultiple(),
        }


class HabitacionForm(forms.ModelForm):
    class Meta:
        model = Habitacion
        fields = [
            "alojamiento",
            "tipo",
            "numero",
            "piso",
            "precio",
            "foto",
            "estado",
        ]

        labels = {
            "alojamiento": "Establecimiento",
            "tipo": "Tipo de habitación",
            "numero": "Número de habitación",
            "piso": "Piso",
            "precio": "Precio por noche",
            "foto": "Subir foto de la habitación",
            "estado": "Estado",
        }

        widgets = {
            "alojamiento": forms.Select(),
            "tipo": forms.Select(),
            "numero": forms.TextInput(attrs={
                "placeholder": "Ej. 101"
            }),
            "piso": forms.NumberInput(attrs={
                "min": 1
            }),
            "precio": forms.NumberInput(attrs={
                "min": "0.01",
                "step": "0.01"
            }),
            "estado": forms.Select(),
        }

    def clean_precio(self):
        precio = self.cleaned_data["precio"]
        if precio <= 0:
            raise forms.ValidationError("El precio por noche debe ser mayor que cero.")
        return precio





class TipoHabitacionForm(forms.ModelForm):
    class Meta:
        model = TipoHabitacion
        fields = ["nombre", "descripcion", "capacidad"]

        labels = {
            "nombre": "Nombre del tipo",
            "descripcion": "Descripción",
            "capacidad": "Capacidad de huéspedes",
        }

        widgets = {
            "nombre": forms.TextInput(attrs={
                "placeholder": "Ej. Habitación doble"
            }),
            "descripcion": forms.Textarea(attrs={
                "rows": 4,
                "placeholder": "Describe las características de la habitación"
            }),
            "capacidad": forms.NumberInput(attrs={
                "min": 1
            }),
        }

    def clean_capacidad(self):
        capacidad = self.cleaned_data["capacidad"]
        if capacidad < 1:
            raise forms.ValidationError("La capacidad debe ser al menos una persona.")
        return capacidad


class ServicioForm(forms.ModelForm):
    def __init__(self, *args, area_permitida=None, **kwargs):
        super().__init__(*args, **kwargs)
        if area_permitida:
            self.fields["area"].choices = [
                (value, label)
                for value, label in self.fields["area"].choices
                if value == area_permitida
            ]
            self.initial["area"] = area_permitida

    class Meta:
        model = Servicio
        fields = ["area", "nombre", "descripcion", "precio", "activo"]

        labels = {
            "area": "Área del hotel",
            "nombre": "Nombre del servicio",
            "descripcion": "Descripción",
            "precio": "Precio (COP)",
            "activo": "Servicio activo",
        }

        widgets = {
            "area": forms.Select(),
            "nombre": forms.TextInput(attrs={
                "placeholder": "Ej. Desayuno"
            }),
            "descripcion": forms.Textarea(attrs={
                "rows": 4,
                "placeholder": "Describe el servicio"
            }),
            "precio": forms.NumberInput(attrs={
                "min": "0",
                "step": "0.01",
                "placeholder": "Ej. 25000"
            }),
        }



  
class HuespedForm(forms.ModelForm):
    class Meta:
        model = Huesped
        fields = [
            "tipo_documento",
            "numero_documento",
            "nombres",
            "apellidos",
            "telefono",
            "correo",
            "nacionalidad",
        ]

        labels = {
            "tipo_documento": "Tipo de documento",
            "numero_documento": "Número de documento",
            "nombres": "Nombres",
            "apellidos": "Apellidos",
            "telefono": "Teléfono",
            "correo": "Correo electrónico",
            "nacionalidad": "Nacionalidad",
        }

        widgets = {
            "tipo_documento": forms.Select(choices=[
                ("CC", "Cédula de ciudadanía"),
                ("CE", "Cédula de extranjería"),
                ("TI", "Tarjeta de identidad"),
                ("PASAPORTE", "Pasaporte"),
            ]),
            "numero_documento": forms.TextInput(attrs={
                "placeholder": "Número de documento"
            }),
            "nombres": forms.TextInput(attrs={
                "placeholder": "Nombres del huésped"
            }),
            "apellidos": forms.TextInput(attrs={
                "placeholder": "Apellidos del huésped"
            }),
            "telefono": forms.TextInput(attrs={
                "placeholder": "Número de contacto"
            }),
            "correo": forms.EmailInput(attrs={
                "placeholder": "correo@ejemplo.com"
            }),
            "nacionalidad": forms.TextInput(attrs={
                "placeholder": "Colombiana"
            }),
        }


class ReservaForm(forms.ModelForm):
    class Meta:
        model = Reserva
        fields = [
            "huesped",
            "habitacion",
            "fecha_entrada",
            "fecha_salida",
            "cantidad_huespedes",
        ]

        labels = {
            "huesped": "Huésped",
            "habitacion": "Habitación",
            "fecha_entrada": "Fecha de entrada",
            "fecha_salida": "Fecha de salida",
            "cantidad_huespedes": "Cantidad de huéspedes",
        }

        widgets = {
            "fecha_entrada": forms.DateInput(attrs={"type": "date"}),
            "fecha_salida": forms.DateInput(attrs={"type": "date"}),
            "cantidad_huespedes": forms.NumberInput(attrs={"min": 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        fecha_minima = timezone.localdate().isoformat()
        self.fields["fecha_entrada"].widget.attrs["min"] = fecha_minima
        self.fields["fecha_salida"].widget.attrs["min"] = fecha_minima

    def clean(self):
        datos = super().clean()

        entrada = datos.get("fecha_entrada")
        salida = datos.get("fecha_salida")
        cantidad = datos.get("cantidad_huespedes")
        habitacion = datos.get("habitacion")

        if entrada and entrada < timezone.localdate():
            self.add_error(
                "fecha_entrada",
                "La fecha de entrada no puede estar en el pasado.",
            )

        if salida and salida < timezone.localdate():
            self.add_error(
                "fecha_salida",
                "La fecha de salida no puede estar en el pasado.",
            )

        if entrada and salida and salida <= entrada:
            self.add_error(
                "fecha_salida",
                "La fecha de salida debe ser posterior a la entrada."
            )

        if cantidad is not None and cantidad < 1:
            self.add_error(
                "cantidad_huespedes",
                "Debe alojarse al menos una persona.",
            )

        if cantidad and habitacion and cantidad > habitacion.tipo.capacidad:
            self.add_error(
                "cantidad_huespedes",
                "La cantidad de huéspedes supera la capacidad de la habitación."
            )

        if habitacion and habitacion.estado == "MANTENIMIENTO":
            self.add_error(
                "habitacion",
                "No se pueden reservar habitaciones en mantenimiento.",
            )

        if entrada and salida and habitacion:
            reservas_activas = Reserva.objects.filter(
                habitacion=habitacion,
                fecha_entrada__lt=salida,
                fecha_salida__gt=entrada,
                estado__in=["PENDIENTE", "CONFIRMADA", "EN_CURSO"],
            )
            if self.instance.pk:
                reservas_activas = reservas_activas.exclude(pk=self.instance.pk)
            if reservas_activas.exists():
                self.add_error(
                    "habitacion",
                    "La habitación ya tiene una reserva para esas fechas.",
                )

        return datos


class ServicioReservaForm(forms.ModelForm):
    class Meta:
        model = ServicioReserva
        fields = ["servicio", "cantidad"]
        widgets = {"cantidad": forms.NumberInput(attrs={"min": 1})}

    def clean_cantidad(self):
        cantidad = self.cleaned_data["cantidad"]
        if cantidad < 1:
            raise forms.ValidationError("La cantidad debe ser al menos uno.")
        return cantidad


class ConsumoForm(forms.ModelForm):
    metodo_pago = forms.ChoiceField(
        label="Método de pago",
        choices=[
            ("Efectivo", "Efectivo"),
            ("Transferencia", "Transferencia"),
            ("Tarjeta", "Tarjeta"),
        ],
    )

    class Meta:
        model = Consumo
        fields = ["reserva", "servicio", "cantidad"]
        labels = {
            "reserva": "Huésped / habitación",
            "servicio": "Producto o servicio",
            "cantidad": "Cantidad",
        }
        widgets = {
            "cantidad": forms.NumberInput(attrs={"min": 1}),
        }

    def __init__(self, *args, area, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reserva"].widget.attrs["class"] = "form-select"
        self.fields["reserva"].queryset = Reserva.objects.filter(
            estado="EN_CURSO"
        ).select_related("huesped", "habitacion")
        self.fields["reserva"].label_from_instance = (
            lambda reserva: (
                f"Habitación {reserva.habitacion.numero} — "
                f"{reserva.huesped.nombres} {reserva.huesped.apellidos}"
            )
        )
        self.fields["servicio"].queryset = Servicio.objects.filter(
            activo=True,
            area=area,
        ).order_by("nombre")
        self.fields["servicio"].widget.attrs["class"] = "form-select"
        self.fields["cantidad"].widget.attrs["class"] = "form-control"
        self.fields["metodo_pago"].widget.attrs["class"] = "form-select"

    def clean_cantidad(self):
        cantidad = self.cleaned_data["cantidad"]
        if cantidad < 1:
            raise forms.ValidationError("La cantidad debe ser al menos uno.")
        return cantidad


class PagoForm(forms.ModelForm):
    class Meta:
        model = Pago
        fields = ["reserva", "valor", "metodo", "referencia"]

        labels = {
            "reserva": "Reserva",
            "valor": "Valor del pago",
            "metodo": "Método de pago",
            "referencia": "Referencia del pago",
        }

        widgets = {
            "valor": forms.NumberInput(attrs={
                "min": "0.01",
                "step": "0.01",
                "placeholder": "Ej. 250000"
            }),
            "metodo": forms.Select(choices=[
                ("Efectivo", "Efectivo"),
                ("Transferencia", "Transferencia"),
                ("Tarjeta", "Tarjeta"),
            ]),
            "referencia": forms.TextInput(attrs={
                "placeholder": "Número de comprobante (opcional)"
            }),
        }

    def clean_valor(self):
        valor = self.cleaned_data["valor"]
        if valor <= 0:
            raise forms.ValidationError("El valor debe ser mayor que cero.")
        return valor

    def clean(self):
        datos = super().clean()
        reserva = datos.get("reserva")
        valor = datos.get("valor")
        if reserva and valor:
            pagos_previos = reserva.pagos.exclude(pk=self.instance.pk).aggregate(
                total=Sum("valor")
            )["total"] or 0
            saldo = max(reserva.valor_total - pagos_previos, 0)
            if valor > saldo:
                self.add_error(
                    "valor",
                    f"El pago supera el saldo pendiente (${saldo:,.2f}).",
                )
        return datos