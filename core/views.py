from datetime import timezone
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import Sum, Q
from decimal import Decimal
from django.utils import timezone

from .forms import (
    ExpenseForm,
    PurchaseInvoiceForm,
    PurchaseInvoiceItemForm,
    PurchasePaymentForm,
    SalesInvoiceForm,
    SalesInvoiceItemForm,
    SalesInvoiceItemFormSet,
    SalesInvoiceItemModelFormSet,
    SalesPaymentForm,
)
from .models import Expense, Product, PurchaseInvoice, PurchasePayment, SalesInvoice, SalesPayment, Supplier, SupplierProduct


# ── Role helpers ───────────────────────────────────────────────────────────────

def is_administrator(user):
    return user.is_superuser or user.groups.filter(name="administrator").exists()


def is_operator_or_admin(user):
    return user.is_superuser or user.groups.filter(
        name__in=["administrator", "operator"]
    ).exists()


# ── Home ───────────────────────────────────────────────────────────────────────
PAGE_SIZE = 30
 

@login_required
def home(request):
    from collections import defaultdict

    is_admin = is_administrator(request.user)

    sales_invoices = SalesInvoice.objects.select_related("customer").order_by("-invoice_date", "-id")

    STATUS_ORDER = {
        SalesInvoice.STATUS_PENDING: 0,
        SalesInvoice.STATUS_PARTIAL: 1,
        SalesInvoice.STATUS_PAID:    2,
    }

    customers_map = {}
    for inv in sales_invoices:
        cid = inv.customer_id
        if cid not in customers_map:
            customers_map[cid] = {
                "name": inv.customer.name,
                "invoices": [],
                "pending_count": 0,
                "partial_count": 0,
                "paid_count": 0,
                "total_pending": Decimal("0.00"),
            }
        customers_map[cid]["invoices"].append(inv)
        if inv.status == SalesInvoice.STATUS_PENDING:
            customers_map[cid]["pending_count"] += 1
        elif inv.status == SalesInvoice.STATUS_PARTIAL:
            customers_map[cid]["partial_count"] += 1
        elif inv.status == SalesInvoice.STATUS_PAID:
            customers_map[cid]["paid_count"] += 1
        customers_map[cid]["total_pending"] += inv.balance_due

    # Ordenar facturas de cada cliente:
    # 1° pendientes, 2° abonadas, 3° pagadas — dentro de cada grupo por fecha desc
    for c in customers_map.values():
        c["invoices"].sort(
            key=lambda i: (STATUS_ORDER.get(i.status, 9), -i.invoice_date.toordinal())
        )

    # Clientes: primero los que deben (mayor deuda), luego los saldados por nombre
    sales_customers = sorted(
        customers_map.values(),
        key=lambda c: (-c["total_pending"], c["name"].lower()),
    )

    context = {
        "is_admin": is_admin,
        "sales_invoices": sales_invoices,
        "sales_customers": sales_customers,
        "total_sales_invoices": sales_invoices.count(),
    }

    if is_admin:
        import datetime as _dt
        from django.db.models import Min, Sum as _Sum
        from .models import PurchaseInvoiceItem, SalesInvoiceItem

        # ── Leer filtros de fecha desde GET ──────────────────────────────────
        c_desde_raw = request.GET.get("c_desde", "")
        c_hasta_raw = request.GET.get("c_hasta", "")
        try:
            c_desde = _dt.date.fromisoformat(c_desde_raw)
        except (ValueError, TypeError):
            c_desde = None
        try:
            c_hasta = _dt.date.fromisoformat(c_hasta_raw)
        except (ValueError, TypeError):
            c_hasta = None

        # ── Facturas de compra filtradas por fecha para la tabla ──────────────
        purchase_invoices = PurchaseInvoice.objects.select_related("supplier").order_by("-invoice_date", "-id")
        if c_desde:
            purchase_invoices = purchase_invoices.filter(invoice_date__gte=c_desde)
        if c_hasta:
            purchase_invoices = purchase_invoices.filter(invoice_date__lte=c_hasta)

        # ── Contador de inventario por producto ───────────────────────────────
        # 1. Compras en el rango
        purchase_qs = PurchaseInvoiceItem.objects
        if c_desde:
            purchase_qs = purchase_qs.filter(invoice__invoice_date__gte=c_desde)
        if c_hasta:
            purchase_qs = purchase_qs.filter(invoice__invoice_date__lte=c_hasta)

        purchase_items = (
            purchase_qs
            .values(
                "supplier_product__product__id",
                "supplier_product__product__name",
                "supplier_product__product__kg_per_block",
            )
            .annotate(
                total_kilos_comprados=Sum("total_kilos"),
                total_bloques_ingresados=Sum("block_quantity"),
                primera_compra=Min("invoice__invoice_date"),
            )
            .order_by("supplier_product__product__name")
        )

        # 2. Ventas: sumar el campo blocks directamente por producto y rango
        sales_qs = (
            SalesInvoiceItem.objects
            .values("product__id")
            .annotate(total_blocks=_Sum("blocks"))
        )
        if c_desde:
            sales_qs = sales_qs.filter(invoice__invoice_date__gte=c_desde)
        if c_hasta:
            sales_qs = sales_qs.filter(invoice__invoice_date__lte=c_hasta)

        sales_blocks_map = {
            row["product__id"]: Decimal(str(row["total_blocks"] or 0))
            for row in sales_qs
        }

        # 3. Construir contadores
        product_counters = []
        for row in purchase_items:
            pid            = row["supplier_product__product__id"]
            name           = row["supplier_product__product__name"]
            kg_per_block   = row["supplier_product__product__kg_per_block"]
            kilos          = row["total_kilos_comprados"] or Decimal("0.00")
            ingresados     = row["total_bloques_ingresados"]
            primera_compra = row["primera_compra"]

            if ingresados:
                comprados = Decimal(str(ingresados))
            elif kg_per_block and kg_per_block > 0:
                comprados = kilos / Decimal(str(kg_per_block))
            else:
                continue

            vendidos  = sales_blocks_map.get(pid, Decimal("0"))
            restantes = comprados - vendidos
            pct = min(int((vendidos / comprados) * 100), 100) if comprados > 0 else 0

            product_counters.append({
                "name":           name,
                "comprados":      int(comprados),
                "vendidos":       float(vendidos),
                "restantes":      float(restantes),
                "pct":            pct,
                "agotado":        restantes <= 0,
                "stock_bajo":     pct >= 80 and restantes > 0,
                "primera_compra": primera_compra,
            })

        context.update({
            "purchase_invoices":       purchase_invoices,
            "total_purchase_invoices": purchase_invoices.count(),
            "total_sales_invoices":    sales_invoices.count(),
            "product_counters":        product_counters,
            "c_desde":                 c_desde_raw,
            "c_hasta":                 c_hasta_raw,
        })

    return render(request, "core/purchases/home.html", context)

