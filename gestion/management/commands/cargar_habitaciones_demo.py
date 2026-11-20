from decimal import Decimal
from io import BytesIO
from pathlib import Path
from random import Random

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from PIL import Image

from gestion.models import Alojamiento, Habitacion, TipoHabitacion


TIPOS_HABITACION = (
    {
        "nombre": "Individual estándar",
        "capacidad": 1,
        "descripcion": "Cama sencilla, baño privado, aire acondicionado y Wi-Fi.",
        "tarifa": Decimal("135000"),
        "cantidad": 20,
    },
    {
        "nombre": "Doble estándar",
        "capacidad": 2,
        "descripcion": "Cama doble, baño privado, aire acondicionado y Wi-Fi.",
        "tarifa": Decimal("185000"),
        "cantidad": 50,
    },
    {
        "nombre": "Doble twin",
        "capacidad": 2,
        "descripcion": "Dos camas sencillas, baño privado, aire acondicionado y Wi-Fi.",
        "tarifa": Decimal("205000"),
        "cantidad": 30,
    },
    {
        "nombre": "Doble superior",
        "capacidad": 2,
        "descripcion": "Cama queen, zona de estar, baño privado y aire acondicionado.",
        "tarifa": Decimal("235000"),
        "cantidad": 28,
    },
    {
        "nombre": "Triple",
        "capacidad": 3,
        "descripcion": "Tres puestos para dormir, baño privado y aire acondicionado.",
        "tarifa": Decimal("275000"),
        "cantidad": 20,
    },
    {
        "nombre": "Familiar 4 personas",
        "capacidad": 4,
        "descripcion": "Dos camas dobles, baño privado, aire acondicionado y Wi-Fi.",
        "tarifa": Decimal("330000"),
        "cantidad": 20,
    },
    {
        "nombre": "Familiar 5 personas",
        "capacidad": 5,
        "descripcion": "Dos camas y cama auxiliar, baño privado y aire acondicionado.",
        "tarifa": Decimal("390000"),
        "cantidad": 12,
    },
    {
        "nombre": "Junior suite",
        "capacidad": 2,
        "descripcion": "Cama king, sala pequeña, baño privado y aire acondicionado.",
        "tarifa": Decimal("430000"),
        "cantidad": 8,
    },
    {
        "nombre": "Suite ejecutiva",
        "capacidad": 2,
        "descripcion": "Cama king, sala de estar, escritorio y baño privado.",
        "tarifa": Decimal("500000"),
        "cantidad": 6,
    },
    {
        "nombre": "Suite familiar",
        "capacidad": 6,
        "descripcion": "Dos espacios para dormir, sala, baño privado y aire acondicionado.",
        "tarifa": Decimal("560000"),
        "cantidad": 6,
    },
)

TARIFAS_EXISTENTES = {
    "Individual": Decimal("135000"),
    "Doble": Decimal("185000"),
    "Triple": Decimal("275000"),
    "Familiar": Decimal("420000"),
}

FOTOS = (
    "habitacion-clasica.jpg",
    "habitacion-moderna.jpg",
)


