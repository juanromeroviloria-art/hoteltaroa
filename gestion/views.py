
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.db import transaction
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied, ValidationError
from .models import Usuario as PerfilUsuario
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
    SolicitudCancelacion,
    TipoHabitacion,
)
from .forms import (
    AlojamientoForm,
    ConsumoForm,
    HabitacionForm,
    HuespedForm,
    PagoForm,
    ReservaForm,
    ServicioForm,
    ServicioReservaForm,
    TipoHabitacionForm,
)
from django.db.models.deletion import ProtectedError
from django.db.models import Count, Q, Sum
from datetime import date
from django.contrib.auth.password_validation import validate_password
from django.core.validators import validate_email
from django.db import models
from django.templatetags.static import static
from .operations import (
    cancelar_reserva,
    confirmar_reserva,
    registrar_check_in,
    registrar_check_out,
    sincronizar_estado_habitacion,
)
from .permissions import requiere_roles, usuario_tiene_rol


AREAS_CONSUMO_POR_ROL = {
    "Restaurante": "RESTAURANTE",
    "Bar": "BAR",
    "Lavandería": "LAVANDERIA",
}
COMIDAS_DISPONIBLES_EN_RESERVA = ("desayuno", "almuerzo", "cena")


def servicios_comida_reserva():
    filtro_nombre = Q()
    for nombre in COMIDAS_DISPONIBLES_EN_RESERVA:
        filtro_nombre |= Q(nombre__iexact=nombre)
    return Servicio.objects.filter(
        activo=True,
        area="RESTAURANTE",
    ).filter(filtro_nombre)


def obtener_imagen_alojamiento(alojamiento):
    if alojamiento and alojamiento.foto:
        return alojamiento.foto.url
    return static("img/hotel-taroa-costa.jpg")


def inicio(request):
    alojamiento = Alojamiento.objects.first()
    return render(request, "inicio.html", {
        "alojamiento": alojamiento,
        "imagen_alojamiento": obtener_imagen_alojamiento(alojamiento),
        "habitaciones_disponibles": Habitacion.objects.select_related(
            "alojamiento", "tipo"
        ).exclude(estado="MANTENIMIENTO").order_by("precio")[:6],
    })

def login_usuario(request):
    if request.user.is_authenticated:
        return redirect("panel")

    if request.method == "POST":
        usuario = request.POST.get("usuario", "").strip()
        contrasena = request.POST.get("contrasena", "")

        user = authenticate(
            request,
            username=usuario,
            password=contrasena
        )

        if user is not None:
            login(request, user)
            return redirect("panel")
        else:
            messages.error(
                request,
                "Usuario o contraseña incorrectos."
            )

    return render(request, "gestion/login.html")

@login_required
def panel(request):
    rol = PerfilUsuario.objects.filter(
        usuario=request.user
    ).values_list("rol__nombre", flat=True).first()
    if not usuario_tiene_rol(
        request.user,
        "Administrador",
        "Recepcionista",
        "Gerente",
        *AREAS_CONSUMO_POR_ROL,
    ):
        return redirect("habitaciones_cliente")

    if rol in AREAS_CONSUMO_POR_ROL:
        return redirect("consumos")

    habitaciones = Habitacion.objects.all()
    reservas = Reserva.objects.all()
    fecha_actual = date.today()
    rol_actual = "Administrador" if request.user.is_superuser else rol
    es_gerente = rol_actual == "Gerente"
    es_recepcionista = rol_actual == "Recepcionista"
    contexto = {
        "rol_actual": rol_actual,
        "es_gerente": es_gerente,
        "es_recepcionista": es_recepcionista,
        "fecha_actual": fecha_actual,
        "puede_administrar": usuario_tiene_rol(
            request.user, "Administrador"
        ),
        "puede_operar": usuario_tiene_rol(
            request.user, "Administrador", "Recepcionista"
        ),
        "total_habitaciones": habitaciones.count(),
        "habitaciones_disponibles": habitaciones.filter(
            estado="DISPONIBLE"
        ).count(),
        "habitaciones_ocupadas": habitaciones.filter(
            estado="OCUPADA"
        ).count(),
        "reservas_activas": reservas.filter(
            estado__in=["PENDIENTE", "CONFIRMADA", "EN_CURSO"]
        ).count(),
        "reservas_hoy": reservas.filter(
            fecha_entrada=fecha_actual,
            estado__in=["PENDIENTE", "CONFIRMADA"],
        ).count(),
        "reservas_pendientes": reservas.filter(
            estado="PENDIENTE"
        ).count(),
        "reservas_pendientes_hoy": reservas.filter(
            fecha_entrada=fecha_actual,
            estado="PENDIENTE",
        ).count(),
        "reservas_pendientes_lista": reservas.filter(
            estado="PENDIENTE",
        ).select_related(
            "huesped", "habitacion"
        ).order_by("fecha_entrada", "huesped__apellidos")[:8],
        "salidas_hoy": reservas.filter(
            fecha_salida=fecha_actual,
            estado="EN_CURSO",
        ).count(),
        "huespedes_alojados": reservas.filter(
            estado="EN_CURSO"
        ).count(),
        "salidas_hoy_lista": reservas.filter(
            fecha_salida=fecha_actual,
            estado="EN_CURSO",
        ).select_related(
            "huesped", "habitacion"
        ).order_by("fecha_salida", "huesped__apellidos")[:10],
        "total_huespedes": Huesped.objects.count(),
        "ingresos": Pago.objects.aggregate(total=Sum("valor"))["total"] or 0,
        "ingresos_mes": Pago.objects.filter(
            fecha__year=fecha_actual.year,
            fecha__month=fecha_actual.month,
        ).aggregate(total=Sum("valor"))["total"] or 0,
        "proximas_entradas": reservas.filter(
            fecha_entrada__gte=fecha_actual,
            estado__in=["PENDIENTE", "CONFIRMADA"],
        ).select_related(
            "huesped", "habitacion"
        ).order_by("fecha_entrada", "huesped__apellidos")[:10],
    }
    contexto["porcentaje_ocupacion"] = (
        contexto["habitaciones_ocupadas"] * 100 / contexto["total_habitaciones"]
        if contexto["total_habitaciones"]
        else 0
    )
    return render(request, "gestion/panel.html", contexto)



@login_required
@require_POST
def cerrar_sesion(request):
    logout(request)
    messages.success(request, "Has cerrado sesión correctamente.")
    return redirect("login")


@login_required
def perfil(request):
    huesped = getattr(request.user, "perfil_huesped", None)
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        try:
            validate_email(email)
            if huesped and not request.POST.get("telefono", "").strip():
                raise ValidationError("El teléfono es obligatorio.")
        except ValidationError as error:
            messages.error(request, "; ".join(error.messages))
        else:
            request.user.first_name = request.POST.get("first_name", "").strip()
            request.user.last_name = request.POST.get("last_name", "").strip()
            request.user.email = email
            request.user.save(update_fields=["first_name", "last_name", "email"])
            if huesped:
                huesped.nombres = request.user.first_name
                huesped.apellidos = request.user.last_name
                huesped.correo = request.user.email
                huesped.telefono = request.POST.get("telefono", "").strip()
                huesped.save(update_fields=[
                    "nombres",
                    "apellidos",
                    "correo",
                    "telefono",
                ])
            messages.success(request, "Perfil actualizado correctamente.")
            return redirect("perfil")
    return render(request, "gestion/perfil.html", {"huesped": huesped})


