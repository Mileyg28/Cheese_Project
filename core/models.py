from decimal import Decimal
from email import errors

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Product(TimeStampedModel):
    PRICE_TYPE_PER_KG = "per_kg"
    PRICE_TYPE_PER_BLOCK = "per_block"

    PRICE_TYPE_CHOICES = [
        (PRICE_TYPE_PER_KG, "Por kilo"),
        (PRICE_TYPE_PER_BLOCK, "Por bloque"),
    ]

    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)

    sale_pricing_type = models.CharField(
        max_length=20,
        choices=PRICE_TYPE_CHOICES,
        default=PRICE_TYPE_PER_KG,
    )
    purchase_pricing_type = models.CharField(
        max_length=20,
        choices=PRICE_TYPE_CHOICES,
        default=PRICE_TYPE_PER_KG,
    )

    requires_weight = models.BooleanField(default=True)
    requires_blocks = models.BooleanField(default=False)

    blocks_per_basket = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Dato opcional solo como referencia operativa.",
    )
    kg_per_block = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Peso promedio de un bloque en kg. Se usa para calcular bloques automáticamente.",
        verbose_name="Kg por bloque",
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Product"
        verbose_name_plural = "Products"

    def __str__(self):
        return self.name

    def clean(self):
        if self.sale_pricing_type == self.PRICE_TYPE_PER_KG and not self.requires_weight:
            raise ValidationError(
                {"requires_weight": "A product sold per kg must require weight."}
            )

        if self.sale_pricing_type == self.PRICE_TYPE_PER_BLOCK and not self.requires_blocks:
            raise ValidationError(
                {"requires_blocks": "A product sold per block must require blocks."}
            )


class Supplier(TimeStampedModel):
    name = models.CharField(max_length=150)
    document_number = models.CharField(max_length=30, unique=True, null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Supplier"
        verbose_name_plural = "Suppliers"

    def __str__(self):
        return self.name

    @property
    def total_purchased(self):
        return (
            self.purchase_invoices.aggregate(total=Sum("total_amount")).get("total")
            or Decimal("0.00")
        )

    @property
    def total_paid(self):
        return (
            PurchasePayment.objects.filter(invoice__supplier=self).aggregate(
                total=Sum("amount")
            ).get("total")
            or Decimal("0.00")
        )

    @property
    def balance_due(self):
        return self.total_purchased - self.total_paid


class Customer(TimeStampedModel):
    name = models.CharField(max_length=150)
    document_number = models.CharField(max_length=30, unique=True, null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    neighborhood = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Customer"
        verbose_name_plural = "Customers"

    def __str__(self):
        return self.name

    @property
    def total_invoiced(self):
        return (
            self.sales_invoices.aggregate(total=Sum("total_amount")).get("total")
            or Decimal("0.00")
        )

    @property
    def total_paid(self):
        return (
            SalesPayment.objects.filter(invoice__customer=self).aggregate(
                total=Sum("amount")
            ).get("total")
            or Decimal("0.00")
        )

    @property
    def balance_due(self):
        return self.total_invoiced - self.total_paid
# ── Mensajero ──────────────────────────────────────────────────────────────────
 
class Mensajero(TimeStampedModel):
    name = models.CharField(max_length=150, verbose_name="Nombre")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Teléfono")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
 
    class Meta:
        ordering = ["name"]
        verbose_name = "Mensajero"
        verbose_name_plural = "Mensajeros"
 
    def __str__(self):
        return self.name

class SupplierProduct(TimeStampedModel):
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name="supplier_products",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="supplier_products",
    )
    kilos_per_basket = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="How many kilos one basket represents for this supplier and product.",
    )
    default_purchase_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Default purchase price for this supplier and product.",
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["supplier__name", "product__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["supplier", "product"],
                name="unique_supplier_product",
            )
        ]
        verbose_name = "Supplier product"
        verbose_name_plural = "Supplier products"

    def __str__(self):
        return f"{self.supplier.name} - {self.product.name}"