# ── Purchases (administrator only) ────────────────────────────────────────────

@login_required
def create_purchase_invoice(request):
    if not is_administrator(request.user):
        raise PermissionDenied

    supplier_id = request.GET.get("supplier") or request.POST.get("supplier")
    selected_supplier = None

    if supplier_id:
        selected_supplier = get_object_or_404(Supplier, pk=supplier_id, is_active=True)

    if request.method == "POST":
        invoice_form = PurchaseInvoiceForm(request.POST)
        item_form = PurchaseInvoiceItemForm(request.POST, supplier=selected_supplier)

        if invoice_form.is_valid() and item_form.is_valid():
            is_paid = invoice_form.cleaned_data.get("is_paid", False)

            invoice = invoice_form.save(commit=False)

            last = PurchaseInvoice.objects.order_by("-id").first()
            next_number = (int(last.invoice_number) + 1) if last and last.invoice_number.isdigit() else 1
            invoice.invoice_number = str(next_number)

            invoice.save()

            item = item_form.save(commit=False)
            item.invoice = invoice
            item.save()

            # Si se marcó como pagada, crear el pago automáticamente
            invoice.refresh_from_db()
            if is_paid and invoice.total_amount > 0:
                PurchasePayment.objects.create(
                    invoice=invoice,
                    payment_date=invoice.invoice_date,
                    amount=invoice.total_amount,
                    notes="Pago registrado automáticamente al crear la factura.",
                )
                invoice.refresh_from_db()

            messages.success(request, f"Factura de compra #{invoice.invoice_number} creada correctamente.")
            return redirect("create_purchase_invoice")
    else:
        initial = {}
        if selected_supplier:
            initial["supplier"] = selected_supplier.id

        invoice_form = PurchaseInvoiceForm(initial=initial)
        item_form = PurchaseInvoiceItemForm(supplier=selected_supplier)

    context = {
        "invoice_form": invoice_form,
        "item_form": item_form,
        "selected_supplier": selected_supplier,
    }
    return render(request, "core/purchases/create_purchase_invoice.html", context)