class Command(BaseCommand):
    help = "Completa Hotel Taroa con 200 habitaciones de demostración y fotos locales."

    def add_arguments(self, parser):
        parser.add_argument(
            "--actualizar-existentes",
            action="store_true",
            help="Ajusta tarifas existentes al rango configurado para la demostración.",
        )

    def handle(self, *args, **options):
        alojamiento = Alojamiento.objects.order_by("id").first()
        if alojamiento is None:
            raise CommandError(
                "Primero registra un alojamiento para crear sus habitaciones."
            )

        total_actual = Habitacion.objects.filter(
            alojamiento=alojamiento
        ).count()
        if total_actual > 200:
            raise CommandError(
                f"El alojamiento ya tiene {total_actual} habitaciones; "
                "no se eliminará ninguna para reducir el total a 200."
            )

        tipos = {}
        for especificacion in TIPOS_HABITACION:
            tipos[especificacion["nombre"]], _ = TipoHabitacion.objects.get_or_create(
                nombre=especificacion["nombre"],
                defaults={
                    "capacidad": especificacion["capacidad"],
                    "descripcion": especificacion["descripcion"],
                },
            )

        especificaciones = [
            especificacion
            for especificacion in TIPOS_HABITACION
            for _ in range(especificacion["cantidad"])
        ]
        Random(2026).shuffle(especificaciones)
        existentes_por_numero = {
            habitacion.numero: habitacion
            for habitacion in Habitacion.objects.filter(
                alojamiento=alojamiento
            ).select_related("tipo")
        }
        habitaciones_faltantes = 200 - total_actual

        if options["actualizar_existentes"]:
            for habitacion in existentes_por_numero.values():
                tarifa_base = TARIFAS_EXISTENTES.get(habitacion.tipo.nombre)
                if tarifa_base is not None:
                    habitacion.precio = self._tarifa_piso(
                        tarifa_base, habitacion.piso
                    )
                if not habitacion.foto:
                    habitacion.foto.name = self._guardar_foto(
                        habitacion.numero,
                        habitacion.tipo.nombre,
                    )
                habitacion.save(update_fields=["precio", "foto"])

        creadas = 0
        completadas = 0
        especificacion_index = 0
        with transaction.atomic():
            for piso in range(1, 6):
                if creadas >= habitaciones_faltantes:
                    break
                for consecutivo in range(1, 41):
                    if creadas >= habitaciones_faltantes:
                        break
                    numero = f"{piso}{consecutivo:02d}"
                    habitacion = existentes_por_numero.get(numero)
                    if habitacion is not None:
                        if not habitacion.foto:
                            habitacion.foto.name = self._guardar_foto(
                                numero,
                                habitacion.tipo.nombre,
                            )
                            habitacion.save(update_fields=["foto"])
                            completadas += 1
                        continue

                    if especificacion_index >= len(especificaciones):
                        break

                    especificacion = especificaciones[especificacion_index]
                    especificacion_index += 1
                    habitacion = Habitacion.objects.create(
                        alojamiento=alojamiento,
                        tipo=tipos[especificacion["nombre"]],
                        numero=numero,
                        piso=piso,
                        precio=self._tarifa_piso(
                            especificacion["tarifa"], piso
                        ),
                        estado="DISPONIBLE",
                    )
                    habitacion.foto.name = self._guardar_foto(
                        numero,
                        especificacion["nombre"],
                    )
                    habitacion.save(update_fields=["foto"])
                    existentes_por_numero[numero] = habitacion
                    creadas += 1

            for habitacion in existentes_por_numero.values():
                if not habitacion.foto:
                    habitacion.foto.name = self._guardar_foto(
                        habitacion.numero,
                        habitacion.tipo.nombre,
                    )
                    habitacion.save(update_fields=["foto"])
                    completadas += 1

        total_final = Habitacion.objects.filter(
            alojamiento=alojamiento
        ).count()
        con_foto = Habitacion.objects.filter(
            alojamiento=alojamiento
        ).exclude(foto="").count()
        self.stdout.write(self.style.SUCCESS(
            f"Listo: {total_final} habitaciones en {alojamiento.nombre}; "
            f"{creadas} nuevas, {completadas} existentes completadas, "
            f"{con_foto} con imagen asignada."
        ))

    @staticmethod
    def _tarifa_piso(tarifa_base, piso):
        incremento = Decimal("1") + Decimal(piso - 1) * Decimal("0.025")
        tarifa_ajustada = tarifa_base * incremento
        return (
            (tarifa_ajustada / Decimal("10000")).quantize(Decimal("1"))
            * Decimal("10000")
        )

    @staticmethod
    def _guardar_foto(numero, tipo):
        nombre_archivo = f"habitaciones/habitacion-{numero}.jpg"
        if default_storage.exists(nombre_archivo):
            return nombre_archivo

        suma = sum(ord(caracter) for caracter in f"{numero}{tipo}")
        origen = (
            Path(settings.BASE_DIR)
            / "gestion"
            / "static"
            / "img"
            / FOTOS[suma % len(FOTOS)]
        )
        with Image.open(origen) as imagen:
            imagen = imagen.convert("RGB")
            imagen.thumbnail((900, 600), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            imagen.save(buffer, format="JPEG", quality=78, optimize=True)
        return default_storage.save(
            nombre_archivo,
            ContentFile(buffer.getvalue()),
        )
