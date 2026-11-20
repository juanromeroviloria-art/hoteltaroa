from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from gestion.models import Servicio


SERVICIOS = {
    "RESTAURANTE": (
        (
            "Desayuno costeño",
            "Huevos, arepa, queso costeño, fruta y bebida caliente.",
            "24000",
        ),
        ("Arepa de huevo", "Arepa de maíz rellena con huevo.", "12000"),
        (
            "Patacón con queso costeño",
            "Patacones crujientes acompañados de queso costeño.",
            "16000",
        ),
        ("Empanadas de carne", "Porción de dos empanadas de carne.", "14000"),
        ("Carimañolas", "Porción de dos carimañolas de yuca y carne.", "15000"),
        ("Fruta fresca", "Porción de frutas de temporada.", "12000"),
        ("Sopa del día", "Sopa preparada con ingredientes frescos del día.", "18000"),
        (
            "Filete de pescado a la plancha",
            "Filete de pescado con arroz y ensalada.",
            "39000",
        ),
        (
            "Mojarra frita con arroz de coco",
            "Mojarra entera, arroz de coco y patacón.",
            "46000",
        ),
        (
            "Arroz de camarones",
            "Arroz preparado con camarones y vegetales.",
            "42000",
        ),
        (
            "Pollo a la plancha",
            "Pechuga de pollo con acompañamiento y ensalada.",
            "32000",
        ),
        ("Carne asada", "Carne asada con arroz, papa y ensalada.", "38000"),
        (
            "Ensalada de la casa",
            "Ensalada fresca con vegetales y aderezo de la casa.",
            "22000",
        ),
        (
            "Hamburguesa Taroa",
            "Hamburguesa de carne con queso, vegetales y papas.",
            "29000",
        ),
        ("Postre del día", "Porción individual del postre disponible.", "12000"),
        (
            "Menú infantil",
            "Porción infantil de pollo, papas y bebida.",
            "26000",
        ),
    ),
    "BAR": (
        ("Agua embotellada", "Botella de agua personal.", "4500"),
        ("Gaseosa", "Gaseosa personal de sabores disponibles.", "6000"),
        ("Jugo natural", "Jugo natural de fruta de temporada.", "10000"),
        ("Limonada de coco", "Limonada preparada con coco.", "16000"),
        ("Café", "Taza de café colombiano.", "6000"),
        (
            "Cerveza nacional",
            "Botella individual de cerveza nacional.",
            "9000",
        ),
        (
            "Cerveza importada",
            "Botella individual de cerveza importada.",
            "14000",
        ),
        ("Mojito", "Cóctel de ron, hierbabuena, limón y soda.", "26000"),
        ("Piña colada", "Cóctel de ron, piña y crema de coco.", "28000"),
        ("Cuba libre", "Cóctel de ron, gaseosa cola y limón.", "24000"),
        ("Gin tonic", "Ginebra con agua tónica y cítricos.", "32000"),
        (
            "Cóctel sin alcohol",
            "Bebida preparada sin alcohol con frutas.",
            "18000",
        ),
    ),
    "LAVANDERIA": (
        (
            "Lavado y planchado de camisa",
            "Lavado y planchado de una camisa.",
            "10000",
        ),
        (
            "Lavado y planchado de pantalón",
            "Lavado y planchado de un pantalón.",
            "13000",
        ),
        ("Lavado de camiseta", "Lavado de una camiseta.", "8000"),
        ("Lavado de vestido", "Lavado de un vestido de uso diario.", "18000"),
        ("Lavado de toalla", "Lavado de una toalla de baño.", "7000"),
        (
            "Lavado de prenda delicada",
            "Lavado cuidadoso de una prenda delicada.",
            "16000",
        ),
        (
            "Bolsa de ropa hasta 5 kg",
            "Lavado y doblado de una bolsa de ropa hasta 5 kg.",
            "35000",
        ),
        (
            "Servicio exprés por prenda",
            "Lavado prioritario de una prenda.",
            "8000",
        ),
    ),
}


class Command(BaseCommand):
    help = "Agrega un catálogo de muestra para restaurante, bar y lavandería."

    def handle(self, *args, **options):
        creados = 0
        existentes = 0
        with transaction.atomic():
            for area, productos in SERVICIOS.items():
                for nombre, descripcion, precio in productos:
                    _, creado = Servicio.objects.get_or_create(
                        area=area,
                        nombre=nombre,
                        defaults={
                            "descripcion": descripcion,
                            "precio": Decimal(precio),
                            "activo": True,
                        },
                    )
                    if creado:
                        creados += 1
                    else:
                        existentes += 1

        self.stdout.write(self.style.SUCCESS(
            f"Catálogo listo: {creados} servicios nuevos y "
            f"{existentes} ya registrados."
        ))