# ── Ajax supplier products ─────────────────────────────────────────────────────

@login_required
def get_supplier_products(request):
    if not is_administrator(request.user):
        raise PermissionDenied

    supplier_id = request.GET.get("supplier_id")

    if not supplier_id:
        return JsonResponse({"products": []})

    supplier_products = SupplierProduct.objects.filter(
        supplier_id=supplier_id,
        is_active=True,
        product__is_active=True,
    ).select_related("product")

    products = [
        {
            "id": sp.id,
            "name": sp.product.name,
            "price_per_kilo": str(sp.default_purchase_price),
            "kilos_per_basket": str(sp.kilos_per_basket or "0.00"),
            "purchase_pricing_type": sp.product.purchase_pricing_type,
            "requires_weight": sp.product.requires_weight,
        }
        for sp in supplier_products
    ]

    return JsonResponse({"products": products})


# ── Edit purchase invoice (administrator only) ─────────────────────────────────

@login_required
@transaction.atomic
def edit_purchase_invoice(request, pk):
    if not is_administrator(request.user):
        raise PermissionDenied

    invoice = get_object_or_404(
        PurchaseInvoice.objects.select_related("supplier").prefetch_related(
            "items__supplier_product__product", "payments"
        ),
        pk=pk,
    )
    item = invoice.items.first()
    selected_supplier = invoice.supplier

    if request.method == "POST":
        # Get supplier from POST in case it changed
        post_supplier_id = request.POST.get("supplier")
        if post_supplier_id:
            try:
                selected_supplier = Supplier.objects.get(pk=post_supplier_id, is_active=True)
            except Supplier.DoesNotExist:
                selected_supplier = invoice.supplier

        invoice_form = PurchaseInvoiceForm(request.POST, instance=invoice)
        item_form = PurchaseInvoiceItemForm(
            request.POST, instance=item, supplier=selected_supplier
        )

        if invoice_form.is_valid() and item_form.is_valid():
            is_paid = invoice_form.cleaned_data.get("is_paid", False)

            updated_invoice = invoice_form.save()

            updated_item = item_form.save(commit=False)
            updated_item.invoice = updated_invoice
            updated_item.save()

            # Traer estado fresco después de que item.save() recalculó los totales
            updated_invoice.refresh_from_db()

            if is_paid:
                # Marcar como pagada: registrar el saldo pendiente si lo hay
                if updated_invoice.balance_due > 0:
                    PurchasePayment.objects.create(
                        invoice=updated_invoice,
                        payment_date=updated_invoice.invoice_date,
                        amount=updated_invoice.balance_due,
                        notes="Pago registrado al editar la factura.",
                    )
            else:
                # Desmarcar pagada: eliminar TODOS los pagos sin importar si era
                # pagada (STATUS_PAID) o abonada (STATUS_PARTIAL).
                # Usamos filter() por PK para evitar el manager cacheado en memoria.
                PurchasePayment.objects.filter(invoice_id=updated_invoice.pk).delete()
                # Instancia fresca para que update_totals() no use datos obsoletos
                fresh = PurchaseInvoice.objects.get(pk=updated_invoice.pk)
                fresh.update_totals()

            messages.success(
                request,
                f"Factura de compra #{updated_invoice.invoice_number} actualizada correctamente.",
            )
            return redirect("home")
    else:
        invoice_form = PurchaseInvoiceForm(
            instance=invoice,
            initial={"is_paid": invoice.status == PurchaseInvoice.STATUS_PAID},
        )
        item_form = PurchaseInvoiceItemForm(instance=item, supplier=selected_supplier)

    context = {
        "invoice": invoice,
        "invoice_form": invoice_form,
        "item_form": item_form,
        "selected_supplier": selected_supplier,
        "initial_product_id": item.supplier_product_id if item else "",
    }
    return render(request, "core/purchases/edit_purchase_invoice.html", context)


# ── Purchase invoice detail ────────────────────────────────────────────────────
 
@login_required
def purchase_invoice_detail(request, pk):
    if not is_administrator(request.user):
        raise PermissionDenied
 
    invoice = get_object_or_404(
        PurchaseInvoice.objects.select_related("supplier").prefetch_related(
            "items__supplier_product__product", "payments"
        ),
        pk=pk,
    )
    return render(request, "core/purchases/purchase_invoice_detail.html", {"invoice": invoice})