@login_required
@requiere_roles("Administrador")
def alojamiento_configurar(request):
    alojamiento = Alojamiento.objects.first()
    if request.method == "POST":
        form = AlojamientoForm(
            request.POST,
            request.FILES,
            instance=alojamiento,
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Información del alojamiento guardada.")
            return redirect("panel")
    else:
        form = AlojamientoForm(instance=alojamiento)
    return render(request, "gestion/alojamiento_form.html", {
        "form": form,
        "titulo": "Configurar alojamiento" if alojamiento else "Registrar alojamiento",
    })



@login_required
@requiere_roles("Administrador")
def usuarios(request):
    lista_usuarios = User.objects.all().order_by("username")
    return render(
        request,
        "gestion/usuarios.html",
        {"usuarios": lista_usuarios}
    )


@login_required
@requiere_roles("Administrador")
def usuario_crear(request):
    roles = obtener_roles()

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        role_id = request.POST.get("rol")
        is_active = "is_active" in request.POST

        rol = get_object_or_404(Rol, pk=role_id) if role_id else None

        if not username or not password or not rol:
            messages.error(
                request,
                "Completa el usuario, la contraseña y el rol."
            )
        elif User.objects.filter(username=username).exists():
            messages.error(request, "Ese nombre de usuario ya existe.")
        elif len(password) < 8:
            messages.error(
                request,
                "La contraseña debe tener al menos 8 caracteres."
            )
        else:
            with transaction.atomic():
                nuevo_usuario = User.objects.create_user(
                    username=username,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    is_active=is_active,
                    is_staff=(rol.nombre == "Administrador")
                )

                PerfilUsuario.objects.create(
                    usuario=nuevo_usuario,
                    rol=rol
                )

            messages.success(request, "Usuario creado correctamente.")
            return redirect("usuarios")

    return render(
        request,
        "gestion/usuario_form.html",
        {
            "accion": "Crear",
            "usuario_editado": None,
            "roles": roles,
            "rol_actual": None,
        }
    )


@login_required
@requiere_roles("Administrador")
def usuario_editar(request, usuario_id):
    usuario_editado = get_object_or_404(User, pk=usuario_id)
    roles = obtener_roles()

    perfil = PerfilUsuario.objects.filter(
        usuario=usuario_editado
    ).select_related("rol").first()

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        role_id = request.POST.get("rol")
        is_active = "is_active" in request.POST

        rol = get_object_or_404(Rol, pk=role_id) if role_id else None

        if not username or not rol:
            messages.error(request, "El usuario y el rol son obligatorios.")
        elif User.objects.filter(username=username).exclude(
            pk=usuario_id
        ).exists():
            messages.error(request, "Ese nombre de usuario ya existe.")
        elif password and len(password) < 8:
            messages.error(
                request,
                "La nueva contraseña debe tener al menos 8 caracteres."
            )
        elif usuario_editado.pk == request.user.pk and not is_active:
            messages.error(request, "No puedes desactivar tu propia cuenta.")
        else:
            with transaction.atomic():
                usuario_editado.username = username
                usuario_editado.first_name = first_name
                usuario_editado.last_name = last_name
                usuario_editado.email = email
                usuario_editado.is_active = is_active
                usuario_editado.is_staff = (
                    rol.nombre == "Administrador"
                )

                if password:
                    usuario_editado.set_password(password)

                usuario_editado.save()

                if perfil:
                    perfil.rol = rol
                    perfil.save(update_fields=["rol"])
                else:
                    PerfilUsuario.objects.create(
                        usuario=usuario_editado,
                        rol=rol
                    )

            messages.success(request, "Usuario actualizado correctamente.")
            return redirect("usuarios")

    return render(
        request,
        "gestion/usuario_form.html",
        {
            "accion": "Editar",
            "usuario_editado": usuario_editado,
            "roles": roles,
            "rol_actual": perfil.rol_id if perfil else None,
        }
    )


@login_required
@requiere_roles("Administrador")
@require_POST
def usuario_estado(request, usuario_id):
    usuario_objetivo = get_object_or_404(User, pk=usuario_id)

    if usuario_objetivo.pk == request.user.pk:
        messages.error(request, "No puedes desactivar tu propia cuenta.")
    else:
        usuario_objetivo.is_active = not usuario_objetivo.is_active
        usuario_objetivo.save(update_fields=["is_active"])
        messages.success(request, "El estado del usuario fue actualizado.")

    return redirect("usuarios")


@login_required
@requiere_roles("Administrador")
@require_POST
def usuario_eliminar(request, usuario_id):
    usuario_objetivo = get_object_or_404(User, pk=usuario_id)

    if usuario_objetivo.pk == request.user.pk:
        messages.error(request, "No puedes eliminar tu propia cuenta.")
    else:
        usuario_objetivo.delete()
        messages.success(request, "Usuario eliminado correctamente.")

    return redirect("usuarios")


def obtener_roles():
    roles = [
        "Administrador",
        "Recepcionista",
        "Gerente",
        "Restaurante",
        "Bar",
        "Lavandería",
        "Cliente",
    ]

    for nombre in roles:
        Rol.objects.get_or_create(nombre=nombre)

    return Rol.objects.filter(nombre__in=roles).order_by("id")

def es_administrador(user):
    return usuario_tiene_rol(user, "Administrador")


@login_required
@user_passes_test(es_administrador, login_url="login")
def roles(request):
    lista_roles = Rol.objects.all().order_by("nombre")

    return render(request, "gestion/roles.html", {
        "roles": lista_roles
    })


@login_required
@user_passes_test(es_administrador, login_url="login")
def rol_crear(request):
    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        descripcion = request.POST.get("descripcion", "").strip()

        if not nombre:
            messages.error(request, "Escribe el nombre del rol.")
        elif Rol.objects.filter(nombre__iexact=nombre).exists():
            messages.error(request, "Ya existe un rol con ese nombre.")
        else:
            Rol.objects.create(
                nombre=nombre,
                descripcion=descripcion
            )
            messages.success(request, "Rol creado correctamente.")
            return redirect("roles")

    return render(request, "gestion/rol_form.html", {
        "titulo": "Crear rol",
        "rol": None
    })


@login_required
@user_passes_test(es_administrador, login_url="login")
def rol_editar(request, rol_id):
    rol = get_object_or_404(Rol, id=rol_id)

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        descripcion = request.POST.get("descripcion", "").strip()

        if not nombre:
            messages.error(request, "Escribe el nombre del rol.")
        elif Rol.objects.filter(
            nombre__iexact=nombre
        ).exclude(id=rol.id).exists():
            messages.error(request, "Ya existe otro rol con ese nombre.")
        else:
            rol.nombre = nombre
            rol.descripcion = descripcion
            rol.save()

            messages.success(request, "Rol actualizado correctamente.")
            return redirect("roles")

    return render(request, "gestion/rol_form.html", {
        "titulo": "Editar rol",
        "rol": rol
    })


@login_required
@user_passes_test(es_administrador, login_url="login")
def rol_eliminar(request, rol_id):
    rol = get_object_or_404(Rol, id=rol_id)

    if request.method == "POST":
        if PerfilUsuario.objects.filter(rol=rol).exists():
            messages.error(
                request,
                "No puedes eliminar este rol porque tiene usuarios asignados."
            )
        else:
            rol.delete()
            messages.success(request, "Rol eliminado correctamente.")

        return redirect("roles")

    return redirect("roles")



@login_required
@user_passes_test(es_administrador, login_url="login")
def habitaciones(request):
    lista_habitaciones = Habitacion.objects.select_related(
        "alojamiento", "tipo"
    ).order_by("numero")
    busqueda = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "")
    if busqueda:
        lista_habitaciones = lista_habitaciones.filter(
            Q(numero__icontains=busqueda)
            | Q(tipo__nombre__icontains=busqueda)
            | Q(alojamiento__nombre__icontains=busqueda)
        )
    if estado in dict(Habitacion.ESTADOS):
        lista_habitaciones = lista_habitaciones.filter(estado=estado)

    total_habitaciones = lista_habitaciones.count()
    return render(request, "gestion/habitaciones.html", {
        "habitaciones": Paginator(lista_habitaciones, 20).get_page(
            request.GET.get("page")
        ),
        "busqueda": busqueda,
        "estado_filtro": estado,
        "estados_habitacion": Habitacion.ESTADOS,
        "total_habitaciones": total_habitaciones,
    })


