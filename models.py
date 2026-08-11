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

    precios = db.relationship(
        "ProductoPrecio", back_populates="producto", order_by="ProductoPrecio.vigente_desde"
    )

    def precio_vigente(self, fecha: date):
        """Precio de venta/lista efectivo en una fecha dada (el más reciente <= fecha)."""
        vigente = None
        for p in self.precios:
            if p.vigente_desde <= fecha:
                if vigente is None or p.vigente_desde > vigente.vigente_desde:
                    vigente = p
        return vigente.precio_venta_unidad if vigente else None

    def precio_actual(self):
        return self.precio_vigente(date.today())


class ProductoPrecio(db.Model):
    __tablename__ = "producto_precio"

    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey("producto.id"), nullable=False)
    precio_venta_unidad = db.Column(db.Integer, nullable=False)
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


class FacturaCartera(db.Model):
    __tablename__ = "factura_cartera"

    id = db.Column(db.Integer, primary_key=True)
    salida_id = db.Column(db.Integer, db.ForeignKey("salida_camion.id"), nullable=False)
    cliente = db.Column(db.String(120), nullable=False)
    fecha = db.Column(db.Date, nullable=False, default=date.today)
    monto = db.Column(db.Integer, nullable=False)
    estado = db.Column(db.String(20), nullable=False, default="pendiente")
    fecha_pago = db.Column(db.Date, nullable=True)
    notas = db.Column(db.String(255), nullable=True)

    salida = db.relationship("SalidaCamion", back_populates="facturas")
