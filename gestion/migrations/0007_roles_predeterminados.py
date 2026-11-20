from django.db import migrations


ROLES_PREDETERMINADOS = {
    "Administrador": "Acceso completo a la administración del alojamiento.",
    "Recepcionista": "Gestión operativa de huéspedes, reservas y pagos.",
    "Gerente": "Consulta del panel, indicadores e informes.",
    "Cliente": "Consulta de disponibilidad y gestión de reservas propias.",
}


def crear_roles_predeterminados(apps, schema_editor):
    Rol = apps.get_model("gestion", "Rol")
    database = schema_editor.connection.alias
    for nombre, descripcion in ROLES_PREDETERMINADOS.items():
        Rol.objects.using(database).get_or_create(
            nombre=nombre,
            defaults={"descripcion": descripcion},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("gestion", "0006_reserva_precio_noche"),
    ]

    operations = [
        migrations.RunPython(
            crear_roles_predeterminados,
            migrations.RunPython.noop,
        ),
    ]
