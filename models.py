from datetime import date

from extensions import db


class Producto(db.Model):
    __tablename__ = "producto"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    categoria = db.Column(db.String(60), nullable=True)
    unidades_por_caja = db.Column(db.Integer, nullable=False, default=1)
    maneja_cajas = db.Column(db.Boolean, nullable=False, default=True)
    maneja_unidades = db.Column(db.Boolean, nullable=False, default=True)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    # % de descuento típico de este producto, solo para autocompletar el formulario de
    # compra — la tasa real se puede variar en cada compra, esto es un punto de partida.
    tasa_descuento_referencia = db.Column(db.Float, nullable=False, default=0.0)

    precios = db.relationship(
        "ProductoPrecio",
        back_populates="producto",
        order_by="ProductoPrecio.vigente_desde",
        cascade="all, delete-orphan",
    )

    def _fila_precio_vigente(self, fecha: date):
        """Fila de ProductoPrecio vigente en una fecha (la más reciente <= fecha). Si dos
        precios quedan con la misma fecha (ej. dos ediciones el mismo día), gana el que se
        creó después (id más alto), no el primero encontrado."""
        vigente = None
        for p in self.precios:
            if p.vigente_desde <= fecha:
                if vigente is None or (p.vigente_desde, p.id) > (vigente.vigente_desde, vigente.id):
                    vigente = p
        return vigente

    def precio_vigente(self, fecha: date):
        """Precio de venta por UNIDAD efectivo en una fecha — el que usa el resto del
        sistema (ventas, canjes) para calcular dinero. Puede tener un pequeño redondeo
        respecto al precio de caja ingresado si la caja no se divide exacto."""
        fila = self._fila_precio_vigente(fecha)
        return fila.precio_venta_unidad if fila else None

    def precio_caja_vigente(self, fecha: date):
        """Precio de venta por CAJA tal como se ingresó, efectivo en una fecha — el que se
        muestra en Productos, sin el redondeo del precio por unidad."""
        fila = self._fila_precio_vigente(fecha)
        return fila.precio_venta_caja if fila else None

    def precio_actual(self):
        return self.precio_vigente(date.today())

    def precio_caja_actual(self):
        return self.precio_caja_vigente(date.today())


class ProductoPrecio(db.Model):
    __tablename__ = "producto_precio"

    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey("producto.id"), nullable=False)
    # precio_venta_unidad es el que usan los cálculos internos (redondeado, por unidad
    # suelta). precio_venta_caja es exactamente lo que el usuario escribió — se guarda
    # aparte para que Productos siempre muestre el número exacto que se ingresó, sin
    # arrastrar el redondeo del precio por unidad.
    precio_venta_unidad = db.Column(db.Integer, nullable=False)
    precio_venta_caja = db.Column(db.Integer, nullable=False)
    vigente_desde = db.Column(db.Date, nullable=False, default=date.today)

    producto = db.relationship("Producto", back_populates="precios")


class Compra(db.Model):
    __tablename__ = "compra"

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False, default=date.today)
    numero_factura = db.Column(db.String(60), nullable=True)
    notas = db.Column(db.String(255), nullable=True)

    detalles = db.relationship(
        "CompraDetalle", back_populates="compra", cascade="all, delete-orphan"
    )


class CompraDetalle(db.Model):
    __tablename__ = "compra_detalle"

    id = db.Column(db.Integer, primary_key=True)
    compra_id = db.Column(db.Integer, db.ForeignKey("compra.id"), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey("producto.id"), nullable=False)
    cantidad_comprada_unidades = db.Column(db.Integer, nullable=False)
    costo_linea = db.Column(db.Integer, nullable=False)
    tasa_descuento_aplicada = db.Column(db.Float, nullable=False, default=0.0)

    compra = db.relationship("Compra", back_populates="detalles")
    producto = db.relationship("Producto")

    @property
    def credito_generado(self):
        return round(self.costo_linea * (self.tasa_descuento_aplicada / 100.0))


