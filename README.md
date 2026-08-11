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
  maneja por caja o por unidad). Si tienes muchos productos para cargar de una vez, usa
  el botón "Carga masiva".
- **Compras**: registra cada compra que le haces a Postobón, incluyendo el % de
  descuento que te dieron ese mes en cada producto.
- **Camión**: registra qué carga el camión al salir a reparto, y cuánto regresa al
  volver. Con eso el sistema calcula solo cuánto se vendió — no hay que registrar la
  venta a mano.
- **Descuentos**: aquí ves cuánto crédito tienes acumulado, y registras cuando Postobón
  te entrega producto a cambio de ese crédito. El botón "Ajustar saldo" sirve para cargar
  el crédito que ya tenías acumulado antes de empezar a usar el sistema (o para corregir
  el saldo si algo quedó mal).
- **Cartera**: registra las facturas que los clientes te deben (ligadas a la ruta del
  camión en la que se generaron), y márcalas como pagadas cuando te paguen. Aquí también
  ves cuánto dinero tienes pendiente por cobrar en total.
- **Reportes**: elige un mes y revisa los totales de compra, venta, crédito, saldo y
  cartera pendiente.

## Para quien mantenga el código (referencia técnica)

- Stack: Python + Flask + SQLite + SQLAlchemy, sin build de frontend (Jinja2 + Bootstrap
  por CDN).
- `services/` contiene toda la lógica de negocio (cálculo de stock, ventas implícitas,
  crédito por descuento, reportes), separada de las rutas HTTP en `routes/`. Está cubierta
  por pruebas unitarias en `tests/`.
- El stock de bodega y las ventas **no se guardan** como campos — se calculan a partir de
  los movimientos (compras, salidas, retornos, canjes). Ver `services/inventario.py` y
  `services/ventas.py`.
- El "crédito por descuento": cada línea de compra guarda su propia
  `tasa_descuento_aplicada` (%), porque puede variar por producto y por mes. El crédito
  generado = costo de la línea × tasa. Se acumula indefinidamente (no se resetea cada
  mes) y se reduce cuando se registra un "canje" (el dueño elige qué producto recibe a
  cambio del crédito). `AjusteCredito` permite sumar o restar manualmente al saldo (ej.
  crédito acumulado antes de usar el sistema, monto positivo; corrección de un error,
  monto negativo). Ver `services/descuentos.py`.
- Los precios de producto tienen historial (`producto_precio`): editar el precio de un
  producto no sobrescribe el anterior, inserta una fila nueva con la fecha desde la que
  aplica. Los reportes usan el precio vigente en la fecha de cada transacción, no el
  precio de hoy.
- La cartera de clientes (`factura_cartera`) es independiente del cálculo de venta/stock
  — es solo un registro de "este cliente debe tanto dinero de esta ruta", que no afecta
  el inventario ni las fórmulas de ganancia. Cada factura queda ligada a una
  `salida_camion`. Ver `services/cartera.py`.

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
```

### Limitaciones conocidas (v1)
- No distingue mermas/producto dañado de ventas reales (todo lo que no regresa en el
  camión se cuenta como vendido).
- No hay pantalla de ajuste manual de inventario (para cuadrar un conteo físico).
- La cartera no valida el monto de la factura contra la venta calculada de la ruta — el
  dueño lo ingresa libremente, no hay una regla que los cruce automáticamente.

Todas declaradas en el plan original; se pueden agregar después si el uso real lo pide.