class PurchaseInvoice(TimeStampedModel):
    STATUS_PENDING = "pending"
    STATUS_PARTIAL = "partial"
    STATUS_PAID = "paid"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PARTIAL, "Partial"),
        (STATUS_PAID, "Paid"),
    ]

    invoice_number = models.CharField(max_length=50)
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="purchase_invoices",
    )
    invoice_date = models.DateField(default=timezone.localdate)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )

    total_kilos = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    subtotal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    freight_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    amount_paid = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    balance_due = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-invoice_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["supplier", "invoice_number"],
                name="unique_purchase_invoice_per_supplier",
            )
        ]
        verbose_name = "Purchase invoice"
        verbose_name_plural = "Purchase invoices"

    def __str__(self):
        return f"Purchase {self.invoice_number} - {self.supplier.name}"

    def update_totals(self, commit=True):
        aggregated = self.items.aggregate(
            total=Sum("line_total"),
            kilos=Sum("total_kilos"),
        )
        items_total = aggregated.get("total") or Decimal("0.00")
        kilos_total = aggregated.get("kilos") or Decimal("0.00")
        payments_total = (
            self.payments.aggregate(total=Sum("amount")).get("total")
            or Decimal("0.00")
        )
 
        self.total_kilos = kilos_total
        self.subtotal = items_total
        self.total_amount = items_total + (self.freight_cost or Decimal("0.00"))
        self.amount_paid = payments_total
        self.balance_due = self.total_amount - self.amount_paid
 
        if self.total_amount > Decimal("0.00") and self.balance_due <= Decimal("0.00"):
            # Pagada: hay un total real y está completamente cubierto
            self.balance_due = Decimal("0.00")
            self.status = self.STATUS_PAID
        elif self.amount_paid > Decimal("0.00"):
            # Abonada parcialmente
            self.status = self.STATUS_PARTIAL
        else:
            # Sin pagos o total en cero → pendiente
            self.status = self.STATUS_PENDING
 
        if commit:
            self.save(
                update_fields=[
                    "total_kilos",
                    "subtotal",
                    "total_amount",
                    "amount_paid",
                    "balance_due",
                    "status",
                    "updated_at",
                ]
            )

    def clean(self):
        if self.freight_cost < 0:
            raise ValidationError({"freight_cost": "Freight cost cannot be negative."})


class PurchaseInvoiceItem(TimeStampedModel):
    invoice = models.ForeignKey(
        PurchaseInvoice,
        on_delete=models.CASCADE,
        related_name="items",
    )
    supplier_product = models.ForeignKey(
        SupplierProduct,
        on_delete=models.PROTECT,
        related_name="purchase_items",
    )

    basket_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        default=Decimal("0.00"),
    )
    kilos_per_basket = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        default=Decimal("0.00"),
    )
    total_kilos = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    weight_kg = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        default=Decimal("0.00"),
        help_text="Real weight if entered manually.",
    )

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Price per kg according to the selected supplier product.",
    )
    line_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    class Meta:
        ordering = ["id"]
        verbose_name = "Purchase invoice item"
        verbose_name_plural = "Purchase invoice items"

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.supplier_product.product.name}"

    @property
    def product(self):
        return self.supplier_product.product

    def clean(self):
        errors = {}

        if self.supplier_product_id and self.invoice_id:
            if self.supplier_product.supplier_id != self.invoice.supplier_id:
                errors["supplier_product"] = (
                    "The selected product does not belong to the invoice supplier."
                )

        if self.basket_quantity is not None and self.basket_quantity < 0:
            errors["basket_quantity"] = "Basket quantity cannot be negative."

        if self.weight_kg is not None and self.weight_kg < 0:
            errors["weight_kg"] = "Weight cannot be negative."

        if errors:
            raise ValidationError(errors)

    def calculate_total_kilos(self):
        if self.weight_kg and self.weight_kg > 0:
            return self.weight_kg

        return (
            (self.basket_quantity or Decimal("0.00"))
            * (self.kilos_per_basket or Decimal("0.00"))
        )

    def save(self, *args, **kwargs):
        self.kilos_per_basket = (
            self.supplier_product.kilos_per_basket or Decimal("0.00")
        )
        self.unit_price = (
            self.supplier_product.default_purchase_price or Decimal("0.00")
        )
        self.total_kilos = self.calculate_total_kilos()
        self.line_total = self.total_kilos * self.unit_price

        super().save(*args, **kwargs)
        self.invoice.update_totals()

    def delete(self, *args, **kwargs):
        invoice = self.invoice
        super().delete(*args, **kwargs)
        invoice.update_totals()


class PurchasePayment(TimeStampedModel):
    invoice = models.ForeignKey(
        PurchaseInvoice,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    payment_date = models.DateField(default=timezone.localdate)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-payment_date", "-id"]
        verbose_name = "Purchase payment"
        verbose_name_plural = "Purchase payments"

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.amount}"

    def clean(self):
        if self.amount is None:
            errors["amount"] = "El valor del pago es obligatorio."
        elif self.amount <= 0:
            raise ValidationError({"amount": "Payment amount must be greater than zero."})

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.invoice.update_totals()

    def delete(self, *args, **kwargs):
        invoice = self.invoice
        super().delete(*args, **kwargs)
        invoice.update_totals()


invoice_number_4_digits_validator = RegexValidator(
    regex=r"^\d{4}$",
    message="El número de factura debe tener exactamente 4 dígitos.",
)


