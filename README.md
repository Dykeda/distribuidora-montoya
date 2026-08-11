# Distribuidora Montoya — Sistema de control interno

Aplicación web para controlar el inventario, las compras a Postobón, las rutas del
camión de reparto y el crédito por descuento de Distribuidora Montoya. Se puede entregar
de tres formas: como un único `.exe` que no necesita tener Python instalado (la más
simple para enviarle al dueño), corriendo localmente con Python instalado (`instalar.bat`
/ `iniciar.bat`), o publicada en línea para acceder desde cualquier lugar (ver
`DEPLOY.md`).

Desde que se puede usar en línea, **todo el sistema pide contraseña** antes de mostrar
cualquier pantalla (antes no la pedía, porque solo corría en un computador de confianza).
Si la estás usando en línea, avísale al dueño cuál es esa contraseña.

## Para el dueño — opción más simple: el .exe

Si recibiste un archivo `DistribuidoraMontoya.exe`, no necesitas instalar nada:
1. Ponlo en cualquier carpeta de tu computador (por ejemplo, el Escritorio).
2. Doble clic. La primera vez, Windows puede mostrar una advertencia azul ("Windows
   protegió su PC") porque el programa no tiene firma digital — es normal, dale clic en
   **"Más información"** y luego **"Ejecutar de todas formas"**.
3. Se abre solo en tu navegador y pide la contraseña: `montoya2026` (a menos que te hayan
   dado una distinta).
4. **No cierres la ventana negra** mientras lo uses. Ciérrala cuando termines.
5. Todos tus datos quedan guardados en una carpeta `instance` que aparece junto al .exe —
   no la borres ni la muevas por separado del programa.

## Para el dueño (uso diario, si corre localmente con Python instalado)

### Primera vez (una sola vez)
1. Doble clic en **`instalar.bat`**.
2. Espera a que termine (instala lo necesario y prepara la base de datos). Presiona una
   tecla cuando lo pida para cerrar la ventana.

### Cada vez que quieras usar el sistema
1. Doble clic en **`iniciar.bat`**.
2. Se abrirá automáticamente en tu navegador (Chrome, Edge, etc.) y pedirá la contraseña
   (por defecto `montoya2026` si nadie la cambió — ver nota de seguridad abajo).
3. **No cierres la ventana negra** que se abre mientras estés usando el sistema — es la
   que mantiene el programa funcionando. Cuando termines, cierra esa ventana.

### Respaldo de la información (recomendado hacerlo seguido)
Doble clic en **`respaldar.bat`**. Guarda una copia de toda la información del negocio con
la fecha y hora en el nombre. Si el computador tiene OneDrive, el respaldo queda ahí y se
sube solo a la nube — así no se pierde nada aunque el computador falle.

### Qué hace cada pantalla
- **Inicio**: resumen del mes — cuánto se compró, cuánto se vendió, cuánto crédito de
  descuento se ganó, y cuánto saldo tienes disponible para canjear por producto.
- **Inventario**: cuánto hay en bodega de cada producto, ahora mismo.
- **Productos**: da de alta o edita las referencias que manejas (nombre, precio, si se
  maneja por caja o por unidad). El precio se ingresa **por caja completa** (así se
  piensa el negocio), y el sistema lo guarda internamente por unidad para calcular
  ventas e inventario — la lista de Productos también muestra el precio por caja, no por
  unidad. Si tienes muchos productos para cargar de una vez, usa el botón "Carga masiva".
  El campo "Descuento de referencia" es opcional — si lo llenas, ese % viene precargado
  automáticamente al elegir ese producto en una compra (lo puedes cambiar ahí mismo si
  ese mes el descuento fue distinto).
- **Compras**: registra cada compra que le haces a Postobón, incluyendo el % de
  descuento que te dieron ese mes en cada producto.
- **Camión**: registra qué carga el camión al salir a reparto, y cuánto regresa al
  volver. Con eso el sistema calcula solo cuánto se vendió — no hay que registrar la
  venta a mano. Si al camión se le acaba algo en plena ruta, usa "Recargar camión" para
  mandarle más producto sin cerrar la ruta — se suma a lo cargado de ese día. El
  historial se puede filtrar por mes/año, igual que Caja y Reportes.
- **Venta Bodega**: para cuando alguien compra directo en la bodega, sin pasar por el
  camión. Descuenta el inventario igual que una entrega, y se suma a la venta del día.
- **Venta Diaria**: historial día por día de todo lo vendido (camión + bodega), con
  filtro de mes/año y un detalle por fecha que muestra cada ruta cerrada y cada venta de
  bodega de ese día, producto por producto. A diferencia de Caja, aquí se ve la venta
  **bruta** tal como se vendió — no resta lo que quedó en cartera sin cobrar ni las
  salidas de dinero.
- **Descuentos**: aquí ves cuánto crédito tienes acumulado, y registras cuando Postobón
  te entrega producto a cambio de ese crédito. El botón "Ajustar saldo" sirve para cargar
  el crédito que ya tenías acumulado antes de empezar a usar el sistema (o para corregir
  el saldo si algo quedó mal).
- **Cartera**: registra las facturas que los clientes te deben, y márcalas como pagadas
  cuando te paguen. Si la deuda es de una ruta del camión ya registrada, elígela en el
  formulario; si es una deuda de antes de usar el sistema, deja esa parte en blanco. Aquí
  también ves cuánto dinero tienes pendiente por cobrar en total, agrupado por
  antigüedad (0-15, 16-30, 31-60 y más de 60 días) y con los días pendientes de cada
  factura, para que sea fácil ver qué deudas llevan más tiempo sin cobrarse.
- **Caja**: el saldo de efectivo día a día — se calcula solo (venta del camión menos lo
  que quedó en cartera sin cobrar, más venta directa en bodega, menos las salidas de
  dinero), no hay que registrar entradas aparte.
- **Salidas de dinero**: registra pagos del negocio (a Postobón, otros distribuidores,
  nómina) y gastos del hogar (arriendo, servicios, etc.). Si no está la categoría que
  necesitas, la creas con el botón "+ Nueva categoría" — quedan disponibles para la
  próxima vez. Aquí ves siempre el registro completo de todas las salidas, con pestañas
  para filtrar por Negocio o Hogar. Se descuentan automáticamente de Caja.
- **Reportes**: elige un mes y revisa los totales de compra, venta, crédito, saldo,
  cartera pendiente, entradas/salidas de caja y saldo de caja. Incluye una tabla de
  "Rendimiento por producto" — qué productos generaron más crédito de descuento ese mes,
  de mayor a menor, independiente de cuánto se vendió de cada uno (como la ganancia real
  es el crédito y no un margen de venta, esto ayuda a decidir qué productos conviene
  empujar más).

## Para quien mantenga el código (referencia técnica)

- Stack: Python + Flask + SQLite + SQLAlchemy, sin build de frontend (Jinja2 + Bootstrap
  por CDN).
- `services/` contiene toda la lógica de negocio (cálculo de stock, ventas implícitas,
  crédito por descuento, reportes), separada de las rutas HTTP en `routes/`. Está cubierta
  por pruebas unitarias en `tests/`.
- El stock de bodega y las ventas **no se guardan** como campos — se calculan a partir de
  los movimientos (compras, salidas, recargas, retornos, canjes, ventas en bodega). Ver
  `services/inventario.py` y `services/ventas.py`.
- `RecargaCamion`/`RecargaCamionDetalle`: producto extra que se le manda a una ruta que
  sigue en tránsito (no tiene retorno todavía). `services.ventas.cargado_por_producto()`
  suma la salida inicial más todas las recargas del día para saber cuánto se vendió al
  cerrar la ruta — por eso el formulario de retorno muestra "cargado (salida + recargas)"
  en vez de solo lo que salió al principio.
- `VentaBodega`/`VentaBodegaDetalle`: venta directa en bodega, sin pasar por el camión.
  Se valoriza igual que un canje (cantidad × precio vigente en la fecha), descuenta stock,
  y se suma a `ventas_en_periodo()` junto con la venta implícita de las rutas cerradas.
- El "crédito por descuento": cada línea de compra guarda su propia
  `tasa_descuento_aplicada` (%), porque puede variar por producto y por mes. El crédito
  generado = costo de la línea × tasa. Se acumula indefinidamente (no se resetea cada
  mes) y se reduce cuando se registra un "canje" (el dueño elige qué producto recibe a
  cambio del crédito). `AjusteCredito` permite sumar o restar manualmente al saldo (ej.
  crédito acumulado antes de usar el sistema, monto positivo; corrección de un error,
  monto negativo). Ver `services/descuentos.py`.
- `services/descuentos.py::rendimiento_por_producto()`: agrupa `CompraDetalle` por
  producto dentro del período y calcula el crédito generado de cada uno, ordenado de
  mayor a menor — deliberadamente independiente de `ventas_en_periodo()` (cuánto se
  vendió), porque en este negocio un producto puede venderse mucho y dejar poco crédito,
  o venderse poco y ser el más rentable, según la tasa de descuento que le dio Postobón
  ese mes.
- Los precios de producto tienen historial (`producto_precio`): editar el precio de un
  producto no sobrescribe el anterior, inserta una fila nueva con la fecha desde la que
  aplica. Los reportes usan el precio vigente en la fecha de cada transacción, no el
  precio de hoy. Si dos precios quedan con la misma fecha (ej. dos ediciones el mismo
  día), `Producto.precio_vigente()` desempata por el id más alto (el más reciente), no
  por el primero encontrado.
- El precio se **captura y se muestra por caja completa** en las pantallas de Productos.
  `ProductoPrecio` guarda **los dos valores por separado**: `precio_venta_caja` (el
  número exacto que se escribió, sin tocar — es lo que Productos siempre muestra) y
  `precio_venta_unidad` (ese mismo precio ÷ unidades por caja, redondeado — el que usa
  el resto del sistema para calcular ventas, canjes, etc. en unidades sueltas). Guardarlos
  aparte evita que el redondeo del precio por unidad se note al mostrar el precio de caja
  (antes de esto, reconstruir el precio de caja multiplicando de vuelta el precio por
  unidad producía diferencias de unos pesos, ej. $51,800 → $51,810 mostrado — ya no pasa).
- La cartera de clientes (`factura_cartera`) es independiente del cálculo de venta/stock
  — es solo un registro de "este cliente debe tanto dinero", que no afecta el inventario
  ni las fórmulas de ganancia. `salida_id` es opcional: si la deuda viene de una ruta
  registrada en el sistema se liga a esa `salida_camion` (aparece en el detalle de esa
  ruta); si es una deuda de antes de usar el sistema, se deja en blanco. Ver
  `services/cartera.py`.
- Antigüedad de cartera (`services/cartera.py::facturas_con_antiguedad()` y
  `resumen_antiguedad()`): los días pendientes de una factura se calculan al vuelo
  (`fecha_referencia - factura.fecha`, hoy por defecto), no se guardan — no hay campo de
  "días" ni de "fecha de vencimiento" en el modelo. `resumen_antiguedad()` agrupa el
  dinero pendiente en 4 rangos fijos (`RANGOS_ANTIGUEDAD`: 0-15, 16-30, 31-60, 60+ días);
  las facturas pagadas no cuentan en ningún rango.
- Caja (`services/caja.py`): las **entradas** se derivan de datos que ya existen (no
  tienen tabla propia) — `efectivo_por_salida()` = venta implícita de la ruta menos las
  facturas de cartera ligadas a esa `salida_camion` (lo que no se cobró en efectivo), más
  la venta directa en bodega (`VentaBodega`, siempre en efectivo). Las **salidas** sí
  tienen tabla propia: `Gasto` (categoría, fecha, monto, notas), donde la categoría es
  `CategoriaGasto` con un `tipo` ("negocio" o "hogar") — el usuario puede agregar más
  categorías desde la pantalla, además de las 8 que vienen por defecto
  (`services/gastos.py::CATEGORIAS_DEFAULT`, sembradas al iniciar la app vía
  `asegurar_categorias_default()`, idempotente). `saldo_acumulado()` = todas las entradas
  menos todas las salidas hasta una fecha de corte.
- Venta Diaria (`services/ventas.py::historial_diario()` y `detalle_dia()`, rutas en
  `routes/venta_diaria.py`): día por día, venta de camión (rutas cuyo *retorno* cae en
  la fecha) + venta de bodega (cuya fecha cae en la fecha), **sin restar cartera ni
  gastos** — a propósito, es venta bruta, no efectivo neto. Ojo: este `historial_diario()`
  vive en `services/ventas.py` y es una función distinta de
  `services/caja.py::historial_diario()` (que sí resta cartera y gastos para mostrar el
  efectivo neto del día) — mismo nombre, dos módulos, propósitos distintos; no son
  duplicados a fusionar. El historial de Camión (`routes/camion.py::listar()`) usa el
  mismo patrón de filtro mes/año que Caja y Venta Diaria.

### Comandos útiles
```
venv\Scripts\activate
pytest tests\          # corre todas las pruebas
python app.py           # levanta el servidor manualmente
flask --app app init-db # recrea las tablas si hace falta
```

### Reconstruir el .exe
`config.py` y `app.py` detectan si corren "congelados" (`sys.frozen`, lo pone
PyInstaller) para separar los recursos empaquetados (templates/static, de solo lectura)
de los datos que deben persistir junto al .exe real (`instance/distribuidora.db`). Para
generar un .exe nuevo después de cambios en el código:
```
venv\Scripts\pip install pyinstaller
venv\Scripts\python -m PyInstaller --onefile --console --name DistribuidoraMontoya --add-data "templates;templates" --add-data "static;static" app.py
```
El resultado queda en `dist\DistribuidoraMontoya.exe`. `build/`, `dist/` y `*.spec` están
en `.gitignore` — no se versionan, se regeneran cuando hagan falta.

### Contraseña y despliegue en línea
- La app exige login en todas partes (`app.py`, función `exigir_login`). La contraseña
  vive en `Config.APP_PASSWORD`, leída de la variable de entorno `APP_PASSWORD` (con
  `montoya2026` como valor por defecto SOLO para uso local). Lo mismo con `SECRET_KEY`
  (firma las cookies de sesión).
- **Si se despliega en línea, hay que fijar `APP_PASSWORD` y `SECRET_KEY` propios como
  variables de entorno — nunca dejar los valores por defecto expuestos a internet.**
  Guía completa de despliegue (PythonAnywhere + GitHub) en `DEPLOY.md`.

### Fórmulas de reportes
```
compra_total(periodo)     = SUM(costo_linea) de las compras del período
credito_generado(periodo) = SUM(costo_linea * tasa_descuento_aplicada / 100)
credito_canjeado(periodo) = SUM(valor_usado) de los canjes del período
saldo_acumulado(fecha)    = credito_generado_total_hasta(fecha) + ajustes_total_hasta(fecha)
                             - credito_canjeado_total_hasta(fecha)
venta_total(periodo)      = SUM((salida - retorno) * precio vigente en la fecha del retorno)
                             de las rutas cerradas cuyo retorno cae en el período
cartera_pendiente(fecha)  = SUM(monto) de facturas con fecha <= fecha, y que en esa fecha
                             seguían sin pagar (estado pendiente, o se pagaron después)
pct_descuento_promedio    = credito_generado(periodo) / compra_total_dinero(periodo) * 100
                             (ponderado por dinero comprado, no un promedio simple de las
                             tasas ingresadas en cada línea)
efectivo_por_salida        = venta_por_salida(ruta) - SUM(monto) de las facturas de cartera
                             ligadas a esa misma salida_camion
entradas(periodo)          = SUM(efectivo_por_salida) de rutas cerradas en el período
                             + venta directa en bodega del período (siempre en efectivo)
gastos(periodo)            = SUM(monto) de Gasto con fecha dentro del período
saldo_caja(periodo)        = entradas(periodo) - gastos(periodo)
saldo_caja_acumulado(fecha) = entradas(sin límite inferior, hasta fecha)
                             - gastos(sin límite inferior, hasta fecha)
```

### Limitaciones conocidas (v1)
- No distingue mermas/producto dañado de ventas reales (todo lo que no regresa en el
  camión se cuenta como vendido).
- No hay pantalla de ajuste manual de inventario (para cuadrar un conteo físico).
- La cartera no valida el monto de la factura contra la venta calculada de la ruta — el
  dueño lo ingresa libremente, no hay una regla que los cruce automáticamente.

Todas declaradas en el plan original; se pueden agregar después si el uso real lo pide.
