# Distribuidora Montoya — Sistema de control interno

Aplicación web local para controlar el inventario, las compras a Postobón, las rutas del
camión de reparto y el crédito por descuento de Distribuidora Montoya.

## Para el dueño (uso diario)

### Primera vez (una sola vez)
1. Doble clic en **`instalar.bat`**.
2. Espera a que termine (instala lo necesario y prepara la base de datos). Presiona una
   tecla cuando lo pida para cerrar la ventana.

### Cada vez que quieras usar el sistema
1. Doble clic en **`iniciar.bat`**.
2. Se abrirá automáticamente en tu navegador (Chrome, Edge, etc.).
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
  te entrega producto a cambio de ese crédito.
- **Reportes**: elige un mes y revisa los totales de compra, venta, crédito y saldo.

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
  cambio del crédito). Ver `services/descuentos.py`.
- Los precios de producto tienen historial (`producto_precio`): editar el precio de un
  producto no sobrescribe el anterior, inserta una fila nueva con la fecha desde la que
  aplica. Los reportes usan el precio vigente en la fecha de cada transacción, no el
  precio de hoy.

### Comandos útiles
```
venv\Scripts\activate
pytest tests\          # corre todas las pruebas
python app.py           # levanta el servidor manualmente
flask --app app init-db # recrea las tablas si hace falta
```

### Fórmulas de reportes
```
compra_total(periodo)     = SUM(costo_linea) de las compras del período
credito_generado(periodo) = SUM(costo_linea * tasa_descuento_aplicada / 100)
credito_canjeado(periodo) = SUM(valor_usado) de los canjes del período
saldo_acumulado(fecha)    = credito_generado_total_hasta(fecha) - credito_canjeado_total_hasta(fecha)
venta_total(periodo)      = SUM((salida - retorno) * precio vigente en la fecha del retorno)
                             de las rutas cerradas cuyo retorno cae en el período
```

### Limitaciones conocidas (v1)
- No distingue mermas/producto dañado de ventas reales (todo lo que no regresa en el
  camión se cuenta como vendido).
- No maneja cartera/ventas a crédito de los clientes de la distribuidora.
- No hay pantalla de ajuste manual de inventario (para cuadrar un conteo físico).

Todas declaradas en el plan original; se pueden agregar después si el uso real lo pide.
