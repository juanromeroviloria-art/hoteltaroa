from django.contrib.auth.decorators import user_passes_test

from .models import Usuario as PerfilUsuario


def usuario_tiene_rol(usuario, *roles):
    if not usuario.is_authenticated:
        return False
    if usuario.is_superuser:
        return True
    return PerfilUsuario.objects.filter(
        usuario=usuario,
        rol__nombre__in=roles,
    ).exists()


def requiere_roles(*roles):
    return user_passes_test(
        lambda usuario: usuario_tiene_rol(usuario, *roles),
        login_url="login",
    )