class SalesInvoice(TimeStampedModel):
    STATUS_PENDING = "pending"
    STATUS_PARTIAL = "partial"
    STATUS_PAID = "paid"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pendiente"),
        (STATUS_PARTIAL, "Abonada"),
        (STATUS_PAID, "Pagada"),
    ]

    invoice_number = models.CharField(
        max_length=4,
        unique=True,
        validators=[invoice_number_4_digits_validator],
        verbose_name="Número de factura",
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="sales_invoices",
        verbose_name="Cliente",
    )
    mensajero = models.ForeignKey(
        Mensajero,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_invoices",
        verbose_name="Mensajero",
    )
    invoice_date = models.DateField(
        default=timezone.localdate,
        verbose_name="Fecha",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name="Estado",
    )

    subtotal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Subtotal",
    )
    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Total factura",
    )
    amount_paid = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Valor pagado",
    )
    balance_due = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Saldo pendiente",
    )

    notes = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        ordering = ["-invoice_date", "-id"]
        verbose_name = "Factura de venta"
        verbose_name_plural = "Facturas de venta"

    def __str__(self):
        return f"Venta {self.invoice_number} - {self.customer.name}"

    @property
    def is_paid(self):
        return self.status == self.STATUS_PAID

    def update_totals(self, commit=True):
        items_total = (
            self.items.aggregate(total=Sum("line_total")).get("total")
            or Decimal("0.00")
        )
        payments_total = (
            self.payments.aggregate(total=Sum("amount")).get("total")
            or Decimal("0.00")
        )
 
        self.subtotal = items_total
        self.total_amount = items_total
        self.amount_paid = payments_total
        self.balance_due = self.total_amount - self.amount_paid
 
        if self.total_amount > Decimal("0.00") and self.balance_due <= Decimal("0.00"):
            # Pagada: hay un total real y está completamente cubierto
            self.balance_due = Decimal("0.00")
            self.status = self.STATUS_PAID
        elif self.amount_paid > Decimal("0.00"):
            # Abonada parcialmente
            self.status = self.STATUS_PARTIAL
        else:
            # Sin pagos o total en cero → pendiente
            self.status = self.STATUS_PENDING
 
        if commit:
            self.save(
                update_fields=[
                    "subtotal",
                    "total_amount",
                    "amount_paid",
                    "balance_due",
                    "status",
                    "updated_at",
                ]
            )

    def clean(self):
        if self.total_amount < 0:
            raise ValidationError({"total_amount": "El total no puede ser negativo."})

        if self.amount_paid < 0:
            raise ValidationError({"amount_paid": "El valor pagado no puede ser negativo."})


class SalesInvoiceItem(TimeStampedModel):
    invoice = models.ForeignKey(
        SalesInvoice,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Factura",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="sales_items",
        verbose_name="Producto",
    )

    weight_kg = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        default=Decimal("0.00"),
        verbose_name="Peso (kg)",
    )
    blocks = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Bloques",
    )

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Precio unitario",
        help_text="Precio por kilo o por bloque según el tipo de venta del producto.",
    )
    line_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Total",
    )

    class Meta:
        ordering = ["id"]
        verbose_name = "Detalle de factura de venta"
        verbose_name_plural = "Detalles de factura de venta"

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.product.name}"

    def clean(self):
        errors = {}

        if not self.product_id:
            errors["product"] = "Debes seleccionar un producto."

        if self.unit_price < 0:
            errors["unit_price"] = "El precio unitario no puede ser negativo."

        if self.product_id:
            if self.product.sale_pricing_type == Product.PRICE_TYPE_PER_KG:
                if not self.weight_kg or self.weight_kg <= 0:
                    errors["weight_kg"] = "El peso es obligatorio para productos vendidos por kilo."

            if self.product.sale_pricing_type == Product.PRICE_TYPE_PER_BLOCK:
                if not self.blocks or self.blocks <= 0:
                    errors["blocks"] = "La cantidad de bloques es obligatoria para productos vendidos por bloque."

        if errors:
            raise ValidationError(errors)

    def calculate_line_total(self):
        if self.product.sale_pricing_type == Product.PRICE_TYPE_PER_KG:
            return (self.weight_kg or Decimal("0.00")) * self.unit_price

        if self.product.sale_pricing_type == Product.PRICE_TYPE_PER_BLOCK:
            return Decimal(self.blocks or 0) * self.unit_price

        return Decimal("0.00")

    def save(self, *args, **kwargs):
        self.full_clean()
        self.line_total = self.calculate_line_total()
        super().save(*args, **kwargs)
        self.invoice.update_totals()

    def delete(self, *args, **kwargs):
        invoice = self.invoice
        super().delete(*args, **kwargs)
        invoice.update_totals()


class SalesPayment(TimeStampedModel):
    invoice = models.ForeignKey(
        SalesInvoice,
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name="Factura",
    )
    payment_date = models.DateField(
        default=timezone.localdate,
        verbose_name="Fecha de pago",
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Valor pagado",
    )
    notes = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        ordering = ["-payment_date", "-id"]
        verbose_name = "Pago de venta"
        verbose_name_plural = "Pagos de venta"

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.amount}"

    def clean(self):
        errors = {}

        if self.amount is None:
            errors["amount"] = "El valor del pago es obligatorio."
        elif self.amount <= 0:
            errors["amount"] = "El valor del pago debe ser mayor que cero."
        elif self.invoice_id:
            current_paid = (
                self.invoice.payments.exclude(pk=self.pk).aggregate(total=Sum("amount")).get("total")
                or Decimal("0.00")
            )
            remaining_balance = self.invoice.total_amount - current_paid
            if self.amount > remaining_balance:
                errors["amount"] = "El pago no puede ser mayor al saldo pendiente de la factura."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        self.invoice.update_totals()

    def delete(self, *args, **kwargs):
        invoice = self.invoice
        super().delete(*args, **kwargs)
        invoice.update_totals()