@login_required
@user_passes_test(es_administrador, login_url="login")
def habitacion_crear(request):
    if request.method == "POST":
        formulario = HabitacionForm(request.POST, request.FILES)

        if formulario.is_valid():
            habitacion = formulario.save(commit=False)

            repetida = Habitacion.objects.filter(
                alojamiento=habitacion.alojamiento,
                numero=habitacion.numero
            ).exists()

            if repetida:
                formulario.add_error(
                    "numero",
                    "Ya existe una habitación con ese número en este establecimiento."
                )
            else:
                habitacion.save()
                messages.success(
                    request, "Habitación creada correctamente."
                )
                return redirect("habitaciones")
    else:
        formulario = HabitacionForm()

    return render(request, "gestion/habitacion_form.html", {
        "formulario": formulario,
        "titulo": "Crear habitación",
    })


@login_required
@user_passes_test(es_administrador, login_url="login")
def habitacion_editar(request, habitacion_id):
    habitacion = get_object_or_404(Habitacion, pk=habitacion_id)

    if request.method == "POST":
        formulario = HabitacionForm(
            request.POST,
            request.FILES,
            instance=habitacion,
        )

        if formulario.is_valid():
            repetida = Habitacion.objects.filter(
                alojamiento=formulario.cleaned_data["alojamiento"],
                numero=formulario.cleaned_data["numero"]
            ).exclude(pk=habitacion.pk).exists()

            if repetida:
                formulario.add_error(
                    "numero",
                    "Ya existe una habitación con ese número en este establecimiento."
                )
            else:
                formulario.save()
                messages.success(
                    request, "Habitación actualizada correctamente."
                )
                return redirect("habitaciones")
    else:
        formulario = HabitacionForm(instance=habitacion)

    return render(request, "gestion/habitacion_form.html", {
        "formulario": formulario,
        "titulo": "Editar habitación",
    })


@login_required
@user_passes_test(es_administrador, login_url="login")
def habitacion_eliminar(request, habitacion_id):
    habitacion = get_object_or_404(Habitacion, pk=habitacion_id)

    if request.method == "POST":
        if Reserva.objects.filter(habitacion=habitacion).exists():
            messages.error(
                request,
                "No se puede eliminar esta habitación porque tiene reservas registradas."
            )
        else:
            habitacion.delete()
            messages.success(
                request, "Habitación eliminada correctamente."
            )

    return redirect("habitaciones")

@login_required
@user_passes_test(es_administrador, login_url="login")
def tipos_habitacion(request):
    tipos = TipoHabitacion.objects.all().order_by("nombre")

    return render(request, "gestion/tipos_habitacion.html", {
        "tipos": tipos,
    })


@login_required
@user_passes_test(es_administrador, login_url="login")
def tipo_habitacion_crear(request):
    if request.method == "POST":
        formulario = TipoHabitacionForm(request.POST)

        if formulario.is_valid():
            nombre = formulario.cleaned_data["nombre"].strip()

            if TipoHabitacion.objects.filter(
                nombre__iexact=nombre
            ).exists():
                formulario.add_error(
                    "nombre",
                    "Ya existe un tipo de habitación con ese nombre."
                )
            else:
                formulario.save()
                messages.success(
                    request, "Tipo de habitación creado correctamente."
                )
                return redirect("tipos_habitacion")
    else:
        formulario = TipoHabitacionForm()

    return render(request, "gestion/tipo_habitacion_form.html", {
        "formulario": formulario,
        "titulo": "Crear tipo de habitación",
    })


@login_required
@user_passes_test(es_administrador, login_url="login")
def tipo_habitacion_editar(request, tipo_id):
    tipo = get_object_or_404(TipoHabitacion, pk=tipo_id)

    if request.method == "POST":
        formulario = TipoHabitacionForm(request.POST, instance=tipo)

        if formulario.is_valid():
            nombre = formulario.cleaned_data["nombre"].strip()

            repetido = TipoHabitacion.objects.filter(
                nombre__iexact=nombre
            ).exclude(pk=tipo.pk).exists()

            if repetido:
                formulario.add_error(
                    "nombre",
                    "Ya existe otro tipo de habitación con ese nombre."
                )
            else:
                formulario.save()
                messages.success(
                    request, "Tipo de habitación actualizado correctamente."
                )
                return redirect("tipos_habitacion")
    else:
        formulario = TipoHabitacionForm(instance=tipo)

    return render(request, "gestion/tipo_habitacion_form.html", {
        "formulario": formulario,
        "titulo": "Editar tipo de habitación",
    })


@login_required
@user_passes_test(es_administrador, login_url="login")
def tipo_habitacion_eliminar(request, tipo_id):
    tipo = get_object_or_404(TipoHabitacion, pk=tipo_id)

    if request.method == "POST":
        if Habitacion.objects.filter(tipo=tipo).exists():
            messages.error(
                request,
                "No puedes eliminar este tipo porque tiene habitaciones asociadas."
            )
        else:
            tipo.delete()
            messages.success(
                request, "Tipo de habitación eliminado correctamente."
            )

    return redirect("tipos_habitacion")


@login_required
@requiere_roles(
    "Administrador",
    "Recepcionista",
    "Gerente",
    *AREAS_CONSUMO_POR_ROL,
)
def servicios(request):
    rol = PerfilUsuario.objects.filter(
        usuario=request.user
    ).values_list("rol__nombre", flat=True).first()
    es_admin = usuario_tiene_rol(request.user, "Administrador")
    lista_servicios = Servicio.objects.all()
    if rol in AREAS_CONSUMO_POR_ROL:
        lista_servicios = lista_servicios.filter(
            area=AREAS_CONSUMO_POR_ROL[rol]
        )
    return render(request, "gestion/servicios.html", {
        "servicios": lista_servicios.order_by("area", "nombre"),
        "puede_agregar_servicio": es_admin or rol in AREAS_CONSUMO_POR_ROL,
        "puede_administrar_servicios": es_admin,
    })


@login_required
@requiere_roles("Administrador", *AREAS_CONSUMO_POR_ROL)
def servicio_crear(request):
    rol = PerfilUsuario.objects.filter(
        usuario=request.user
    ).values_list("rol__nombre", flat=True).first()
    area_permitida = AREAS_CONSUMO_POR_ROL.get(rol)
    form = ServicioForm(
        request.POST or None,
        area_permitida=area_permitida,
    )

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Servicio creado correctamente.")
        return redirect("servicios")

    return render(request, "gestion/servicio_form.html", {
        "form": form,
        "titulo": "Crear servicio",
        "boton": "Guardar servicio",
    })