# ── Purchase payment ───────────────────────────────────────────────────────────
@login_required
def add_purchase_payment(request, pk):
    if not is_administrator(request.user):
        raise PermissionDenied
 
    invoice = get_object_or_404(
        PurchaseInvoice.objects.select_related("supplier"),
        pk=pk,
    )
 
    if invoice.status == PurchaseInvoice.STATUS_PAID:
        messages.error(request, "Esta factura ya está completamente pagada.")
        return redirect("home")
 
    if request.method == "POST":
        form = PurchasePaymentForm(request.POST, invoice=invoice)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.invoice = invoice
            payment.save()
            messages.success(request, "Pago al proveedor registrado correctamente.")
            return redirect("home")
    else:
        form = PurchasePaymentForm(invoice=invoice)
 
    payments = invoice.payments.order_by("-payment_date", "-id")
 
    context = {
        "invoice": invoice,
        "form": form,
        "payments": payments,
    }
    return render(request, "core/purchases/add_purchase_payment.html", context)

# ── Sales ──────────────────────────────────────────────────────────────────────

@login_required
@transaction.atomic
def create_sales_invoice(request):
    if not is_operator_or_admin(request.user):
        raise PermissionDenied

    if request.method == "POST":
        invoice_form = SalesInvoiceForm(request.POST)
        item_formset = SalesInvoiceItemFormSet(request.POST, prefix="items")

        if invoice_form.is_valid() and item_formset.is_valid():
            is_paid = invoice_form.cleaned_data.get("is_paid", False)

            invoice = invoice_form.save(commit=False)
            invoice.subtotal = 0
            invoice.total_amount = 0
            invoice.amount_paid = 0
            invoice.balance_due = 0
            invoice.save()

            for form in item_formset:
                if form.cleaned_data:
                    item = form.save(commit=False)
                    item.invoice = invoice
                    item.save()

            invoice.refresh_from_db()
            invoice.update_totals()

            if is_paid and invoice.total_amount > 0:
                SalesPayment.objects.create(
                    invoice=invoice,
                    payment_date=invoice.invoice_date,
                    amount=invoice.total_amount,
                    notes="Pago registrado automáticamente al crear la factura.",
                )
                invoice.refresh_from_db()

            messages.success(request, "Factura de venta creada correctamente.")
            return redirect("create_sales_invoice")

    else:
        invoice_form = SalesInvoiceForm()
        item_formset = SalesInvoiceItemFormSet(prefix="items")

    products_data = {
        str(p.id): {
            "pricing_type": p.sale_pricing_type,
            "requires_weight": p.requires_weight,
            "requires_blocks": p.requires_blocks,
            "kg_per_block": float(p.kg_per_block) if p.kg_per_block else None,
        }
        for p in Product.objects.filter(is_active=True)
    }

    context = {
        "invoice_form": invoice_form,
        "item_formset": item_formset,
        "products_data": json.dumps(products_data),
    }
    return render(request, "core/purchases/create_sales_invoice.html", context)


@login_required
def sales_invoice_detail(request, pk):
    if not is_operator_or_admin(request.user):
        raise PermissionDenied

    invoice = get_object_or_404(
        SalesInvoice.objects.select_related("customer").prefetch_related("items__product"),
        pk=pk,
    )
    return render(request, "core/purchases/sales_invoice_detail.html", {"invoice": invoice})


@login_required
def add_sales_payment(request, pk):
    if not is_operator_or_admin(request.user):
        raise PermissionDenied

    invoice = get_object_or_404(
        SalesInvoice.objects.select_related("customer"),
        pk=pk,
    )

    if request.method == "POST":
        form = SalesPaymentForm(request.POST, invoice=invoice)
        if form.is_valid():
            try:
                payment = form.save(commit=False)
                payment.invoice = invoice
                payment.save()
                messages.success(request, "Pago registrado correctamente.")
                return redirect("sales_invoice_detail", pk=invoice.pk)
            except Exception as e:
                form.add_error("amount", str(e))
    else:
        form = SalesPaymentForm(invoice=invoice)

    context = {
        "invoice": invoice,
        "form": form,
    }
    return render(request, "core/purchases/add_sales_payment.html", context)

# ── Edit sales invoice (administrator only) ────────────────────────────────────
 
