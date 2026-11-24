import re
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth.models import User
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from PIL import Image

from .forms import (
    AlojamientoForm,
    HabitacionForm,
    PagoForm,
    ReservaForm,
)
from .models import (
    Alojamiento,
    Consumo,
    Habitacion,
    Huesped,
    Pago,
    Reserva,
    Rol,
    Servicio,
    ServicioReserva,
    TipoHabitacion,
    Usuario as PerfilUsuario,
)
from .operations import (
    cancelar_reserva,
    registrar_check_in,
    registrar_check_out,
)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class HotelWorkflowTests(TestCase):
    def setUp(self):
        self.rol_admin, _ = Rol.objects.get_or_create(
            nombre="Administrador"
        )
        self.admin = User.objects.create_user(
            username="admin",
            password="test-pass-12345",
            is_staff=True,
        )
        PerfilUsuario.objects.create(usuario=self.admin, rol=self.rol_admin)
        self.alojamiento = Alojamiento.objects.create(
            nombre="Hotel Taroa",
            descripcion="Alojamiento en Riohacha",
            direccion="Centro",
            municipio="Riohacha",
            telefono="3001234567",
            correo="hotel@example.com",
        )
        self.tipo = TipoHabitacion.objects.create(
            nombre="Doble",
            capacidad=2,
        )
        self.habitacion = Habitacion.objects.create(
            alojamiento=self.alojamiento,
            tipo=self.tipo,
            numero="101",
            precio=Decimal("100000.00"),
        )
        self.huesped = Huesped.objects.create(
            tipo_documento="CC",
            numero_documento="123456",
            nombres="Ana",
            apellidos="Gómez",
            telefono="3001112233",
            correo="ana@example.com",
        )
        self.entrada = date.today() + timedelta(days=10)
        self.salida = self.entrada + timedelta(days=2)

    def crear_reserva(self, **datos):
        defaults = {
            "huesped": self.huesped,
            "habitacion": self.habitacion,
            "fecha_entrada": self.entrada,
            "fecha_salida": self.salida,
            "cantidad_huespedes": 2,
            "estado": "PENDIENTE",
        }
        defaults.update(datos)
        return Reserva.objects.create(**defaults)

    def enviar_y_verificar_solicitud(self, datos):
        response = self.client.post("/cliente/reservar/", datos)
        self.assertRedirects(response, "/cliente/reservar/")
        correo = next(
            mensaje
            for mensaje in reversed(mail.outbox)
            if mensaje.to
        )
        coincidencia = re.search(
            r"Tu código de verificación es: (\d{6})",
            correo.body,
        )
        self.assertIsNotNone(coincidencia)
        return self.client.post(
            "/cliente/reservar/verificar-correo/",
            {"codigo": coincidencia.group(1)},
        )

    def test_reservation_form_blocks_overlapping_active_booking(self):
        self.crear_reserva(estado="CONFIRMADA")
        form = ReservaForm(data={
            "huesped": self.huesped.pk,
            "habitacion": self.habitacion.pk,
            "fecha_entrada": self.entrada.isoformat(),
            "fecha_salida": self.salida.isoformat(),
            "cantidad_huespedes": 1,
        })

        self.assertFalse(form.is_valid())
        self.assertIn("habitacion", form.errors)

    def test_reservation_form_rejects_past_dates_and_sets_calendar_minimum(self):
        yesterday = date.today() - timedelta(days=1)
        form = ReservaForm(data={
            "huesped": self.huesped.pk,
            "habitacion": self.habitacion.pk,
            "fecha_entrada": yesterday.isoformat(),
            "fecha_salida": date.today().isoformat(),
            "cantidad_huespedes": 1,
        })

        self.assertFalse(form.is_valid())
        self.assertIn("fecha_entrada", form.errors)
        self.assertEqual(
            form.fields["fecha_entrada"].widget.attrs["min"],
            date.today().isoformat(),
        )

    def test_reservation_form_allows_adjacent_dates_and_rejects_capacity(self):
        self.crear_reserva(estado="CONFIRMADA")
        adjacent_form = ReservaForm(data={
            "huesped": self.huesped.pk,
            "habitacion": self.habitacion.pk,
            "fecha_entrada": self.salida.isoformat(),
            "fecha_salida": (self.salida + timedelta(days=1)).isoformat(),
            "cantidad_huespedes": 2,
        })
        self.assertTrue(adjacent_form.is_valid(), adjacent_form.errors)

        capacity_form = ReservaForm(data={
            "huesped": self.huesped.pk,
            "habitacion": self.habitacion.pk,
            "fecha_entrada": (self.salida + timedelta(days=1)).isoformat(),
            "fecha_salida": (self.salida + timedelta(days=2)).isoformat(),
            "cantidad_huespedes": 3,
        })
        self.assertFalse(capacity_form.is_valid())
        self.assertIn("cantidad_huespedes", capacity_form.errors)

    def test_check_in_and_check_out_update_reservation_and_room(self):
        reserva = self.crear_reserva(estado="CONFIRMADA")

        registrar_check_in(reserva.pk)
        reserva.refresh_from_db()
        self.habitacion.refresh_from_db()
        self.assertEqual(reserva.estado, "EN_CURSO")
        self.assertIsNotNone(reserva.fecha_check_in)
        self.assertEqual(self.habitacion.estado, "OCUPADA")

        registrar_check_out(reserva.pk)
        reserva.refresh_from_db()
        self.habitacion.refresh_from_db()
        self.assertEqual(reserva.estado, "FINALIZADA")
        self.assertIsNotNone(reserva.fecha_check_out)
        self.assertEqual(self.habitacion.estado, "DISPONIBLE")

    def test_booking_marks_room_occupied_and_cancellation_releases_it(self):
        cliente = User.objects.create(
            username="cliente-estado-habitacion",
        )
        huesped = Huesped.objects.create(
            usuario=cliente,
            tipo_documento="CC",
            numero_documento="778899",
            nombres="Luis",
            apellidos="Pérez",
            telefono="3004445566",
            correo="luis@example.com",
        )
        self.client.force_login(cliente)

        response = self.enviar_y_verificar_solicitud({
            "habitacion": self.habitacion.pk,
            "fecha_entrada": self.entrada.isoformat(),
            "fecha_salida": self.salida.isoformat(),
            "cantidad_huespedes": 2,
        })

        self.assertRedirects(response, "/cliente/mis-reservas/")
        self.habitacion.refresh_from_db()
        self.assertEqual(self.habitacion.estado, "OCUPADA")

        reserva = Reserva.objects.get(huesped=huesped)
        self.assertEqual(reserva.estado, "PENDIENTE")
        self.assertEqual(reserva.pagos.count(), 0)
        self.client.force_login(self.admin)
        recepcion = self.client.get("/reservas/")
        self.assertContains(recepcion, "Pago pendiente")
        cancelar_reserva(reserva.pk)
        self.habitacion.refresh_from_db()
        self.assertEqual(self.habitacion.estado, "DISPONIBLE")

    def test_check_in_rejects_cancelled_and_checkout_requires_checkin(self):
        cancelada = self.crear_reserva(estado="CANCELADA")
        with self.assertRaises(ValidationError):
            registrar_check_in(cancelada.pk)

        pendiente = self.crear_reserva(
            estado="PENDIENTE",
            fecha_entrada=self.salida,
            fecha_salida=self.salida + timedelta(days=1),
        )
        with self.assertRaises(ValidationError):
            registrar_check_out(pendiente.pk)

    def test_receptionist_can_complete_reservation_workflow(self):
        role, _ = Rol.objects.get_or_create(nombre="Recepcionista")
        receptionist = User.objects.create_user(
            username="recepcion-operativa",
            password="test-pass-12345",
        )
        PerfilUsuario.objects.create(usuario=receptionist, rol=role)
        reserva = self.crear_reserva()
        servicio = Servicio.objects.create(
            nombre="Desayuno",
            precio=Decimal("20000.00"),
        )
        self.client.force_login(receptionist)

        response = self.client.get("/pagos/crear/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Registrar pago")

        response = self.client.post(f"/reservas/{reserva.pk}/confirmar/")
        self.assertRedirects(response, "/reservas/")
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, "CONFIRMADA")

        response = self.client.get(f"/reservas/{reserva.pk}/servicios/")
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            f"/reservas/{reserva.pk}/servicios/",
            {"servicio": servicio.pk, "cantidad": 1},
        )
        self.assertRedirects(response, "/reservas/")
        reserva.refresh_from_db()
        self.assertEqual(reserva.valor_total, Decimal("220000.00"))

        response = self.client.post(
            "/pagos/crear/",
            {
                "reserva": reserva.pk,
                "valor": "50000.00",
                "metodo": "Efectivo",
                "referencia": "",
            },
        )
        self.assertRedirects(response, "/pagos/")
        self.client.post(f"/reservas/{reserva.pk}/check-in/")
        reserva.refresh_from_db()
        self.habitacion.refresh_from_db()
        self.assertEqual(reserva.estado, "EN_CURSO")
        self.assertEqual(self.habitacion.estado, "OCUPADA")

        self.client.post(f"/reservas/{reserva.pk}/check-out/")
        reserva.refresh_from_db()
        self.habitacion.refresh_from_db()
        self.assertEqual(reserva.estado, "FINALIZADA")
        self.assertEqual(reserva.saldo_pendiente, Decimal("170000.00"))
        self.assertEqual(self.habitacion.estado, "DISPONIBLE")

    def test_services_and_partial_payments_calculate_balance(self):
        reserva = self.crear_reserva()
        self.assertEqual(reserva.precio_noche, Decimal("100000.00"))
        servicio = Servicio.objects.create(
            nombre="Desayuno",
            precio=Decimal("20000.00"),
        )
        ServicioReserva.objects.create(
            reserva=reserva,
            servicio=servicio,
            cantidad=2,
            precio_unitario=servicio.precio,
        )
        self.habitacion.precio = Decimal("150000.00")
        self.habitacion.save(update_fields=["precio"])
        self.assertEqual(reserva.valor_total, Decimal("240000.00"))

        pago = Pago.objects.create(
            reserva=reserva,
            valor=Decimal("140000.00"),
            metodo="Efectivo",
        )
        reserva.refresh_from_db()
        self.assertEqual(reserva.valor_pagado, Decimal("140000.00"))
        self.assertEqual(reserva.saldo_pendiente, Decimal("100000.00"))

        form = PagoForm(data={
            "reserva": reserva.pk,
            "valor": "100000.01",
            "metodo": "Efectivo",
            "referencia": "",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("valor", form.errors)

        abono = PagoForm(data={
            "reserva": reserva.pk,
            "valor": "100000.00",
            "metodo": "Transferencia",
            "referencia": "REF-1",
        })
        self.assertTrue(abono.is_valid(), abono.errors)
        abono.save()
        reserva.refresh_from_db()
        self.assertEqual(reserva.saldo_pendiente, Decimal("0.00"))

    def test_department_consumptions_are_added_to_checkout_invoice_and_payment(self):
        reserva = self.crear_reserva(estado="CONFIRMADA")
        registrar_check_in(reserva.pk)
        productos = {
            "Bar": Servicio.objects.create(
                nombre="Jugo del bar",
                precio=Decimal("6000.00"),
                area="BAR",
            ),
            "Restaurante": Servicio.objects.create(
                nombre="Cena del restaurante",
                precio=Decimal("25000.00"),
                area="RESTAURANTE",
            ),
            "Lavandería": Servicio.objects.create(
                nombre="Lavado de ropa",
                precio=Decimal("10000.00"),
                area="LAVANDERIA",
            ),
        }

        for area, producto in productos.items():
            with self.subTest(area=area):
                role, _ = Rol.objects.get_or_create(nombre=area)
                employee = User.objects.create_user(
                    username=f"empleado-{producto.area.lower()}",
                    password="secure-test-password",
                )
                PerfilUsuario.objects.create(usuario=employee, rol=role)
                self.client.force_login(employee)

                response = self.client.get("/panel/")
                self.assertRedirects(response, "/consumos/")
                response = self.client.get("/consumos/")
                self.assertContains(response, producto.nombre)
                for otro_producto in productos.values():
                    if otro_producto.pk != producto.pk:
                        self.assertNotContains(response, otro_producto.nombre)

                response = self.client.post("/consumos/", {
                    "reserva": reserva.pk,
                    "servicio": producto.pk,
                    "cantidad": 2 if area == "Bar" else 1,
                    "metodo_pago": "Efectivo",
                })
                self.assertRedirects(response, "/consumos/")
                consumo = Consumo.objects.get(
                    reserva=reserva,
                    servicio=producto,
                    registrado_por=employee,
                )
                pago_consumo = Pago.objects.get(consumo=consumo)
                self.assertEqual(pago_consumo.valor, consumo.subtotal)
                self.assertEqual(pago_consumo.metodo, "Efectivo")
                self.assertEqual(pago_consumo.registrado_por, employee)
                self.assertContains(
                    self.client.get("/consumos/"),
                    "Registrar consumo y pago",
                )

                if area == "Bar":
                    producto.precio = Decimal("9000.00")
                    producto.save(update_fields=["precio"])
                    response = self.client.post("/consumos/", {
                        "reserva": reserva.pk,
                        "servicio": productos["Restaurante"].pk,
                        "cantidad": 1,
                        "metodo_pago": "Efectivo",
                    })
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(
                        Consumo.objects.filter(reserva=reserva).count(),
                        1,
                    )
                    self.assertEqual(
                        Pago.objects.filter(reserva=reserva).count(),
                        1,
                    )

        reserva.refresh_from_db()
        self.assertEqual(reserva.valor_total, Decimal("247000.00"))
        self.assertEqual(reserva.valor_pagado, Decimal("47000.00"))
        self.assertEqual(reserva.saldo_pendiente, Decimal("200000.00"))

        receptionist_role, _ = Rol.objects.get_or_create(
            nombre="Recepcionista"
        )
        receptionist = User.objects.create_user(
            username="recepcion-factura",
            password="secure-test-password",
        )
        PerfilUsuario.objects.create(
            usuario=receptionist,
            rol=receptionist_role,
        )
        self.client.force_login(receptionist)
        response = self.client.post(f"/reservas/{reserva.pk}/check-out/")
        self.assertRedirects(
            response,
            f"/reservas/{reserva.pk}/factura/",
        )
        response = self.client.get(f"/reservas/{reserva.pk}/factura/")
        self.assertContains(response, "Factura de estadía")
        for producto in productos.values():
            self.assertContains(response, producto.nombre)
        self.assertContains(response, "Consumo #")
        for empleado in (
            User.objects.get(username="empleado-bar"),
            User.objects.get(username="empleado-restaurante"),
            User.objects.get(username="empleado-lavanderia"),
        ):
            self.assertContains(response, empleado.username)
        self.assertContains(response, "247000,00")
        self.assertContains(response, "47000,00")

        pagos = self.client.get("/pagos/")
        for empleado in (
            User.objects.get(username="empleado-bar"),
            User.objects.get(username="empleado-restaurante"),
            User.objects.get(username="empleado-lavanderia"),
        ):
            self.assertContains(pagos, empleado.username)

        response = self.client.get(
            f"/pagos/crear/?reserva={reserva.pk}"
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post("/pagos/crear/", {
            "reserva": reserva.pk,
            "valor": "200000.00",
            "metodo": "Tarjeta",
            "referencia": "CHECKOUT-1",
        })
        self.assertRedirects(
            response,
            f"/reservas/{reserva.pk}/factura/",
        )
        pago_checkout = Pago.objects.get(
            reserva=reserva,
            referencia="CHECKOUT-1",
        )
        self.assertEqual(pago_checkout.registrado_por, receptionist)
        response = self.client.get(f"/reservas/{reserva.pk}/factura/")
        self.assertContains(response, "Cuenta pagada")
        reserva.refresh_from_db()
        self.assertEqual(reserva.saldo_pendiente, Decimal("0.00"))

    def test_customer_can_only_view_their_own_reservation_invoice(self):
        customer = User.objects.create_user(
            username="cliente-factura",
            password="secure-test-password",
        )
        self.huesped.usuario = customer
        self.huesped.save(update_fields=["usuario"])
        reserva = self.crear_reserva()
        otra_reserva = self.crear_reserva(
            huesped=Huesped.objects.create(
                tipo_documento="CC",
                numero_documento="994433",
                nombres="Otro",
                apellidos="Huésped",
                telefono="3001234567",
            )
        )

        self.client.force_login(customer)
        response = self.client.get(f"/reservas/{reserva.pk}/factura/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Factura de estadía")
        self.assertEqual(
            self.client.get(
                f"/reservas/{otra_reserva.pk}/factura/"
            ).status_code,
            403,
        )

    def test_customer_reservation_history_uses_horizontal_cards(self):
        customer = User.objects.create_user(username="cliente-historial")
        self.huesped.usuario = customer
        self.huesped.save(update_fields=["usuario"])
        reserva = self.crear_reserva(
            estado="FINALIZADA",
            cantidad_huespedes=2,
            cantidad_ninos=1,
        )
        self.client.force_login(customer)

        response = self.client.get("/cliente/historial/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "historial-reservas-seccion")
        self.assertContains(response, "lista-historial-reservas")
        self.assertContains(response, "datos-reserva-horizontal")
        self.assertContains(response, "Total personas")
        self.assertContains(response, f"Reserva #{reserva.pk}")

    def test_customer_active_reservations_use_horizontal_cards_and_keep_actions(self):
        customer = User.objects.create_user(username="cliente-mis-reservas")
        self.huesped.usuario = customer
        self.huesped.save(update_fields=["usuario"])
        reserva = self.crear_reserva(
            estado="CONFIRMADA",
            cantidad_huespedes=2,
            cantidad_ninos=1,
        )
        self.client.force_login(customer)

        response = self.client.get("/cliente/mis-reservas/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "mis-reservas-seccion")
        self.assertContains(response, "lista-mis-reservas")
        self.assertContains(response, "datos-reserva-horizontal")
        self.assertContains(response, f"Reserva #{reserva.pk}")
        self.assertContains(response, "Ver factura detallada")
        self.assertContains(response, "Motivo de cancelación")
        self.assertContains(response, "Solicitar cancelación")

    def test_role_permissions_and_reports_render(self):
        reserva = self.crear_reserva()
        servicio = Servicio.objects.create(
            nombre="Desayuno",
            precio=Decimal("20000.00"),
        )
        ServicioReserva.objects.create(
            reserva=reserva,
            servicio=servicio,
            cantidad=1,
            precio_unitario=servicio.precio,
        )
        Pago.objects.create(
            reserva=reserva,
            valor=Decimal("50000.00"),
            metodo="Efectivo",
        )
        self.client.force_login(self.admin)
        response = self.client.get("/reportes/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reporte de reservas")
        self.assertContains(response, "Ana Gómez")
        self.assertEqual(self.client.get("/panel/").status_code, 200)
        self.assertEqual(self.client.get("/reservas/").status_code, 200)
        self.assertEqual(self.client.get("/pagos/").status_code, 200)
        self.assertEqual(self.client.get("/habitaciones/").status_code, 200)
        self.assertEqual(self.client.get("/perfil/").status_code, 200)
        self.assertEqual(
            self.client.get("/alojamiento/configurar/").status_code,
            200,
        )
        response = self.client.get("/roles/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/panel/"')
        response = self.client.get("/roles/crear/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Volver al panel principal")
        self.assertContains(response, 'href="/panel/"')

        role, _ = Rol.objects.get_or_create(nombre="Recepcionista")
        receptionist = User.objects.create_user(
            username="recepcion",
            password="test-pass-12345",
        )
        PerfilUsuario.objects.create(usuario=receptionist, rol=role)
        self.client.force_login(receptionist)
        response = self.client.get("/usuarios/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.headers["Location"])
        self.assertEqual(self.client.get("/reservas/").status_code, 200)
        self.assertEqual(self.client.get("/huespedes/").status_code, 200)

    def test_superuser_can_sign_in_and_open_panel_without_role_profile(self):
        administrator = User.objects.create_superuser(
            username="administrador-raiz",
            email="admin@example.com",
            password="secure-test-password",
        )

        response = self.client.get("/")
        self.assertContains(response, 'href="/login/">Acceso administrativo')

        response = self.client.post("/login/", {
            "usuario": administrator.username,
            "contrasena": "secure-test-password",
        })
        self.assertRedirects(response, "/panel/")
        self.assertEqual(
            self.client.get("/panel/").status_code,
            200,
        )
        self.assertFalse(
            PerfilUsuario.objects.filter(usuario=administrator).exists()
        )

    def test_manager_has_read_only_dashboard_reservations_payments_and_reports(self):
        manager_role, _ = Rol.objects.get_or_create(nombre="Gerente")
        manager = User.objects.create_user(username="gerente")
        PerfilUsuario.objects.create(usuario=manager, rol=manager_role)
        reserva = self.crear_reserva(estado="CONFIRMADA")
        Pago.objects.create(
            reserva=reserva,
            valor=Decimal("50000.00"),
            metodo="Transferencia",
        )
        self.client.force_login(manager)

        panel = self.client.get("/panel/")
        self.assertEqual(panel.status_code, 200)
        self.assertContains(panel, "Panel de gerencia")
        self.assertContains(panel, 'href="/servicios/"')
        self.assertContains(panel, "Ingresos recaudados este mes")
        self.assertContains(panel, "$50000")
        self.assertContains(panel, "Llegadas de hoy y próximas")
        self.assertContains(panel, "Consultar reservas")
        self.assertNotContains(panel, 'href="/usuarios/"')
        self.assertNotContains(panel, 'href="/alojamiento/configurar/"')
        self.assertNotContains(panel, "Administración del sistema")

        reservas = self.client.get("/reservas/")
        self.assertEqual(reservas.status_code, 200)
        self.assertContains(reservas, "Ana")
        self.assertNotContains(reservas, "Confirmar")
        self.assertNotContains(reservas, "Editar")
        self.assertNotContains(reservas, "Check-in")

        pagos = self.client.get("/pagos/")
        self.assertEqual(pagos.status_code, 200)
        self.assertContains(pagos, "50000")
        self.assertNotContains(pagos, "Registrar pago")

        reportes = self.client.get("/reportes/")
        self.assertEqual(reportes.status_code, 200)
        self.assertContains(reportes, "Reportes generales")

        catalogo_servicios = self.client.get("/servicios/")
        self.assertEqual(catalogo_servicios.status_code, 200)
        self.assertNotContains(catalogo_servicios, "+ Nuevo servicio")

        for ruta in (
            "/usuarios/",
            "/habitaciones/",
            "/servicios/crear/",
            "/reservas/crear/",
            "/pagos/crear/",
        ):
            with self.subTest(ruta=ruta):
                respuesta = self.client.get(ruta)
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn("/login/", respuesta.headers["Location"])

        respuesta = self.client.post(
            f"/reservas/{reserva.pk}/check-in/"
        )
        self.assertEqual(respuesta.status_code, 302)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, "CONFIRMADA")

    def test_service_catalog_permissions_are_scoped_by_staff_role(self):
        area_roles = {
            "Restaurante": "RESTAURANTE",
            "Bar": "BAR",
            "Lavandería": "LAVANDERIA",
        }
        services_by_area = {
            area: Servicio.objects.create(
                nombre=f"Servicio {area}",
                precio=Decimal("10000.00"),
                area=area_code,
            )
            for area, area_code in area_roles.items()
        }

        self.client.force_login(self.admin)
        admin_catalog = self.client.get("/servicios/")
        self.assertEqual(admin_catalog.status_code, 200)
        self.assertContains(admin_catalog, "+ Nuevo servicio")
        self.assertContains(admin_catalog, "Editar")
        self.assertEqual(
            self.client.post("/servicios/crear/", {
                "area": "BAR",
                "nombre": "Cóctel nuevo",
                "descripcion": "Bebida de prueba",
                "precio": "12000.00",
                "activo": "on",
            }).status_code,
            302,
        )
        self.assertTrue(
            Servicio.objects.filter(nombre="Cóctel nuevo", area="BAR").exists()
        )

        for area, area_code in area_roles.items():
            with self.subTest(rol=area):
                role, _ = Rol.objects.get_or_create(nombre=area)
                employee = User.objects.create_user(username=f"empleado-{area}")
                PerfilUsuario.objects.create(usuario=employee, rol=role)
                self.client.force_login(employee)

                catalog = self.client.get("/servicios/")
                self.assertEqual(catalog.status_code, 200)
                self.assertContains(catalog, services_by_area[area].nombre)
                self.assertContains(catalog, "+ Nuevo servicio")
                for other_area, other_service in services_by_area.items():
                    if other_area != area:
                        self.assertNotContains(catalog, other_service.nombre)

                created_name = f"Nuevo de {area}"
                response = self.client.post("/servicios/crear/", {
                    "area": area_code,
                    "nombre": created_name,
                    "descripcion": "Servicio del área",
                    "precio": "8500.00",
                    "activo": "on",
                })
                self.assertRedirects(response, "/servicios/")
                self.assertTrue(
                    Servicio.objects.filter(
                        nombre=created_name,
                        area=area_code,
                    ).exists()
                )

                other_area_code = next(
                    code for role_name, code in area_roles.items()
                    if role_name != area
                )
                response = self.client.post("/servicios/crear/", {
                    "area": other_area_code,
                    "nombre": f"Fuera de área {area}",
                    "descripcion": "No debe guardarse",
                    "precio": "9000.00",
                    "activo": "on",
                })
                self.assertEqual(response.status_code, 200)
                self.assertFalse(
                    Servicio.objects.filter(
                        nombre=f"Fuera de área {area}"
                    ).exists()
                )

        for role_name in ("Gerente", "Recepcionista"):
            with self.subTest(rol=role_name):
                role, _ = Rol.objects.get_or_create(nombre=role_name)
                employee = User.objects.create_user(
                    username=f"solo-lectura-{role_name}"
                )
                PerfilUsuario.objects.create(usuario=employee, rol=role)
                self.client.force_login(employee)

                catalog = self.client.get("/servicios/")
                self.assertEqual(catalog.status_code, 200)
                self.assertNotContains(catalog, "+ Nuevo servicio")
                for service in services_by_area.values():
                    self.assertContains(catalog, service.nombre)
                self.assertEqual(
                    self.client.get("/servicios/crear/").status_code,
                    302,
                )

    def test_demo_service_catalog_adds_sellable_items_per_area_idempotently(self):
        call_command("cargar_catalogo_servicios_demo", stdout=StringIO())
        call_command("cargar_catalogo_servicios_demo", stdout=StringIO())

        expected_counts = {
            "RESTAURANTE": 16,
            "BAR": 12,
            "LAVANDERIA": 8,
        }
        for area, expected_count in expected_counts.items():
            servicios = Servicio.objects.filter(area=area, activo=True)
            with self.subTest(area=area):
                self.assertEqual(servicios.count(), expected_count)
                self.assertTrue(
                    all(servicio.precio > 0 for servicio in servicios)
                )
                self.assertEqual(
                    servicios.values("nombre").distinct().count(),
                    expected_count,
                )

        self.assertTrue(
            Servicio.objects.filter(
                area="RESTAURANTE",
                nombre="Mojarra frita con arroz de coco",
            ).exists()
        )
        self.assertTrue(
            Servicio.objects.filter(
                area="BAR",
                nombre="Limonada de coco",
            ).exists()
        )
        self.assertTrue(
            Servicio.objects.filter(
                area="LAVANDERIA",
                nombre="Lavado y planchado de camisa",
            ).exists()
        )

    def test_seeded_services_are_visible_only_to_their_area(self):
        call_command("cargar_catalogo_servicios_demo", stdout=StringIO())
        area_items = (
            (
                "Restaurante",
                "Mojarra frita con arroz de coco",
                "Agua embotellada",
            ),
            ("Bar", "Mojito", "Mojarra frita con arroz de coco"),
            (
                "Lavandería",
                "Lavado y planchado de camisa",
                "Mojito",
            ),
        )

        for area, servicio_propio, servicio_ajeno in area_items:
            with self.subTest(area=area):
                role, _ = Rol.objects.get_or_create(nombre=area)
                employee = User.objects.create_user(username=f"area-{area}")
                PerfilUsuario.objects.create(usuario=employee, rol=role)
                self.client.force_login(employee)

                catalogo = self.client.get("/servicios/")
                self.assertEqual(catalogo.status_code, 200)
                self.assertContains(catalogo, servicio_propio)
                self.assertNotContains(catalogo, servicio_ajeno)

                consumos = self.client.get("/consumos/")
                self.assertEqual(consumos.status_code, 200)
                self.assertContains(consumos, servicio_propio)
                self.assertNotContains(consumos, servicio_ajeno)

    def test_all_staff_dashboards_show_pending_reservations_and_arrivals(self):
        manager_role, _ = Rol.objects.get_or_create(nombre="Gerente")
        receptionist_role, _ = Rol.objects.get_or_create(
            nombre="Recepcionista"
        )
        manager = User.objects.create_user(username="gerente-alertas")
        receptionist = User.objects.create_user(username="recepcion-alertas")
        PerfilUsuario.objects.create(usuario=manager, rol=manager_role)
        PerfilUsuario.objects.create(
            usuario=receptionist, rol=receptionist_role
        )

        today = date.today()
        self.crear_reserva(
            estado="PENDIENTE",
            fecha_entrada=today,
            fecha_salida=today + timedelta(days=1),
        )
        upcoming_guest = Huesped.objects.create(
            tipo_documento="CC",
            numero_documento="654321",
            nombres="Luis",
            apellidos="Pérez",
            telefono="3002223344",
            correo="luis@example.com",
        )
        pending_guest = Huesped.objects.create(
            tipo_documento="CC",
            numero_documento="789012",
            nombres="Marta",
            apellidos="Díaz",
            telefono="3003334455",
            correo="marta@example.com",
        )
        upcoming_room = Habitacion.objects.create(
            alojamiento=self.alojamiento,
            tipo=self.tipo,
            numero="102",
            precio=Decimal("100000.00"),
        )
        self.crear_reserva(
            huesped=upcoming_guest,
            habitacion=upcoming_room,
            estado="CONFIRMADA",
            fecha_entrada=today + timedelta(days=2),
            fecha_salida=today + timedelta(days=3),
        )
        self.crear_reserva(
            huesped=pending_guest,
            habitacion=upcoming_room,
            estado="PENDIENTE",
            fecha_entrada=today + timedelta(days=5),
            fecha_salida=today + timedelta(days=6),
        )

        for employee in (self.admin, manager, receptionist):
            with self.subTest(rol=employee.username):
                self.client.force_login(employee)
                response = self.client.get("/panel/")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["reservas_pendientes"], 2)
                self.assertEqual(
                    response.context["reservas_pendientes_hoy"], 1
                )
                self.assertContains(response, "Pendientes de confirmación")
                self.assertContains(response, "Marta Díaz")
                self.assertContains(response, "Llega hoy")
                self.assertContains(response, "Ana Gómez")
                self.assertContains(response, "Luis Pérez")
                self.assertContains(response, "Pendiente de confirmar")
                self.assertContains(
                    response,
                    'href="/reservas/?estado=PENDIENTE"',
                )

    def test_receptionist_dashboard_shows_today_operations_and_quick_actions(self):
        reception_role, _ = Rol.objects.get_or_create(nombre="Recepcionista")
        receptionist = User.objects.create_user(username="recepcion-panel")
        PerfilUsuario.objects.create(usuario=receptionist, rol=reception_role)
        today = date.today()
        arrival = self.crear_reserva(
            estado="CONFIRMADA",
            fecha_entrada=today,
            fecha_salida=today + timedelta(days=1),
        )
        checkout_room = Habitacion.objects.create(
            alojamiento=self.alojamiento,
            tipo=self.tipo,
            numero="102",
            precio=Decimal("100000.00"),
        )
        checkout = self.crear_reserva(
            habitacion=checkout_room,
            estado="EN_CURSO",
            fecha_entrada=today - timedelta(days=1),
            fecha_salida=today,
        )
        self.client.force_login(receptionist)

        response = self.client.get("/panel/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Panel de recepción")
        self.assertContains(response, 'href="/servicios/"')
        self.assertContains(response, "Entradas de hoy")
        self.assertContains(response, "Salidas de hoy")
        self.assertContains(response, "Huéspedes alojados")
        self.assertContains(response, arrival.huesped.nombres)
        self.assertContains(response, checkout.huesped.nombres)
        self.assertContains(response, "Nueva reserva")
        self.assertContains(response, "Registrar huésped")
        self.assertContains(response, "Registrar pago")
        self.assertContains(response, 'href="/reservas/crear/"')
        self.assertContains(response, 'href="/huespedes/crear/"')
        self.assertContains(response, 'href="/pagos/crear/"')
        self.assertNotContains(response, "Administración del sistema")
        self.assertNotContains(response, 'href="/usuarios/"')
        self.assertNotContains(response, 'href="/habitaciones/crear/"')

        self.assertEqual(self.client.get("/reservas/crear/").status_code, 200)
        self.assertEqual(self.client.get("/huespedes/crear/").status_code, 200)
        self.assertEqual(self.client.get("/pagos/crear/").status_code, 200)
        for ruta in ("/usuarios/", "/habitaciones/crear/", "/roles/"):
            with self.subTest(ruta=ruta):
                response = self.client.get(ruta)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login/", response.headers["Location"])

    def test_homepage_uses_local_hotel_image_instead_of_legacy_image_url(self):
        self.alojamiento.foto_url = (
            "https://hotel.example.com/fotos/hotel-taroa.jpg"
        )
        self.alojamiento.save(update_fields=["foto_url"])

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/img/hotel-taroa-costa.")
        self.assertNotContains(response, self.alojamiento.foto_url)

    def test_homepage_lists_available_rooms_for_anonymous_visitors(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Crear cuenta")
        self.assertContains(response, "Habitaciones disponibles")
        self.assertContains(response, "Habitación 101")
        self.assertContains(response, "Reservar habitación")
        self.assertContains(
            response,
            f'href="/cliente/reservar/?habitacion={self.habitacion.pk}"',
        )

        self.habitacion.estado = "OCUPADA"
        self.habitacion.save(update_fields=["estado"])
        response = self.client.get("/")
        self.assertContains(response, "Habitación 101")

    def test_homepage_hides_create_account_button_for_authenticated_users(self):
        cliente = User.objects.create_user(username="cliente-inicio")
        self.client.force_login(cliente)

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Crear cuenta")
        self.assertContains(response, "Ver habitaciones")

    def test_anonymous_reservation_requires_customer_login_and_returns_to_booking(self):
        next_url = f"/cliente/reservar/?habitacion={self.habitacion.pk}"
        response = self.client.get(next_url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            f"/cliente/login/?next={next_url.replace('?', '%3F').replace('=', '%3D')}",
        )

        cliente = User.objects.create_user(
            username="cliente-desde-portada",
            password="secure-test-password",
        )
        Huesped.objects.create(
            usuario=cliente,
            tipo_documento="CC",
            numero_documento="776655",
            nombres="Lucía",
            apellidos="Marín",
            telefono="3001234567",
            correo="lucia@example.com",
        )
        login_page = self.client.get(response.headers["Location"])
        self.assertContains(login_page, f'name="next" value="{next_url}"')

        response = self.client.post("/cliente/login/", {
            "usuario": cliente.username,
            "contrasena": "secure-test-password",
            "next": next_url,
        })

        self.assertRedirects(response, next_url)
        self.assertEqual(self.client.get(next_url).status_code, 200)

    def test_admin_login_uses_separate_hotel_background_image(self):
        self.alojamiento.foto_url = (
            "https://hotel.example.com/fotos/fondo-login.jpg"
        )
        self.alojamiento.save(update_fields=["foto_url"])

        response = self.client.get("/login/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="fondo-login"')
        self.assertContains(response, "/static/img/fondo-login.")
        self.assertNotContains(response, self.alojamiento.foto_url)
        self.assertContains(response, "Iniciar sesión")

    def test_admin_can_upload_photos_for_hotel_and_room(self):
        image_buffer = BytesIO()
        Image.new("RGB", (4, 4), color="orange").save(
            image_buffer,
            format="PNG",
        )
        image_content = image_buffer.getvalue()

        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                self.client.force_login(self.admin)
                response = self.client.post(
                    "/alojamiento/configurar/",
                    {
                        "nombre": self.alojamiento.nombre,
                        "descripcion": self.alojamiento.descripcion,
                        "direccion": self.alojamiento.direccion,
                        "municipio": self.alojamiento.municipio,
                        "telefono": self.alojamiento.telefono,
                        "correo": self.alojamiento.correo,
                        "foto": SimpleUploadedFile(
                            "hotel.png",
                            image_content,
                            content_type="image/png",
                        ),
                        "sitios_turisticos": "",
                    },
                )
                self.assertRedirects(response, "/panel/")
                self.alojamiento.refresh_from_db()
                self.assertTrue(self.alojamiento.foto)
                self.assertTrue(
                    self.alojamiento.foto.path.startswith(media_root)
                )
                response = self.client.get("/")
                self.assertContains(response, self.alojamiento.foto.url)

                response = self.client.post(
                    "/habitaciones/crear/",
                    {
                        "alojamiento": self.alojamiento.pk,
                        "tipo": self.tipo.pk,
                        "numero": "102",
                        "piso": 1,
                        "precio": "120000.00",
                        "foto": SimpleUploadedFile(
                            "habitacion.png",
                            image_content,
                            content_type="image/png",
                        ),
                        "estado": "DISPONIBLE",
                    },
                )
                self.assertRedirects(response, "/habitaciones/")
                habitacion = Habitacion.objects.get(numero="102")
                self.assertTrue(habitacion.foto)

                cliente = User.objects.create_user(username="cliente-fotos")
                Huesped.objects.create(
                    usuario=cliente,
                    tipo_documento="CC",
                    numero_documento="445566",
                    nombres="Sara",
                    apellidos="Díaz",
                    telefono="3001234567",
                    correo="sara@example.com",
                )
                self.client.force_login(cliente)
                response = self.client.get("/cliente/habitaciones/")
                self.assertContains(response, habitacion.foto.url)

    def test_image_forms_accept_uploaded_files_without_url_fields(self):
        self.assertIn("foto", AlojamientoForm().fields)
        self.assertNotIn("foto_url", AlojamientoForm().fields)
        self.assertIn("foto", HabitacionForm().fields)
        self.assertNotIn("foto_url", HabitacionForm().fields)

    def test_demo_room_command_creates_200_rooms_with_local_images_and_rates(self):
        reserva_existente = self.crear_reserva(estado="FINALIZADA")
        tarifa_reserva = reserva_existente.precio_noche

        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                call_command(
                    "cargar_habitaciones_demo",
                    actualizar_existentes=True,
                    stdout=StringIO(),
                )

                habitaciones = list(
                    Habitacion.objects.filter(
                        alojamiento=self.alojamiento
                    ).select_related("tipo")
                )
                self.assertEqual(len(habitaciones), 200)
                self.assertTrue(all(habitacion.foto for habitacion in habitaciones))
                self.assertGreater(
                    len({habitacion.tipo_id for habitacion in habitaciones}),
                    5,
                )
                self.assertGreater(
                    max(habitacion.precio for habitacion in habitaciones),
                    min(habitacion.precio for habitacion in habitaciones),
                )
                for habitacion in habitaciones:
                    self.assertTrue(
                        (Path(media_root) / habitacion.foto.name).is_file()
                    )

                catalogo = self.client.get("/cliente/habitaciones/")
                self.assertEqual(catalogo.status_code, 200)
                self.assertContains(catalogo, "Cama sencilla")
                self.assertContains(catalogo, "/media/habitaciones/habitacion-")

                reserva_existente.refresh_from_db()
                self.assertEqual(reserva_existente.precio_noche, tarifa_reserva)

                call_command(
                    "cargar_habitaciones_demo",
                    stdout=StringIO(),
                )
                self.assertEqual(
                    Habitacion.objects.filter(
                        alojamiento=self.alojamiento
                    ).count(),
                    200,
                )

    def test_dashboard_renders_accessible_occupancy_chart(self):
        self.client.force_login(self.admin)

        response = self.client.get("/panel/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ocupación actual")
        self.assertContains(
            response,
            'role="progressbar"',
        )

    def test_customer_can_book_only_an_available_room(self):
        cliente = User.objects.create_user(
            username="cliente",
            password="test-pass-12345",
        )
        huesped = Huesped.objects.create(
            usuario=cliente,
            tipo_documento="CC",
            numero_documento="654321",
            nombres="Luis",
            apellidos="Pérez",
            telefono="3004445566",
            correo="luis@example.com",
        )
        self.client.force_login(cliente)
        self.habitacion.foto_url = "https://hotel.example.com/habitacion-101.jpg"
        self.habitacion.save(update_fields=["foto_url"])
        response = self.client.get("/cliente/habitaciones/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nuestras habitaciones")
        self.assertContains(
            response,
            f'min="{date.today().isoformat()}"',
        )
        self.assertContains(response, "/static/img/habitacion-moderna.")
        self.assertNotContains(response, self.habitacion.foto_url)
        self.assertContains(response, 'alt="Habitación 101 - Doble"')

        response = self.enviar_y_verificar_solicitud({
            "habitacion": self.habitacion.pk,
            "fecha_entrada": self.entrada.isoformat(),
            "fecha_salida": self.salida.isoformat(),
            "cantidad_huespedes": 2,
        })
        self.assertRedirects(response, "/cliente/mis-reservas/")
        reserva = Reserva.objects.get(huesped=huesped)
        self.assertEqual(reserva.usuario, cliente)
        self.habitacion.refresh_from_db()
        self.assertEqual(self.habitacion.estado, "OCUPADA")

        catalogo = self.client.get("/cliente/habitaciones/")
        self.assertContains(catalogo, "Habitación 101")
        catalogo_fechas_reservadas = self.client.get(
            "/cliente/habitaciones/",
            {
                "entrada": self.entrada.isoformat(),
                "salida": self.salida.isoformat(),
                "cantidad": "1",
            },
        )
        self.assertNotContains(catalogo_fechas_reservadas, "Habitación 101")
        catalogo_fechas_libres = self.client.get(
            "/cliente/habitaciones/",
            {
                "entrada": self.salida.isoformat(),
                "salida": (self.salida + timedelta(days=1)).isoformat(),
                "cantidad": "1",
            },
        )
        self.assertContains(catalogo_fechas_libres, "Habitación 101")
        formulario_reserva = self.client.get("/cliente/reservar/")
        self.assertContains(formulario_reserva, "Habitación 101")

        response = self.client.post("/cliente/reservar/", {
            "habitacion": self.habitacion.pk,
            "fecha_entrada": self.entrada.isoformat(),
            "fecha_salida": self.salida.isoformat(),
            "cantidad_huespedes": 1,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Reserva.objects.filter(habitacion=self.habitacion).count(), 1)

    def test_customer_cannot_double_book_overlapping_dates_but_can_book_another_period(self):
        cliente = User.objects.create_user(username="cliente-una-reserva")
        huesped = Huesped.objects.create(
            usuario=cliente,
            tipo_documento="CC",
            numero_documento="887766",
            nombres="Carlos",
            apellidos="Díaz",
            telefono="3001234567",
            correo="carlos@example.com",
        )
        otra_habitacion = Habitacion.objects.create(
            alojamiento=self.alojamiento,
            tipo=self.tipo,
            numero="102",
            precio=Decimal("120000.00"),
        )
        self.client.force_login(cliente)

        primera_respuesta = self.enviar_y_verificar_solicitud({
            "habitacion": self.habitacion.pk,
            "fecha_entrada": self.entrada.isoformat(),
            "fecha_salida": self.salida.isoformat(),
            "cantidad_huespedes": 1,
            "cantidad_ninos": 0,
        })
        self.assertRedirects(primera_respuesta, "/cliente/mis-reservas/")

        doble_reserva = self.client.post("/cliente/reservar/", {
            "habitacion": otra_habitacion.pk,
            "fecha_entrada": self.entrada.isoformat(),
            "fecha_salida": self.salida.isoformat(),
            "cantidad_huespedes": 1,
            "cantidad_ninos": 0,
        })
        self.assertEqual(doble_reserva.status_code, 200)
        self.assertContains(doble_reserva, "Ya tienes una reserva")
        self.assertEqual(Reserva.objects.filter(huesped=huesped).count(), 1)

        otra_fecha = self.enviar_y_verificar_solicitud({
            "habitacion": self.habitacion.pk,
            "fecha_entrada": self.salida.isoformat(),
            "fecha_salida": (self.salida + timedelta(days=1)).isoformat(),
            "cantidad_huespedes": 1,
            "cantidad_ninos": 0,
        })
        self.assertRedirects(otra_fecha, "/cliente/mis-reservas/")
        self.assertEqual(Reserva.objects.filter(huesped=huesped).count(), 2)

    def test_reservation_code_is_required_and_limited_to_five_attempts(self):
        cliente = User.objects.create_user(username="cliente-codigo")
        huesped = Huesped.objects.create(
            usuario=cliente,
            tipo_documento="CC",
            numero_documento="556677",
            nombres="Lucía",
            apellidos="Pérez",
            telefono="3001234567",
            correo="lucia@example.com",
        )
        self.client.force_login(cliente)

        response = self.client.post("/cliente/reservar/", {
            "habitacion": self.habitacion.pk,
            "fecha_entrada": self.entrada.isoformat(),
            "fecha_salida": self.salida.isoformat(),
            "cantidad_huespedes": 1,
        })
        self.assertRedirects(response, "/cliente/reservar/")
        self.assertFalse(Reserva.objects.filter(huesped=huesped).exists())
        self.assertEqual(mail.outbox[-1].to, ["lucia@example.com"])
        self.assertIn("no es un pago", mail.outbox[-1].body)

        for _ in range(5):
            response = self.client.post(
                "/cliente/reservar/verificar-correo/",
                {"codigo": "no-es-valido"},
            )
            self.assertRedirects(response, "/cliente/reservar/")

        self.assertFalse(Reserva.objects.filter(huesped=huesped).exists())
        formulario = self.client.get("/cliente/reservar/")
        self.assertContains(formulario, "Confirmar solicitud")
        self.assertNotContains(formulario, "Verificar y enviar solicitud")

    def test_expired_reservation_code_cannot_create_a_reservation(self):
        cliente = User.objects.create_user(username="cliente-codigo-vencido")
        huesped = Huesped.objects.create(
            usuario=cliente,
            tipo_documento="CC",
            numero_documento="445566",
            nombres="Eva",
            apellidos="Díaz",
            telefono="3001234567",
            correo="eva@example.com",
        )
        self.client.force_login(cliente)
        response = self.client.post("/cliente/reservar/", {
            "habitacion": self.habitacion.pk,
            "fecha_entrada": self.entrada.isoformat(),
            "fecha_salida": self.salida.isoformat(),
            "cantidad_huespedes": 1,
        })
        self.assertRedirects(response, "/cliente/reservar/")

        session = self.client.session
        verificacion = session["reserva_email_verification"]
        verificacion["expira"] = 0
        session["reserva_email_verification"] = verificacion
        session.save()
        codigo = re.search(
            r"Tu código de verificación es: (\d{6})",
            mail.outbox[-1].body,
        ).group(1)

        response = self.client.post(
            "/cliente/reservar/verificar-correo/",
            {"codigo": codigo},
        )
        self.assertRedirects(response, "/cliente/reservar/")
        self.assertFalse(Reserva.objects.filter(huesped=huesped).exists())

    def test_customer_can_add_active_services_to_reservation(self):
        cliente = User.objects.create_user(username="cliente-servicios")
        huesped = Huesped.objects.create(
            usuario=cliente,
            tipo_documento="CC",
            numero_documento="991122",
            nombres="María",
            apellidos="López",
            telefono="3001234567",
            correo="maria@example.com",
        )
        desayuno = Servicio.objects.create(
            nombre="Desayuno",
            descripcion="Desayuno para un huésped.",
            precio=Decimal("25000.00"),
            activo=True,
        )
        servicio_inactivo = Servicio.objects.create(
            nombre="Servicio inactivo",
            precio=Decimal("50000.00"),
            activo=False,
        )
        self.client.force_login(cliente)

        formulario = self.client.get("/cliente/reservar/")
        self.assertContains(formulario, "Desayuno")
        self.assertNotContains(formulario, "Desayuno para un huésped.")
        self.assertNotContains(formulario, "$25000")
        self.assertNotContains(formulario, "Servicio inactivo")
        self.assertContains(
            formulario,
            f'min="{date.today().isoformat()}"',
        )

        response = self.enviar_y_verificar_solicitud({
            "habitacion": self.habitacion.pk,
            "fecha_entrada": self.entrada.isoformat(),
            "fecha_salida": self.salida.isoformat(),
            "cantidad_huespedes": 2,
            "servicios": [str(desayuno.pk)],
        })

        self.assertRedirects(response, "/cliente/mis-reservas/")
        reserva = Reserva.objects.get(huesped=huesped)
        linea = ServicioReserva.objects.get(reserva=reserva)
        self.assertEqual(linea.servicio, desayuno)
        self.assertEqual(linea.cantidad, 1)
        self.assertEqual(linea.precio_unitario, Decimal("25000.00"))
        self.assertEqual(reserva.valor_total, Decimal("225000.00"))

        mis_reservas = self.client.get("/cliente/mis-reservas/")
        self.assertContains(mis_reservas, "Servicios agregados")
        self.assertContains(mis_reservas, "Desayuno")
        self.assertContains(mis_reservas, "$225000")

    def test_booking_shows_only_meals_and_keeps_restaurant_menu_for_the_hotel(self):
        cliente = User.objects.create_user(username="cliente-menu-reserva")
        huesped = Huesped.objects.create(
            usuario=cliente,
            tipo_documento="CC",
            numero_documento="112233",
            nombres="Carlos",
            apellidos="Díaz",
            telefono="3001234567",
            correo="carlos@example.com",
        )
        comidas = [
            Servicio.objects.create(
                nombre=nombre,
                precio=Decimal("25000.00"),
                area="RESTAURANTE",
            )
            for nombre in ("desayuno", "almuerzo", "cena")
        ]
        plato = Servicio.objects.create(
            nombre="Mojarra frita con arroz de coco",
            precio=Decimal("46000.00"),
            area="RESTAURANTE",
        )
        self.client.force_login(cliente)

        formulario = self.client.get("/cliente/reservar/")
        for comida in comidas:
            self.assertContains(formulario, comida.nombre)
        self.assertNotContains(formulario, plato.nombre)
        self.assertNotContains(formulario, "$25000")
        self.assertContains(formulario, "Al llegar al hotel podrás escoger los platos.")

        respuesta = self.client.post("/cliente/reservar/", {
            "habitacion": self.habitacion.pk,
            "fecha_entrada": self.entrada.isoformat(),
            "fecha_salida": self.salida.isoformat(),
            "cantidad_huespedes": 2,
            "servicios": [str(plato.pk)],
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Reserva.objects.filter(huesped=huesped).exists())

        role, _ = Rol.objects.get_or_create(nombre="Restaurante")
        empleado = User.objects.create_user(username="restaurante-menu-hotel")
        PerfilUsuario.objects.create(usuario=empleado, rol=role)
        self.client.force_login(empleado)

        catalogo = self.client.get("/servicios/")
        consumos = self.client.get("/consumos/")
        self.assertContains(catalogo, plato.nombre)
        self.assertContains(consumos, plato.nombre)