@login_required
@user_passes_test(es_administrador, login_url="login")
def servicio_editar(request, servicio_id):
    servicio = get_object_or_404(Servicio, pk=servicio_id)
    form = ServicioForm(request.POST or None, instance=servicio)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Servicio actualizado correctamente.")
        return redirect("servicios")

    return render(request, "gestion/servicio_form.html", {
        "form": form,
        "titulo": "Editar servicio",
        "boton": "Guardar cambios",
    })


@login_required
@user_passes_test(es_administrador, login_url="login")
def servicio_eliminar(request, servicio_id):
    servicio = get_object_or_404(Servicio, pk=servicio_id)

    if request.method == "POST":
        if ServicioReserva.objects.filter(servicio=servicio).exists():
            messages.error(
                request,
                "No puedes eliminar este servicio porque está asociado a reservas."
            )
        else:
            servicio.delete()
            messages.success(request, "Servicio eliminado correctamente.")

        return redirect("servicios")

    return render(request, "gestion/servicios.html", {
        "servicios": Servicio.objects.all().order_by("nombre"),
        "servicio_eliminar": servicio,
        "puede_administrar_servicios": True,
    })



@login_required
@requiere_roles("Administrador", "Recepcionista")
def huespedes(request):
    busqueda = request.GET.get("q", "").strip()
    lista_huespedes = Huesped.objects.all().order_by("apellidos", "nombres")
    if busqueda:
        lista_huespedes = lista_huespedes.filter(
            Q(nombres__icontains=busqueda)
            | Q(apellidos__icontains=busqueda)
            | Q(numero_documento__icontains=busqueda)
            | Q(correo__icontains=busqueda)
        )
    lista_huespedes = Paginator(lista_huespedes, 20).get_page(
        request.GET.get("page")
    )

    return render(request, "gestion/huespedes.html", {
        "huespedes": lista_huespedes,
        "busqueda": busqueda,
    })


@login_required
@requiere_roles("Administrador", "Recepcionista")
def huesped_crear(request):
    form = HuespedForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Huésped registrado correctamente.")
        return redirect("huespedes")

    return render(request, "gestion/huesped_form.html", {
        "form": form,
        "titulo": "Registrar huésped",
        "boton": "Guardar huésped",
    })


@login_required
@requiere_roles("Administrador", "Recepcionista")
def huesped_editar(request, huesped_id):
    huesped = get_object_or_404(Huesped, pk=huesped_id)
    form = HuespedForm(request.POST or None, instance=huesped)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Huésped actualizado correctamente.")
        return redirect("huespedes")

    return render(request, "gestion/huesped_form.html", {
        "form": form,
        "titulo": "Editar huésped",
        "boton": "Guardar cambios",
    })


@login_required
@requiere_roles("Administrador", "Recepcionista")
def huesped_eliminar(request, huesped_id):
    huesped = get_object_or_404(Huesped, pk=huesped_id)

    if request.method == "POST":
        try:
            huesped.delete()
            messages.success(request, "Huésped eliminado correctamente.")
        except ProtectedError:
            messages.error(
                request,
                "No se puede eliminar este huésped porque tiene reservas asociadas."
            )

        return redirect("huespedes")

    return render(request, "gestion/huespedes.html", {
        "huespedes": Huesped.objects.all().order_by("apellidos", "nombres"),
        "huesped_eliminar": huesped,
    })


@login_required
@requiere_roles("Administrador", "Recepcionista", "Gerente")
def reservas(request):
    lista = Reserva.objects.select_related(
        "huesped", "habitacion"
    ).prefetch_related(
        "pagos", "servicios", "consumos"
    ).order_by("-fecha_registro")
    estado = request.GET.get("estado", "")
    busqueda = request.GET.get("q", "").strip()
    if estado in dict(Reserva.ESTADOS):
        lista = lista.filter(estado=estado)
    if busqueda:
        lista = lista.filter(
            Q(huesped__nombres__icontains=busqueda)
            | Q(huesped__apellidos__icontains=busqueda)
            | Q(huesped__numero_documento__icontains=busqueda)
            | Q(habitacion__numero__icontains=busqueda)
        )
    lista = Paginator(lista, 20).get_page(request.GET.get("page"))

    return render(request, "gestion/reservas.html", {
        "reservas": lista,
        "estado_filtro": estado,
        "busqueda": busqueda,
        "estados_reserva": Reserva.ESTADOS,
        "solicitudes_cancelacion": SolicitudCancelacion.objects.filter(
            estado="PENDIENTE"
        ).select_related("reserva", "reserva__huesped").order_by(
            "fecha_solicitud"
        ),
        "puede_operar": usuario_tiene_rol(
            request.user, "Administrador", "Recepcionista"
        ),
        "puede_administrar": usuario_tiene_rol(
            request.user, "Administrador"
        ),
    })


@login_required
@requiere_roles("Administrador", "Recepcionista")
def reserva_crear(request):
    if request.method == "POST":
        with transaction.atomic():
            habitacion_id = request.POST.get("habitacion", "")
            if habitacion_id.isdigit():
                Habitacion.objects.select_for_update().filter(
                    pk=habitacion_id
                ).first()
            form = ReservaForm(request.POST)
            if form.is_valid():
                reserva = form.save(commit=False)
                reserva.usuario = request.user
                reserva.save()
                sincronizar_estado_habitacion(reserva.habitacion_id)
                messages.success(request, "Reserva creada correctamente.")
                return redirect("reservas")
    else:
        form = ReservaForm()

    return render(request, "gestion/reserva_form.html", {
        "form": form,
        "titulo": "Crear reserva",
        "boton": "Guardar reserva",
    })


@login_required
@requiere_roles("Administrador", "Recepcionista")
def reserva_editar(request, reserva_id):
    reserva = get_object_or_404(Reserva, pk=reserva_id)
    if reserva.estado not in ["PENDIENTE", "CONFIRMADA"]:
        messages.error(request, "Esta reserva ya no se puede modificar.")
        return redirect("reservas")
    if request.method == "POST":
        with transaction.atomic():
            reserva = get_object_or_404(
                Reserva.objects.select_for_update(),
                pk=reserva_id,
            )
            if reserva.estado not in ["PENDIENTE", "CONFIRMADA"]:
                messages.error(request, "Esta reserva ya no se puede modificar.")
                return redirect("reservas")
            habitacion_original_id = reserva.habitacion_id
            habitacion_id = request.POST.get("habitacion", "")
            if habitacion_id.isdigit():
                Habitacion.objects.select_for_update().filter(
                    pk=habitacion_id
                ).first()
            form = ReservaForm(request.POST, instance=reserva)
            if form.is_valid():
                reserva_actualizada = form.save(commit=False)
                if reserva_actualizada.habitacion_id != habitacion_original_id:
                    reserva_actualizada.precio_noche = (
                        reserva_actualizada.habitacion.precio
                    )
                reserva_actualizada.save()
                sincronizar_estado_habitacion(habitacion_original_id)
                sincronizar_estado_habitacion(
                    reserva_actualizada.habitacion_id
                )
                messages.success(request, "Reserva actualizada correctamente.")
                return redirect("reservas")
    else:
        form = ReservaForm(instance=reserva)

    return render(request, "gestion/reserva_form.html", {
        "form": form,
        "titulo": "Editar reserva",
        "boton": "Guardar cambios",
    })