@login_required
@transaction.atomic
def edit_sales_invoice(request, pk):
    if not is_administrator(request.user):
        raise PermissionDenied
 
    invoice = get_object_or_404(
        SalesInvoice.objects.select_related("customer").prefetch_related("items__product"),
        pk=pk,
    )
 
    if request.method == "POST":
        invoice_form = SalesInvoiceForm(request.POST, instance=invoice)
        item_formset = SalesInvoiceItemModelFormSet(
            request.POST,
            queryset=invoice.items.all(),
            prefix="items",
        )
 
        if invoice_form.is_valid() and item_formset.is_valid():
            is_paid = invoice_form.cleaned_data.get("is_paid", False)
 
            invoice_form.save()
 
            # Process each form: delete marked ones, save the rest
            for form in item_formset:
                if not form.cleaned_data:
                    continue
                if form.cleaned_data.get("DELETE"):
                    if form.instance.pk:
                        form.instance.delete()
                else:
                    # Only save if the form has meaningful data (product selected)
                    if form.cleaned_data.get("product"):
                        item = form.save(commit=False)
                        item.invoice = invoice
                        item.save()
 
            invoice.refresh_from_db()
            invoice.update_totals()

            # Corrección del estado de pago
            if is_paid:
                # Marcar como pagada: registrar el saldo pendiente si lo hay
                invoice.refresh_from_db()
                if invoice.balance_due > 0:
                    SalesPayment.objects.create(
                        invoice=invoice,
                        payment_date=invoice.invoice_date,
                        amount=invoice.balance_due,
                        notes="Pago registrado al editar la factura.",
                    )
            else:
                # Desmarcar pagada: eliminar TODOS los pagos sin importar si era
                # pagada (STATUS_PAID) o abonada (STATUS_PARTIAL).
                # Usamos filter() por PK para evitar el manager cacheado en memoria.
                SalesPayment.objects.filter(invoice_id=invoice.pk).delete()
                # Instancia fresca para que update_totals() no use datos obsoletos
                fresh = SalesInvoice.objects.get(pk=invoice.pk)
                fresh.update_totals()
 
            messages.success(
                request,
                f"Factura #{invoice.invoice_number} actualizada correctamente.",
            )
            return redirect("home")
 
    else:
        invoice_form = SalesInvoiceForm(
            instance=invoice,
            initial={"is_paid": invoice.status == SalesInvoice.STATUS_PAID},
        )
        item_formset = SalesInvoiceItemModelFormSet(
            queryset=invoice.items.all(),
            prefix="items",
        )
 
    products_data = {
        str(p.id): {
            "pricing_type": p.sale_pricing_type,
            "requires_weight": p.requires_weight,
            "requires_blocks": p.requires_blocks,
            "kg_per_block": float(p.kg_per_block) if p.kg_per_block else None,
        }
        for p in Product.objects.filter(is_active=True)
    }
 
    context = {
        "invoice": invoice,
        "invoice_form": invoice_form,
        "item_formset": item_formset,
        "products_data": json.dumps(products_data),
    }
    return render(request, "core/purchases/edit_sales_invoice.html", context)


# ── Reportes ──────────────────────────────────────────────────────────────────

