# Manual de usuario — SysHSENA

## Acceso inicial

1. El administrador técnico ejecuta `python manage.py createsuperuser`.
2. Inicia sesión en `/login/`.
3. En **Usuarios**, crea cuentas y asigna uno de los roles disponibles.
4. En **Configuración del hotel**, registra la información del alojamiento,
   municipio, fotografía del equipo (archivo), servicios disponibles y sitios turísticos.
5. Registra tipos de habitación y habitaciones; puedes subir una foto local
   para cada una antes de publicar disponibilidad. Las imágenes de muestra se
   encuentran en `gestion/static/img`.

## Inventario de demostración

Para completar el Hotel Taroa con 200 habitaciones de muestra, ejecuta:

```powershell
.\.venv\Scripts\python.exe manage.py cargar_habitaciones_demo --actualizar-existentes
```

El comando conserva las reservas y sus tarifas históricas, crea los tipos de
habitación necesarios y asigna una fotografía local a cada habitación. Las
tarifas generadas son valores de demostración en COP, diferenciados por tipo y
piso; ajústalas a los precios reales del establecimiento antes de operar.

## Administrador

Puede administrar usuarios y roles, habitaciones, tipos, catálogo de servicios,
huéspedes, reservas, pagos y datos del alojamiento. Desde el panel puede revisar
habitaciones disponibles y ocupadas, reservas del día, ingresos y ocupación.
También puede consultar llegadas de hoy y próximas, con el estado de cada reserva,
y revisar el aviso de solicitudes pendientes de confirmación.

## Recepcionista

Al iniciar sesión verá el **Panel de recepción** con entradas y salidas del día,
huéspedes alojados, reservas pendientes y habitaciones disponibles. Desde sus
accesos rápidos puede crear reservas, registrar huéspedes y recibir pagos.
El panel destaca las reservas pendientes con el huésped, fecha de entrada y
habitación, y muestra las llegadas de hoy y próximas.
Puede consultar el catálogo de servicios, pero no crear ni modificar servicios.
También puede confirmar reservas, agregar servicios y ejecutar check-in/check-out.
El check-in solo se admite para reservas confirmadas; el check-out requiere un
check-in previo. Al solicitar o confirmar una reserva, la habitación se bloquea
como ocupada para evitar otra reserva; al cancelar o finalizar la estadía, queda
disponible. No tiene acceso a la administración de usuarios, roles, habitaciones
ni a la configuración del hotel.

## Restaurante, bar y lavandería

El administrador crea una cuenta de usuario para cada área desde **Usuarios**,
asignándole el rol correspondiente. Antes, registra los productos y servicios
desde **Servicios**, seleccionando si pertenecen al restaurante, al bar o a la
lavandería y configurando su precio. Al iniciar sesión, cada empleado solo puede
consultar y añadir servicios de su propia área; no puede crear servicios para
otra área ni editar o eliminar los existentes. También puede seleccionar
consumos de su área y cargarlos a una habitación con huésped alojado. Al
registrarlos, selecciona el método y el sistema cobra el valor exacto del
consumo, vinculando el pago y quién lo recibió a la reserva. Recepción puede
ver esos pagos en la factura y en el listado de pagos, junto con el usuario que
los registró, y confirmar el saldo restante al hacer el check-out.

Para cargar un catálogo inicial de platos, bebidas y servicios de lavandería,
ejecuta `python manage.py cargar_catalogo_servicios_demo`. Los precios incluidos
son valores de demostración en COP y el comando no duplica los artículos al
ejecutarlo de nuevo.

## Gerente

Al iniciar sesión verá el **Panel de gerencia** con ocupación actual, reservas
activas, entradas del día, huéspedes, ingresos acumulados e ingresos del mes.
También puede revisar las próximas entradas y abrir las consultas de reservas,
pagos y reportes. Su acceso es de solo lectura: no puede crear usuarios,
habitaciones, servicios, reservas ni pagos, ni realizar check-in/check-out.
El panel incluye el aviso de reservas pendientes y la agenda de llegadas para
consultar quién llega hoy y en los próximos días. Puede consultar el catálogo
de servicios, pero no añadirlos ni modificarlos.

## Cliente

Se registra desde **Crear cuenta**, inicia sesión en `/cliente/login/`, consulta
disponibilidad por fechas y capacidad, crea solicitudes de reserva y consulta sus
reservas e historial. Puede enviar una solicitud de cancelación; recepción debe
aprobarla para cancelar la reserva. Las habitaciones no desaparecen del catálogo
por tener una reserva en otras fechas: al buscar disponibilidad, solo se ocultan
las que tienen una reserva que se cruza con el periodo seleccionado. Un mismo
cliente no puede tener dos reservas activas que coincidan en fechas, aunque sean
de habitaciones diferentes; sí puede reservar periodos separados o contiguos.

## Pagos y servicios

Los pagos aceptan abonos y no pueden superar el saldo pendiente. El total de una
reserva incluye el alojamiento por noche, los servicios asociados y los cargos
registrados por restaurante, bar y lavandería. Después del check-out, recepción
puede consultar e imprimir la factura detallada, registrar el pago del saldo y
ver el total pagado. Los reportes también contabilizan los consumos cargados.

## Reportes

El gerente y el administrador pueden filtrar reservas e ingresos por periodo,
estado, habitación y huésped. El reporte presenta ocupación, pagos, saldos,
historial de reservas por huésped y servicios vendidos.