@login_required
@user_passes_test(es_administrador, login_url="login")
def reserva_eliminar(request, reserva_id):
    if request.method == "POST":
        with transaction.atomic():
            reserva = get_object_or_404(
                Reserva.objects.select_for_update(),
                pk=reserva_id,
            )
            if reserva.estado != "CANCELADA":
                messages.error(
                    request,
                    "Cancela la reserva antes de eliminarla para conservar su trazabilidad.",
                )
            else:
                try:
                    reserva.delete()
                    messages.success(request, "Reserva eliminada correctamente.")
                except ProtectedError:
                    messages.error(
                        request,
                        "No se puede eliminar porque la reserva tiene pagos asociados."
                    )

        return redirect("reservas")

    reserva = get_object_or_404(Reserva, pk=reserva_id)
    lista = Reserva.objects.select_related(
        "huesped", "habitacion"
    ).order_by("-fecha_registro")

    return render(request, "gestion/reservas.html", {
        "reservas": lista,
        "reserva_eliminar": reserva,
    })


@login_required
@requiere_roles("Administrador", "Recepcionista")
@require_POST
def reserva_cancelar(request, reserva_id):
    try:
        cancelar_reserva(reserva_id)
    except (Reserva.DoesNotExist, ValidationError) as error:
        messages.error(request, "; ".join(getattr(error, "messages", [str(error)])))
    else:
        messages.success(request, "Reserva cancelada.")
    return redirect("reservas")


@login_required
@requiere_roles("Administrador", "Recepcionista")
@require_POST
def reserva_confirmar(request, reserva_id):
    try:
        confirmar_reserva(reserva_id)
    except (Reserva.DoesNotExist, ValidationError) as error:
        messages.error(request, "; ".join(getattr(error, "messages", [str(error)])))
    else:
        messages.success(request, "Reserva confirmada.")
    return redirect("reservas")


@login_required
@requiere_roles("Administrador", "Recepcionista")
@require_POST
def reserva_check_in(request, reserva_id):
    try:
        registrar_check_in(reserva_id)
    except (Reserva.DoesNotExist, ValidationError) as error:
        messages.error(request, "; ".join(getattr(error, "messages", [str(error)])))
    else:
        messages.success(request, "Check-in registrado correctamente.")
    return redirect("reservas")


@login_required
@requiere_roles("Administrador", "Recepcionista")
@require_POST
def reserva_check_out(request, reserva_id):
    try:
        reserva = registrar_check_out(reserva_id)
    except (Reserva.DoesNotExist, ValidationError) as error:
        messages.error(request, "; ".join(getattr(error, "messages", [str(error)])))
    else:
        messages.success(
            request,
            f"Check-out registrado. Total: ${reserva.valor_total:,.2f}; "
            f"saldo pendiente: ${reserva.saldo_pendiente:,.2f}.",
        )
        return redirect("reserva_factura", reserva_id=reserva.pk)
    return redirect("reservas")


@login_required
def reserva_factura(request, reserva_id):
    reserva = get_object_or_404(
        Reserva.objects.select_related(
            "huesped",
            "habitacion",
            "habitacion__tipo",
            "habitacion__alojamiento",
        ).prefetch_related(
            "servicios__servicio",
            "consumos__servicio",
            "consumos__registrado_por",
            "pagos",
        ),
        pk=reserva_id,
    )
    if not usuario_tiene_rol(
        request.user, "Administrador", "Recepcionista", "Gerente"
    ):
        huesped = getattr(request.user, "perfil_huesped", None)
        if not huesped or reserva.huesped_id != huesped.pk:
            raise PermissionDenied
    return render(request, "gestion/factura_reserva.html", {
        "reserva": reserva,
        "total_alojamiento": reserva.noches * reserva.precio_noche,
        "puede_operar": usuario_tiene_rol(
            request.user, "Administrador", "Recepcionista"
        ),
        "es_cliente": not usuario_tiene_rol(
            request.user, "Administrador", "Recepcionista", "Gerente"
        ),
    })


@login_required
@requiere_roles("Administrador", "Recepcionista")
def reserva_servicio(request, reserva_id):
    reserva = get_object_or_404(
        Reserva.objects.select_related("habitacion"),
        pk=reserva_id,
    )
    if reserva.estado in ["CANCELADA", "FINALIZADA"]:
        messages.error(request, "No se pueden agregar servicios a esta reserva.")
        return redirect("reservas")

    form = ServicioReservaForm(request.POST or None)
    form.fields["servicio"].queryset = Servicio.objects.filter(
        activo=True,
        area="RESTAURANTE",
    )
    form.fields["cantidad"].label = "Unidades adicionales"
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            reserva = Reserva.objects.select_for_update().get(pk=reserva_id)
            if reserva.estado in ["CANCELADA", "FINALIZADA"]:
                messages.error(
                    request,
                    "No se pueden agregar servicios a esta reserva.",
                )
                return redirect("reservas")
            servicio = form.cleaned_data["servicio"]
            cantidad = form.cleaned_data["cantidad"]
            linea, creada = ServicioReserva.objects.get_or_create(
                reserva=reserva,
                servicio=servicio,
                defaults={
                    "cantidad": cantidad,
                    "precio_unitario": servicio.precio,
                },
            )
            if not creada:
                linea.cantidad += cantidad
                linea.save(update_fields=["cantidad"])
        messages.success(request, "Servicio agregado a la reserva.")
        return redirect("reservas")

    return render(request, "gestion/servicio_reserva_form.html", {
        "reserva": reserva,
        "form": form,
    })


@login_required
@requiere_roles(*AREAS_CONSUMO_POR_ROL)
def consumos(request):
    rol = PerfilUsuario.objects.select_related("rol").get(
        usuario=request.user
    ).rol.nombre
    area = AREAS_CONSUMO_POR_ROL[rol]
    form = ConsumoForm(request.POST or None, area=area)

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            reserva = Reserva.objects.select_for_update().get(
                pk=form.cleaned_data["reserva"].pk
            )
            servicio = Servicio.objects.select_for_update().get(
                pk=form.cleaned_data["servicio"].pk,
                activo=True,
                area=area,
            )
            if reserva.estado != "EN_CURSO":
                form.add_error(
                    "reserva",
                    "Solo se pueden registrar consumos de huéspedes alojados.",
                )
            else:
                Consumo.objects.create(
                    reserva=reserva,
                    servicio=servicio,
                    area=area,
                    cantidad=form.cleaned_data["cantidad"],
                    precio_unitario=servicio.precio,
                    registrado_por=request.user,
                )
                messages.success(
                    request,
                    f"Consumo de {servicio.nombre} agregado a la reserva "
                    f"de la habitación {reserva.habitacion.numero}.",
                )
                return redirect("consumos")

    consumos_recientes = Consumo.objects.filter(
        area=area,
    ).select_related(
        "reserva",
        "reserva__huesped",
        "reserva__habitacion",
        "servicio",
    ).order_by("-fecha")[:30]
    return render(request, "gestion/consumos.html", {
        "form": form,
        "area": rol,
        "consumos_recientes": consumos_recientes,
    })


@login_required
@requiere_roles("Administrador", "Recepcionista")
@require_POST
def resolver_solicitud_cancelacion(request, solicitud_id):
    solicitud = get_object_or_404(
        SolicitudCancelacion.objects.select_related("reserva"),
        pk=solicitud_id,
        estado="PENDIENTE",
    )
    accion = request.POST.get("accion")
    if accion not in ["APROBADA", "RECHAZADA"]:
        messages.error(request, "La decisión de cancelación no es válida.")
        return redirect("reservas")

    with transaction.atomic():
        reserva = Reserva.objects.select_for_update().get(
            pk=solicitud.reserva_id
        )
        if accion == "APROBADA":
            if reserva.estado not in ["PENDIENTE", "CONFIRMADA"]:
                messages.error(
                    request,
                    "La reserva ya no admite cancelación.",
                )
                return redirect("reservas")
            reserva.estado = "CANCELADA"
            reserva.save(update_fields=["estado"])
            sincronizar_estado_habitacion(reserva.habitacion_id)
        solicitud.estado = accion
        solicitud.save(update_fields=["estado"])
    messages.success(request, "Solicitud de cancelación procesada.")
    return redirect("reservas")