class SalidaCamion(db.Model):
    __tablename__ = "salida_camion"

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False, default=date.today)
    notas = db.Column(db.String(255), nullable=True)

    detalles = db.relationship(
        "SalidaCamionDetalle", back_populates="salida", cascade="all, delete-orphan"
    )
    retorno = db.relationship(
        "RetornoCamion", back_populates="salida", uselist=False, cascade="all, delete-orphan"
    )
    facturas = db.relationship(
        "FacturaCartera", back_populates="salida", cascade="all, delete-orphan"
    )
    recargas = db.relationship(
        "RecargaCamion", back_populates="salida", cascade="all, delete-orphan"
    )


class SalidaCamionDetalle(db.Model):
    __tablename__ = "salida_camion_detalle"

    id = db.Column(db.Integer, primary_key=True)
    salida_id = db.Column(db.Integer, db.ForeignKey("salida_camion.id"), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey("producto.id"), nullable=False)
    cantidad_unidades = db.Column(db.Integer, nullable=False)

    salida = db.relationship("SalidaCamion", back_populates="detalles")
    producto = db.relationship("Producto")


class RetornoCamion(db.Model):
    __tablename__ = "retorno_camion"

    id = db.Column(db.Integer, primary_key=True)
    salida_id = db.Column(
        db.Integer, db.ForeignKey("salida_camion.id"), nullable=False, unique=True
    )
    fecha = db.Column(db.Date, nullable=False, default=date.today)
    notas = db.Column(db.String(255), nullable=True)

    salida = db.relationship("SalidaCamion", back_populates="retorno")
    detalles = db.relationship(
        "RetornoCamionDetalle", back_populates="retorno", cascade="all, delete-orphan"
    )


class RetornoCamionDetalle(db.Model):
    __tablename__ = "retorno_camion_detalle"

    id = db.Column(db.Integer, primary_key=True)
    retorno_id = db.Column(db.Integer, db.ForeignKey("retorno_camion.id"), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey("producto.id"), nullable=False)
    cantidad_unidades = db.Column(db.Integer, nullable=False)

    retorno = db.relationship("RetornoCamion", back_populates="detalles")
    producto = db.relationship("Producto")


class CanjeDescuento(db.Model):
    __tablename__ = "canje_descuento"

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False, default=date.today)
    notas = db.Column(db.String(255), nullable=True)

    detalles = db.relationship(
        "CanjeDescuentoDetalle", back_populates="canje", cascade="all, delete-orphan"
    )


class CanjeDescuentoDetalle(db.Model):
    __tablename__ = "canje_descuento_detalle"

    id = db.Column(db.Integer, primary_key=True)
    canje_id = db.Column(db.Integer, db.ForeignKey("canje_descuento.id"), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey("producto.id"), nullable=False)
    cantidad_unidades = db.Column(db.Integer, nullable=False)
    valor_usado = db.Column(db.Integer, nullable=False)

    canje = db.relationship("CanjeDescuento", back_populates="detalles")
    producto = db.relationship("Producto")


class Cliente(db.Model):
    """Catálogo de clientes, para no tener que reescribir el nombre en cada factura de
    cartera y poder ver de un vistazo todas las facturas de un mismo cliente."""

    __tablename__ = "cliente"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False, unique=True)
    notas = db.Column(db.String(255), nullable=True)
    activo = db.Column(db.Boolean, nullable=False, default=True)

    facturas = db.relationship("FacturaCartera", back_populates="cliente")


class FacturaCartera(db.Model):
    __tablename__ = "factura_cartera"

    id = db.Column(db.Integer, primary_key=True)
    # Nulo para deudas de antes de usar el sistema, sin una ruta de camión a la cual ligarlas.
    salida_id = db.Column(db.Integer, db.ForeignKey("salida_camion.id"), nullable=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"), nullable=False)
    fecha = db.Column(db.Date, nullable=False, default=date.today)
    monto = db.Column(db.Integer, nullable=False)
    estado = db.Column(db.String(20), nullable=False, default="pendiente")
    fecha_pago = db.Column(db.Date, nullable=True)
    notas = db.Column(db.String(255), nullable=True)

    salida = db.relationship("SalidaCamion", back_populates="facturas")
    cliente = db.relationship("Cliente", back_populates="facturas")


class AjusteCredito(db.Model):
    """Corrección manual al saldo de crédito acumulado — sobre todo para cargar el
    crédito que ya se tenía acumulado con Postobón antes de empezar a usar el sistema.
    monto positivo suma al saldo, negativo lo resta (por si hay que corregir un error)."""

    __tablename__ = "ajuste_credito"

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False, default=date.today)
    monto = db.Column(db.Integer, nullable=False)
    notas = db.Column(db.String(255), nullable=True)