@login_required
def period_report(request):
    if not is_administrator(request.user):
        raise PermissionDenied

    import datetime
    from django.db.models import Count
    from collections import defaultdict

    today = timezone.localdate()

    # Fechas por defecto: domingo anterior → hoy
    # (el domingo pasado como inicio, hoy como fin)
    days_since_sunday = (today.weekday() + 1) % 7
    default_start = today - datetime.timedelta(days=days_since_sunday)
    default_end   = today

    # Leer parámetros GET
    try:
        date_from = datetime.date.fromisoformat(request.GET.get("date_from", ""))
    except (ValueError, TypeError):
        date_from = default_start

    try:
        date_to = datetime.date.fromisoformat(request.GET.get("date_to", ""))
    except (ValueError, TypeError):
        date_to = default_end

    # Proteger: date_from no puede ser mayor que date_to
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    # ── Filtro por producto ────────────────────────────────────────────────
    product_id = request.GET.get("product_id", "").strip()
    selected_product_id = int(product_id) if product_id.isdigit() else None
    all_products = Product.objects.filter(is_active=True).order_by("name")

    period_label = (
        f"{date_from.strftime('%d/%m/%Y')} - {date_to.strftime('%d/%m/%Y')}"
    )

    # Ventas en el rango
    sales_invoices_qs = SalesInvoice.objects.filter(
        invoice_date__gte=date_from,
        invoice_date__lte=date_to,
    ).select_related("customer")

    if selected_product_id:
        sales_invoices_qs = sales_invoices_qs.filter(items__product_id=selected_product_id
        ).distinct()

    stotals = sales_invoices_qs.aggregate(
        total_amount=Sum("total_amount"),
        total_paid=Sum("amount_paid"),
        total_pending=Sum("balance_due"),
    )
    total_sold      = stotals.get("total_amount")  or Decimal("0.00")
    total_collected = stotals.get("total_paid")    or Decimal("0.00")
    total_pending   = stotals.get("total_pending") or Decimal("0.00")

    # Resumen por cliente
    sales_by_customer_qs = (
        sales_invoices_qs
        .values("customer__name")
        .annotate(
            total=Sum("total_amount"),
            paid=Sum("amount_paid"),
            pending=Sum("balance_due"),
            num_invoices=Count("id"),
        )
        # Primero los que deben (pending > 0), luego los saldados
        # Django no permite ordenar por anotación booleana directamente,
        # así que ordenamos por pending desc (mayor deuda primero), luego por nombre
        .order_by("-pending", "customer__name")
    )

    # Agrupar facturas por cliente
    sales_invoices_list = list(
        sales_invoices_qs.order_by("invoice_date", "id")
    )

    invoices_by_customer = defaultdict(list)
    for inv in sales_invoices_list:
        invoices_by_customer[inv.customer_id].append(inv)

    name_to_id = {inv.customer.name: inv.customer_id for inv in sales_invoices_list}

    customers_with_invoices = []
    for row in sales_by_customer_qs:
        cname = row["customer__name"]
        cid   = name_to_id.get(cname)
        invoices = sorted(
            invoices_by_customer.get(cid, []),
            # Pendientes/abonadas primero, pagadas al final
            key=lambda i: (i.status == "paid", i.invoice_number),
        )
        customers_with_invoices.append({
            "name":         cname,
            "num_invoices": row["num_invoices"],
            "total":        row["total"],
            "paid":         row["paid"],
            "pending":      row["pending"],
            "invoices":     invoices,
        })

    context = {
        "date_from":    date_from,
        "date_to":      date_to,
        "period_label": period_label,
        "today":        today,
        "all_products":          all_products,
        "selected_product_id":   selected_product_id,
        "sales_invoices":           sales_invoices_list,
        "customers_with_invoices":  customers_with_invoices,
        "total_sold":      total_sold,
        "total_collected": total_collected,
        "total_pending":   total_pending,
    }

    return render(request, "core/purchases/period_report.html", context)




#------------------GASTOS--------------
@login_required
def create_expense(request):
    """Register a new expense. Administrators and operators."""
    if not is_operator_or_admin(request.user):
        raise PermissionDenied
 
    if request.method == "POST":
        form = ExpenseForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Gasto registrado correctamente.")
            return redirect("expense_list")
    else:
        form = ExpenseForm()
 
    return render(request, "core/purchases/create_expense.html", {"form": form})
 
 
@login_required
def expense_list(request):
    """Register a new expense. Administrators and operators."""
    if not is_operator_or_admin(request.user):
        raise PermissionDenied
 
    import datetime
 
    expenses = Expense.objects.select_related("motorcycle").order_by("-expense_date", "-id")
 
    # Filter by category
    category_filter = request.GET.get("category", "")
    if category_filter:
        expenses = expenses.filter(category=category_filter)
 
    # Filter by date range
    try:
        date_from = datetime.date.fromisoformat(request.GET.get("date_from", ""))
    except (ValueError, TypeError):
        date_from = None
 
    try:
        date_to = datetime.date.fromisoformat(request.GET.get("date_to", ""))
    except (ValueError, TypeError):
        date_to = None
 
    if date_from:
        expenses = expenses.filter(expense_date__gte=date_from)
    if date_to:
        expenses = expenses.filter(expense_date__lte=date_to)
 
    total_amount = expenses.aggregate(total=Sum("amount")).get("total") or Decimal("0.00")
 
    # Totals per category (from filtered queryset)
    totals_by_category = (
        expenses
        .values("category")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    category_labels = dict(Expense.CATEGORY_CHOICES)
    category_totals = [
        {"label": category_labels.get(row["category"], row["category"]), "total": row["total"]}
        for row in totals_by_category
    ]
 
    context = {
        "expenses":          expenses,
        "total_amount":      total_amount,
        "category_totals":   category_totals,
        "category_choices":  Expense.CATEGORY_CHOICES,
        "category_filter":   category_filter,
        "date_from":         date_from,
        "date_to":           date_to,
    }
    return render(request, "core/purchases/expense_list.html", context)