@login_required
@requiere_roles("Administrador", "Recepcionista", "Gerente")
def pagos(request):
    lista = Pago.objects.select_related(
        "reserva",
        "reserva__huesped",
        "reserva__habitacion",
    ).prefetch_related(
        "reserva__pagos",
        "reserva__servicios",
        "reserva__consumos",
    ).order_by("-fecha")
    pagos_lista = Paginator(lista, 20).get_page(request.GET.get("page"))

    return render(request, "gestion/pagos.html", {
        "pagos": pagos_lista,
        "puede_operar": usuario_tiene_rol(
            request.user, "Administrador", "Recepcionista"
        ),
        "puede_administrar": usuario_tiene_rol(
            request.user, "Administrador"
        ),
    })


@login_required
@requiere_roles("Administrador", "Recepcionista")
def pago_crear(request):
    if request.method == "POST":
        reserva_id = request.POST.get("reserva", "")
        with transaction.atomic():
            if reserva_id.isdigit():
                Reserva.objects.select_for_update().filter(
                    pk=reserva_id
                ).first()
            form = PagoForm(request.POST)
            if form.is_valid():
                pago = form.save()
                messages.success(request, "Pago registrado correctamente.")
                if pago.reserva.estado == "FINALIZADA":
                    return redirect(
                        "reserva_factura",
                        reserva_id=pago.reserva_id,
                    )
                return redirect("pagos")
    else:
        form = PagoForm()
        reserva_id = request.GET.get("reserva", "")
        if reserva_id.isdigit() and Reserva.objects.filter(
            pk=reserva_id
        ).exists():
            form.initial["reserva"] = int(reserva_id)

    return render(request, "gestion/pago_form.html", {
        "form": form,
        "titulo": "Registrar pago",
        "boton": "Guardar pago",
    })


@login_required
@user_passes_test(es_administrador, login_url="login")
def pago_editar(request, pago_id):
    pago = get_object_or_404(Pago, pk=pago_id)
    if request.method == "POST":
        with transaction.atomic():
            Reserva.objects.select_for_update().filter(
                pk=pago.reserva_id
            ).first()
            form = PagoForm(request.POST, instance=pago)
            form.fields["reserva"].disabled = True
            if form.is_valid():
                form.save()
                messages.success(request, "Pago actualizado correctamente.")
                return redirect("pagos")
    else:
        form = PagoForm(instance=pago)
        form.fields["reserva"].disabled = True

    return render(request, "gestion/pago_form.html", {
        "form": form,
        "titulo": "Editar pago",
        "boton": "Guardar cambios",
    })


@login_required
@user_passes_test(es_administrador, login_url="login")
def pago_eliminar(request, pago_id):
    pago = get_object_or_404(Pago, pk=pago_id)

    if request.method == "POST":
        pago.delete()
        messages.success(request, "Pago eliminado correctamente.")

    return redirect("pagos")


@login_required
@requiere_roles("Administrador", "Gerente")
def reportes(request):
    inicio = request.GET.get("desde", "")
    fin = request.GET.get("hasta", "")
    estado = request.GET.get("estado", "")
    habitacion_id = request.GET.get("habitacion", "")
    huesped_id = request.GET.get("huesped", "")
    if inicio and fin:
        try:
            if date.fromisoformat(inicio) > date.fromisoformat(fin):
                raise ValueError
        except ValueError:
            messages.error(
                request,
                "El periodo debe tener una fecha inicial anterior o igual a la final.",
            )
            inicio = ""
            fin = ""
    if estado and estado not in dict(Reserva.ESTADOS):
        messages.error(request, "El estado seleccionado no es válido.")
        estado = ""
    reservas = Reserva.objects.select_related(
        "huesped",
        "habitacion",
        "habitacion__tipo",
    ).prefetch_related(
        "pagos",
        "servicios",
        "consumos",
    ).order_by("-fecha_entrada")
    pagos = Pago.objects.select_related("reserva")
    if inicio:
        try:
            fecha_inicio = date.fromisoformat(inicio)
            reservas = reservas.filter(fecha_entrada__gte=fecha_inicio)
            pagos = pagos.filter(fecha__date__gte=fecha_inicio)
        except ValueError:
            messages.error(request, "La fecha inicial no es válida.")
            inicio = ""
    if fin:
        try:
            fecha_fin = date.fromisoformat(fin)
            reservas = reservas.filter(fecha_entrada__lte=fecha_fin)
            pagos = pagos.filter(fecha__date__lte=fecha_fin)
        except ValueError:
            messages.error(request, "La fecha final no es válida.")
            fin = ""
    if estado in dict(Reserva.ESTADOS):
        reservas = reservas.filter(estado=estado)
    if habitacion_id:
        if habitacion_id.isdigit():
            reservas = reservas.filter(habitacion_id=habitacion_id)
        else:
            messages.error(request, "El filtro de habitación no es válido.")
            habitacion_id = ""
    if huesped_id:
        if huesped_id.isdigit():
            reservas = reservas.filter(huesped_id=huesped_id)
        else:
            messages.error(request, "El filtro de huésped no es válido.")
            huesped_id = ""
    pagos = pagos.filter(reserva__in=reservas)
    ingresos = pagos.aggregate(total=Sum("valor"))["total"] or 0
    valor_saldos = sum(
        (reserva.saldo_pendiente for reserva in reservas),
        start=0,
    )
    total_habitaciones = Habitacion.objects.count()
    habitaciones_ocupadas = Habitacion.objects.filter(
        estado="OCUPADA"
    ).count()
    contexto = {
        "total_habitaciones": Habitacion.objects.count(),
        "total_huespedes": Huesped.objects.count(),
        "total_reservas": reservas.count(),
        "total_pagos": pagos.count(),
        "valor_total_pagos": ingresos,
        "saldo_pendiente": valor_saldos,
        "habitaciones_ocupadas": habitaciones_ocupadas,
        "habitaciones_disponibles": Habitacion.objects.filter(
            estado="DISPONIBLE"
        ).count(),
        "porcentaje_ocupacion": (
            habitaciones_ocupadas * 100 / total_habitaciones
            if total_habitaciones else 0
        ),
        "reservas_pendientes": reservas.filter(estado="PENDIENTE").count(),
        "reservas_confirmadas": reservas.filter(estado="CONFIRMADA").count(),
        "pagos_recientes": pagos.select_related(
            "reserva",
            "reserva__huesped",
            "reserva__habitacion",
        ).order_by("-fecha")[:10],
        "reservas_reporte": Paginator(reservas, 20).get_page(
            request.GET.get("page")
        ),
        "desde": inicio,
        "hasta": fin,
        "estado_filtro": estado,
        "estados_reserva": Reserva.ESTADOS,
        "habitacion_filtro": habitacion_id,
        "huesped_filtro": huesped_id,
        "habitaciones_filtro": Habitacion.objects.order_by(
            "alojamiento__nombre", "numero"
        ),
        "huespedes_filtro": Huesped.objects.order_by("apellidos", "nombres"),
        "huespedes_reporte": Huesped.objects.annotate(
            cantidad_reservas=Count("reserva")
        ).order_by("-cantidad_reservas", "apellidos")[:20],
        "servicios_vendidos": ServicioReserva.objects.filter(
            reserva__in=reservas
        ).aggregate(
            unidades=Sum("cantidad"),
            ingresos=Sum(models.F("cantidad") * models.F("precio_unitario")),
        ),
        "consumos_vendidos": Consumo.objects.filter(
            reserva__in=reservas
        ).aggregate(
            unidades=Sum("cantidad"),
            ingresos=Sum(models.F("cantidad") * models.F("precio_unitario")),
        ),
    }

    return render(request, "gestion/reportes.html", contexto)