class RecargaCamion(db.Model):
    """Producto que se le manda al camión mientras sigue en ruta (aparte de la carga
    inicial de la salida), porque se le acabó algo. Se suma a lo cargado de esa salida
    para calcular cuánto se vendió cuando finalmente regresa."""

    __tablename__ = "recarga_camion"

    id = db.Column(db.Integer, primary_key=True)
    salida_id = db.Column(db.Integer, db.ForeignKey("salida_camion.id"), nullable=False)
    fecha = db.Column(db.Date, nullable=False, default=date.today)
    notas = db.Column(db.String(255), nullable=True)

    salida = db.relationship("SalidaCamion", back_populates="recargas")
    detalles = db.relationship(
        "RecargaCamionDetalle", back_populates="recarga", cascade="all, delete-orphan"
    )


class RecargaCamionDetalle(db.Model):
    __tablename__ = "recarga_camion_detalle"

    id = db.Column(db.Integer, primary_key=True)
    recarga_id = db.Column(db.Integer, db.ForeignKey("recarga_camion.id"), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey("producto.id"), nullable=False)
    cantidad_unidades = db.Column(db.Integer, nullable=False)

    recarga = db.relationship("RecargaCamion", back_populates="detalles")
    producto = db.relationship("Producto")


class VentaBodega(db.Model):
    """Venta directa en bodega, sin pasar por el camión — se descuenta del inventario y
    se suma a la venta del día igual que las ventas implícitas de las rutas."""

    __tablename__ = "venta_bodega"

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False, default=date.today)
    notas = db.Column(db.String(255), nullable=True)

    detalles = db.relationship(
        "VentaBodegaDetalle", back_populates="venta", cascade="all, delete-orphan"
    )


class VentaBodegaDetalle(db.Model):
    __tablename__ = "venta_bodega_detalle"

    id = db.Column(db.Integer, primary_key=True)
    venta_id = db.Column(db.Integer, db.ForeignKey("venta_bodega.id"), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey("producto.id"), nullable=False)
    cantidad_unidades = db.Column(db.Integer, nullable=False)
    valor = db.Column(db.Integer, nullable=False)

    venta = db.relationship("VentaBodega", back_populates="detalles")
    producto = db.relationship("Producto")


class CategoriaGasto(db.Model):
    """Categoría de salida de dinero. tipo distingue si es un gasto del negocio (pagos a
    Postobón/otros distribuidores/nómina) o del hogar (arriendo, servicios, etc.). El
    usuario puede agregar más categorías de cualquiera de los dos tipos desde la pantalla."""

    __tablename__ = "categoria_gasto"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # "negocio" o "hogar"
    activa = db.Column(db.Boolean, nullable=False, default=True)

    gastos = db.relationship("Gasto", back_populates="categoria")


class Gasto(db.Model):
    """Una salida de dinero: pago a Postobón/distribuidores/nómina (negocio) o un gasto
    del hogar (arriendo, servicios, etc.). Reduce el efectivo disponible en Caja."""

    __tablename__ = "gasto"

    id = db.Column(db.Integer, primary_key=True)
    categoria_id = db.Column(db.Integer, db.ForeignKey("categoria_gasto.id"), nullable=False)
    fecha = db.Column(db.Date, nullable=False, default=date.today)
    monto = db.Column(db.Integer, nullable=False)
    notas = db.Column(db.String(255), nullable=True)

    categoria = db.relationship("CategoriaGasto", back_populates="gastos")