""""cliente views"""


def registro_cliente(request):
    if request.user.is_authenticated:
        return redirect("habitaciones_cliente")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")
        nombres = request.POST.get("nombres", "").strip()
        apellidos = request.POST.get("apellidos", "").strip()
        tipo_documento = request.POST.get("tipo_documento", "").strip()
        numero_documento = request.POST.get("numero_documento", "").strip()
        telefono = request.POST.get("telefono", "").strip()
        correo = request.POST.get("correo", "").strip()
        nacionalidad = request.POST.get("nacionalidad", "Colombiana").strip()

        if not all([
            username, password, nombres, apellidos,
            tipo_documento, numero_documento, telefono, correo
        ]):
            messages.error(request, "Completa todos los campos obligatorios.")

        elif password != password2:
            messages.error(request, "Las contraseñas no coinciden.")

        elif User.objects.filter(username=username).exists():
            messages.error(request, "Ese nombre de usuario ya existe.")

        elif Huesped.objects.filter(numero_documento=numero_documento).exists():
            messages.error(request, "Ese documento ya está registrado.")

        else:
            try:
                validate_password(password)
            except ValidationError as error:
                for mensaje in error.messages:
                    messages.error(request, mensaje)
            else:
                with transaction.atomic():
                    rol, _ = Rol.objects.get_or_create(
                        nombre="Cliente"
                    )

                    usuario = User.objects.create_user(
                        username=username,
                        password=password,
                        email=correo,
                        first_name=nombres,
                        last_name=apellidos,
                    )

                    PerfilUsuario.objects.create(
                        usuario=usuario,
                        rol=rol
                    )

                    Huesped.objects.create(
                        usuario=usuario,
                        nombres=nombres,
                        apellidos=apellidos,
                        tipo_documento=tipo_documento,
                        numero_documento=numero_documento,
                        telefono=telefono,
                        correo=correo,
                        nacionalidad=nacionalidad or "Colombiana",
                    )

                messages.success(
                    request,
                    "Cuenta creada correctamente. Ya puedes iniciar sesión."
                )
                return redirect("login_cliente")

    return render(request, "registro_cliente.html")



def login_cliente(request):
    siguiente = request.POST.get("next") or request.GET.get("next", "")
    if siguiente and not url_has_allowed_host_and_scheme(
        siguiente,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        siguiente = ""

    if request.user.is_authenticated:
        if hasattr(request.user, "perfil_huesped"):
            return redirect(siguiente or "habitaciones_cliente")
        return redirect("panel")

    if request.method == "POST":
        username = request.POST.get("usuario", "").strip()
        password = request.POST.get("contrasena", "")

        usuario = authenticate(
            request,
            username=username,
            password=password
        )

        if usuario is not None:
            if hasattr(usuario, "perfil_huesped"):
                login(request, usuario)
                return redirect(siguiente or "habitaciones_cliente")

            messages.error(
                request,
                "Esta cuenta no está registrada como cliente."
            )
        else:
            messages.error(
                request,
                "Usuario o contraseña incorrectos."
            )

    return render(request, "login_cliente.html", {"siguiente": siguiente})


def habitaciones_cliente(request):
    habitaciones = Habitacion.objects.select_related(
        "alojamiento", "tipo"
    ).exclude(estado="MANTENIMIENTO").order_by("precio")

    entrada = request.GET.get("entrada", "")
    salida = request.GET.get("salida", "")
    cantidad = request.GET.get("cantidad", "1")

    if entrada and salida:
        try:
            fecha_entrada = date.fromisoformat(entrada)
            fecha_salida = date.fromisoformat(salida)
            cantidad_personas = int(cantidad)

            if (
                fecha_entrada >= date.today()
                and fecha_salida > fecha_entrada
                and cantidad_personas > 0
            ):
                habitaciones = habitaciones.filter(
                    tipo__capacidad__gte=cantidad_personas
                )
                ocupadas = Reserva.objects.filter(
                    fecha_entrada__lt=fecha_salida,
                    fecha_salida__gt=fecha_entrada,
                    estado__in=["PENDIENTE", "CONFIRMADA", "EN_CURSO"],
                ).values_list("habitacion_id", flat=True)

                habitaciones = habitaciones.exclude(
                    id__in=ocupadas
                )
            else:
                messages.error(
                    request,
                    "Verifica las fechas y la cantidad de huéspedes."
                )
        except (ValueError, TypeError):
            messages.error(request, "Las fechas o la cantidad no son válidas.")

    alojamiento = Alojamiento.objects.prefetch_related(
        "servicios_disponibles"
    ).first()
    return render(request, "habitaciones_cliente.html", {
        "habitaciones": habitaciones,
        "alojamiento": alojamiento,
        "sitios_turisticos": (
            alojamiento.sitios_turisticos.splitlines()
            if alojamiento and alojamiento.sitios_turisticos
            else []
        ),
        "entrada": entrada,
        "salida": salida,
        "cantidad": cantidad,
        "fecha_minima": date.today().isoformat(),
        "hay_habitaciones_registradas": Habitacion.objects.exists(),
    })




@login_required(login_url="login_cliente")
def reserva_cliente(request):
    try:
        huesped = request.user.perfil_huesped
    except Huesped.DoesNotExist:
        messages.error(
            request,
            "Esta cuenta no tiene un perfil de huésped asociado. "
            "Ingresa con tu cuenta de cliente o regístrate."
        )
        return redirect("login_cliente")

    servicios_seleccionados = []

    if request.method == "POST":
        habitacion_id = request.POST.get("habitacion")
        entrada = request.POST.get("fecha_entrada", "")
        salida = request.POST.get("fecha_salida", "")
        cantidad = request.POST.get("cantidad_huespedes", "1")
        cantidad_ninos = request.POST.get("cantidad_ninos", "0")
        servicios_seleccionados = request.POST.getlist("servicios")

        try:
            if any(not s.isdigit() for s in servicios_seleccionados):
                raise ValueError("La selección de servicios no es válida.")

            servicios_ids = list(dict.fromkeys(servicios_seleccionados))

            fecha_entrada = date.fromisoformat(entrada)
            fecha_salida = date.fromisoformat(salida)

            cantidad_adultos = int(cantidad)
            cantidad_ninos = int(cantidad_ninos)
            total_personas = cantidad_adultos + cantidad_ninos

            if fecha_entrada < date.today():
                raise ValueError(
                    "La fecha de entrada no puede estar en el pasado."
                )

            if fecha_salida <= fecha_entrada:
                raise ValueError(
                    "La salida debe ser posterior a la entrada."
                )

            if cantidad_adultos < 1:
                raise ValueError("Debe registrarse al menos un adulto.")

            if cantidad_ninos < 0:
                raise ValueError("La cantidad de niños no es válida.")

            with transaction.atomic():
                Huesped.objects.select_for_update().get(pk=huesped.pk)
                reserva_cliente_existente = Reserva.objects.filter(
                    huesped=huesped,
                    fecha_entrada__lt=fecha_salida,
                    fecha_salida__gt=fecha_entrada,
                    estado__in=["PENDIENTE", "CONFIRMADA", "EN_CURSO"],
                ).exists()
                if reserva_cliente_existente:
                    raise ValueError(
                        "Ya tienes una reserva que coincide con esas fechas. "
                        "Elige otras fechas para evitar reservar dos estadías "
                        "al mismo tiempo."
                    )

                habitacion = get_object_or_404(
                    Habitacion.objects.select_for_update().select_related(
                        "tipo", "alojamiento"
                    ).exclude(estado="MANTENIMIENTO"),
                    pk=habitacion_id,
                )

                if total_personas > habitacion.tipo.capacidad:
                    raise ValueError(
                        "La habitación no tiene capacidad suficiente "
                        "para la cantidad de adultos y niños."
                    )

                conflicto = Reserva.objects.filter(
                    habitacion=habitacion,
                    fecha_entrada__lt=fecha_salida,
                    fecha_salida__gt=fecha_entrada,
                    estado__in=["PENDIENTE", "CONFIRMADA", "EN_CURSO"],
                ).exists()

                if conflicto:
                    raise ValueError(
                        "La habitación no está disponible para esas fechas."
                    )

                reserva = Reserva.objects.create(
                    usuario=request.user,
                    huesped=huesped,
                    habitacion=habitacion,
                    fecha_entrada=fecha_entrada,
                    fecha_salida=fecha_salida,
                    cantidad_huespedes=cantidad_adultos,
                    cantidad_ninos=cantidad_ninos,
                    estado="PENDIENTE",
                )

                servicios = list(
                    servicios_comida_reserva()
                    .select_for_update()
                    .filter(pk__in=servicios_ids)
                )

                if len(servicios) != len(servicios_ids):
                    raise ValueError(
                        "Uno o más servicios ya no están disponibles. "
                        "Actualiza la página e inténtalo de nuevo."
                    )

                ServicioReserva.objects.bulk_create([
                    ServicioReserva(
                        reserva=reserva,
                        servicio=servicio,
                        cantidad=1,
                        precio_unitario=servicio.precio,
                    )
                    for servicio in servicios
                ])

                sincronizar_estado_habitacion(habitacion.pk)

            messages.success(
                request,
                "Tu solicitud de reserva fue registrada."
            )
            return redirect("mis_reservas")

        except (ValueError, TypeError) as error:
            messages.error(request, str(error))

    habitaciones = Habitacion.objects.select_related(
        "tipo", "alojamiento"
    ).exclude(estado="MANTENIMIENTO")
    fecha_entrada_form = (
        request.POST.get("fecha_entrada", "")
        if request.method == "POST"
        else request.GET.get("fecha_entrada", "")
    )
    fecha_salida_form = (
        request.POST.get("fecha_salida", "")
        if request.method == "POST"
        else request.GET.get("fecha_salida", "")
    )
    cantidad_adultos_form = (
        request.POST.get("cantidad_huespedes", "1")
        if request.method == "POST"
        else request.GET.get("cantidad_huespedes", "1")
    )
    cantidad_ninos_form = (
        request.POST.get("cantidad_ninos", "0")
        if request.method == "POST"
        else request.GET.get("cantidad_ninos", "0")
    )
    habitacion_seleccionada = (
        request.POST.get("habitacion", "")
        if request.method == "POST"
        else request.GET.get("habitacion", "")
    )
    if fecha_entrada_form and fecha_salida_form:
        try:
            fecha_entrada_filtro = date.fromisoformat(fecha_entrada_form)
            fecha_salida_filtro = date.fromisoformat(fecha_salida_form)
        except ValueError:
            messages.error(request, "Las fechas no son válidas.")
        else:
            if fecha_salida_filtro <= fecha_entrada_filtro:
                messages.error(
                    request,
                    "La salida debe ser posterior a la entrada.",
                )
            else:
                habitaciones_ocupadas = Reserva.objects.filter(
                    fecha_entrada__lt=fecha_salida_filtro,
                    fecha_salida__gt=fecha_entrada_filtro,
                    estado__in=["PENDIENTE", "CONFIRMADA", "EN_CURSO"],
                ).values_list("habitacion_id", flat=True)
                habitaciones = habitaciones.exclude(
                    pk__in=habitaciones_ocupadas
                )

    servicios = servicios_comida_reserva().order_by("nombre")

    return render(request, "reserva_cliente.html", {
        "habitaciones": habitaciones,
        "servicios": servicios,
        "fecha_minima": date.today().isoformat(),
        "fecha_entrada": fecha_entrada_form,
        "fecha_salida": fecha_salida_form,
        "cantidad_huespedes": cantidad_adultos_form,
        "cantidad_ninos": cantidad_ninos_form,
        "habitacion_seleccionada": habitacion_seleccionada,
        "servicios_seleccionados": servicios_seleccionados,
    })





@login_required(login_url="login_cliente")
def mis_reservas(request):
    try:
        huesped = request.user.perfil_huesped
    except Huesped.DoesNotExist:
        messages.error(
            request,
            "Tu cuenta no tiene un perfil de huésped asociado. "
            "Regístrate como cliente o contacta con recepción."
        )
        return redirect("login_cliente")

    reservas = Reserva.objects.filter(
        huesped=huesped,
        estado__in=["PENDIENTE", "CONFIRMADA", "EN_CURSO"],
    ).select_related(
        "habitacion",
        "habitacion__tipo",
        "habitacion__alojamiento"
    ).prefetch_related(
        "servicios",
        "servicios__servicio",
        "consumos",
        "consumos__servicio",
    ).order_by("-fecha_registro")

    return render(request, "mis_reservas.html", {
        "reservas": reservas,
    })


@login_required(login_url="login_cliente")
def historial_reservas(request):
    huesped = getattr(request.user, "perfil_huesped", None)
    if not huesped:
        return redirect("login_cliente")
    reservas = Reserva.objects.filter(huesped=huesped).filter(
        models.Q(estado__in=["CANCELADA", "FINALIZADA"])
        | models.Q(fecha_salida__lt=date.today())
    ).select_related(
        "habitacion", "habitacion__tipo"
    ).prefetch_related(
        "consumos", "consumos__servicio"
    ).order_by("-fecha_registro")
    return render(request, "historial_reservas.html", {
        "reservas": reservas,
    })


@login_required(login_url="login_cliente")
@require_POST
def solicitar_cancelacion(request, reserva_id):
    huesped = getattr(request.user, "perfil_huesped", None)
    if not huesped:
        return redirect("login_cliente")

    reserva = get_object_or_404(
        Reserva,
        pk=reserva_id,
        huesped=huesped,
    )

    motivo = request.POST.get("motivo", "").strip()

    if reserva.estado not in ["PENDIENTE", "CONFIRMADA"]:
        messages.error(
            request,
            "Esta reserva no admite solicitudes de cancelación."
        )
    elif not motivo:
        messages.error(request, "Debes indicar el motivo de la cancelación.")
    elif reserva.solicitudes_cancelacion.filter(
        estado="PENDIENTE"
    ).exists():
        messages.info(
            request,
            "Ya tienes una solicitud de cancelación pendiente."
        )
    else:
        SolicitudCancelacion.objects.create(
            reserva=reserva,
            motivo=motivo,
        )
        messages.success(
            request,
            "Tu solicitud de cancelación fue enviada para revisión."
        )

    return redirect("mis_reservas")
