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
    PurchaseInvoiceForm,
    PurchaseInvoiceItemForm,
    PurchasePaymentForm,
    SalesInvoiceForm,
    SalesInvoiceItemForm,
    SalesInvoiceItemFormSet,
    SalesPaymentForm,
)
from .models import Product, PurchaseInvoice, PurchasePayment, SalesInvoice, SalesPayment, Supplier, SupplierProduct


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
    is_admin = is_administrator(request.user)
 
    active_tab = request.GET.get("tab", "compras" if is_admin else "ventas")
 
    # ── Filtros y paginación de ventas ────────────────────────────────────────
    v_estado      = request.GET.get("v_estado", "")
    v_fecha_desde = request.GET.get("v_fecha_desde", "")
    v_fecha_hasta = request.GET.get("v_fecha_hasta", "")
    v_page        = request.GET.get("v_page", 1)
 
    sales_qs = SalesInvoice.objects.select_related("customer").order_by("-invoice_date", "-id")
    if v_estado:
        sales_qs = sales_qs.filter(status=v_estado)
    if v_fecha_desde:
        sales_qs = sales_qs.filter(invoice_date__gte=v_fecha_desde)
    if v_fecha_hasta:
        sales_qs = sales_qs.filter(invoice_date__lte=v_fecha_hasta)
 
    v_paginator   = Paginator(sales_qs, PAGE_SIZE)
    sales_invoices = v_paginator.get_page(v_page)
 
    context = {
        "is_admin": is_admin,
        "active_tab": active_tab,
        "sales_invoices": sales_invoices,
        "total_sales_invoices": SalesInvoice.objects.count(),
        "v_estado": v_estado,
        "v_fecha_desde": v_fecha_desde,
        "v_fecha_hasta": v_fecha_hasta,
    }
 
    if is_admin:
        # ── Filtros y paginación de compras ────────────────────────────────────
        c_estado      = request.GET.get("c_estado", "")
        c_fecha_desde = request.GET.get("c_fecha_desde", "")
        c_fecha_hasta = request.GET.get("c_fecha_hasta", "")
        c_page        = request.GET.get("c_page", 1)
 
        purchase_qs = PurchaseInvoice.objects.select_related("supplier").order_by("-invoice_date", "-id")
        if c_estado:
            purchase_qs = purchase_qs.filter(status=c_estado)
        if c_fecha_desde:
            purchase_qs = purchase_qs.filter(invoice_date__gte=c_fecha_desde)
        if c_fecha_hasta:
            purchase_qs = purchase_qs.filter(invoice_date__lte=c_fecha_hasta)
 
        c_paginator      = Paginator(purchase_qs, PAGE_SIZE)
        purchase_invoices = c_paginator.get_page(c_page)
 
        all_purchases = PurchaseInvoice.objects.all()
        all_sales     = SalesInvoice.objects.all()
 
        context.update({
            "purchase_invoices": purchase_invoices,
            "total_purchase_invoices": all_purchases.count(),
            "total_purchased": all_purchases.aggregate(total=Sum("total_amount")).get("total") or Decimal("0.00"),
            "total_sold":      all_sales.aggregate(total=Sum("total_amount")).get("total")     or Decimal("0.00"),
            "c_estado": c_estado,
            "c_fecha_desde": c_fecha_desde,
            "c_fecha_hasta": c_fecha_hasta,
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
# ── reportes----------------

@login_required
def period_report(request):
    if not is_administrator(request.user):
        raise PermissionDenied

    import datetime
    from django.db.models import Count

    today = timezone.localdate()

    # ── Modo: semanal o mensual ───────────────────────────────────────────────
    mode = request.GET.get("mode", "weekly")  # "weekly" | "monthly"

    MONTHS_ES = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
        9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
    }

    # ── Rango de años disponibles ─────────────────────────────────────────────
    first_purchase = PurchaseInvoice.objects.order_by("invoice_date").first()
    first_sale     = SalesInvoice.objects.order_by("invoice_date").first()
    start_year = today.year
    if first_purchase:
        start_year = min(start_year, first_purchase.invoice_date.year)
    if first_sale:
        start_year = min(start_year, first_sale.invoice_date.year)
    available_years = list(range(start_year, today.year + 1))

    # ════════════════════════════════════════════════════════════════════════
    # MODO SEMANAL
    # ════════════════════════════════════════════════════════════════════════
    if mode == "weekly":
        iso = today.isocalendar()  # (year, week, weekday)

        try:
            year = int(request.GET.get("year", iso[0]))
        except (ValueError, TypeError):
            year = iso[0]

        try:
            week = int(request.GET.get("week", iso[1]))
        except (ValueError, TypeError):
            week = iso[1]

        # Clamp week to valid range for that year
        max_week = datetime.date(year, 12, 28).isocalendar()[1]
        week = max(1, min(week, max_week))

        # Lunes y domingo de la semana seleccionada
        week_start = datetime.date.fromisocalendar(year, week, 1)   # lunes
        week_end   = datetime.date.fromisocalendar(year, week, 7)   # domingo

        # Semana anterior y siguiente para navegación
        prev_date  = week_start - datetime.timedelta(days=1)
        next_date  = week_end   + datetime.timedelta(days=1)
        prev_week  = prev_date.isocalendar()[1]
        prev_wyear = prev_date.isocalendar()[0]
        next_week  = next_date.isocalendar()[1]
        next_wyear = next_date.isocalendar()[0]

        # ── Compras de la semana ──────────────────────────────────────────
        purchase_invoices = PurchaseInvoice.objects.filter(
            invoice_date__gte=week_start,
            invoice_date__lte=week_end,
        ).select_related("supplier").order_by("invoice_date", "id")

        ptotals = purchase_invoices.aggregate(
            total_amount=Sum("total_amount"),
            total_kilos=Sum("total_kilos"),
            total_freight=Sum("freight_cost"),
        )
        total_purchased        = ptotals.get("total_amount")  or Decimal("0.00")
        total_kilos_purchased  = ptotals.get("total_kilos")   or Decimal("0.00")
        total_freight          = ptotals.get("total_freight") or Decimal("0.00")

        purchases_by_supplier = (
            purchase_invoices
            .values("supplier__name")
            .annotate(
                subtotal=Sum("subtotal"),
                freight=Sum("freight_cost"),
                total=Sum("total_amount"),
                kilos=Sum("total_kilos"),
                num_invoices=Count("id"),
            )
            .order_by("-total")
        )

        # ── Ventas de la semana ───────────────────────────────────────────
        sales_invoices = SalesInvoice.objects.filter(
            invoice_date__gte=week_start,
            invoice_date__lte=week_end,
        ).select_related("customer").order_by("invoice_date", "id")

        stotals = sales_invoices.aggregate(
            total_amount=Sum("total_amount"),
            total_paid=Sum("amount_paid"),
            total_pending=Sum("balance_due"),
        )
        total_sold      = stotals.get("total_amount")  or Decimal("0.00")
        total_collected = stotals.get("total_paid")    or Decimal("0.00")
        total_pending   = stotals.get("total_pending") or Decimal("0.00")

        sales_by_customer = (
            sales_invoices
            .values("customer__name")
            .annotate(
                total=Sum("total_amount"),
                paid=Sum("amount_paid"),
                pending=Sum("balance_due"),
                num_invoices=Count("id"),
            )
            .order_by("-total")
        )

        # Pagos recibidos durante la semana (por fecha de pago)
        from .models import SalesPayment
        payments_in_period = SalesPayment.objects.filter(
            payment_date__gte=week_start,
            payment_date__lte=week_end,
        ).aggregate(total=Sum("amount"))
        total_payments_received = payments_in_period.get("total") or Decimal("0.00")

        # Etiqueta del período
        period_label = (
            f"Semana {week} · "
            f"{week_start.strftime('%d/%m')} – {week_end.strftime('%d/%m/%Y')}"
        )

        # Semanas disponibles del año seleccionado (para el selector)
        max_week_selected = datetime.date(year, 12, 28).isocalendar()[1]
        available_weeks = []
        for w in range(1, max_week_selected + 1):
            ws = datetime.date.fromisocalendar(year, w, 1)
            we = datetime.date.fromisocalendar(year, w, 7)
            available_weeks.append({
                "num": w,
                "label": f"Sem. {w}  ({ws.strftime('%d/%m')} – {we.strftime('%d/%m')})",
            })

        context = {
            "mode": "weekly",
            "year": year,
            "week": week,
            "week_start": week_start,
            "week_end": week_end,
            "period_label": period_label,
            "available_years": available_years,
            "available_weeks": available_weeks,
            "prev_week": prev_week,
            "prev_wyear": prev_wyear,
            "next_week": next_week,
            "next_wyear": next_wyear,
            "can_go_next": next_date <= today,
            # Compras
            "purchase_invoices": purchase_invoices,
            "purchases_by_supplier": purchases_by_supplier,
            "total_purchased": total_purchased,
            "total_kilos_purchased": total_kilos_purchased,
            "total_freight": total_freight,
            # Ventas
            "sales_invoices": sales_invoices,
            "sales_by_customer": sales_by_customer,
            "total_sold": total_sold,
            "total_collected": total_collected,
            "total_pending": total_pending,
            "total_payments_received": total_payments_received,
            # Balance
            "gross_margin": total_sold - total_purchased,
            # Compartidos
            "months": [(k, v) for k, v in MONTHS_ES.items()],
        }

    # ════════════════════════════════════════════════════════════════════════
    # MODO MENSUAL
    # ════════════════════════════════════════════════════════════════════════
    else:
        try:
            year = int(request.GET.get("year", today.year))
        except (ValueError, TypeError):
            year = today.year

        try:
            month = int(request.GET.get("month", today.month))
            if not 1 <= month <= 12:
                month = today.month
        except (ValueError, TypeError):
            month = today.month

        # Mes anterior / siguiente
        if month == 1:
            prev_month, prev_myear = 12, year - 1
        else:
            prev_month, prev_myear = month - 1, year

        if month == 12:
            next_month, next_myear = 1, year + 1
        else:
            next_month, next_myear = month + 1, year

        can_go_next = (next_myear < today.year) or (
            next_myear == today.year and next_month <= today.month
        )

        # ── Compras del mes ───────────────────────────────────────────────
        purchase_invoices = PurchaseInvoice.objects.filter(
            invoice_date__year=year,
            invoice_date__month=month,
        ).select_related("supplier").order_by("invoice_date", "id")

        ptotals = purchase_invoices.aggregate(
            total_amount=Sum("total_amount"),
            total_kilos=Sum("total_kilos"),
            total_freight=Sum("freight_cost"),
        )
        total_purchased       = ptotals.get("total_amount")  or Decimal("0.00")
        total_kilos_purchased = ptotals.get("total_kilos")   or Decimal("0.00")
        total_freight         = ptotals.get("total_freight") or Decimal("0.00")

        purchases_by_supplier = (
            purchase_invoices
            .values("supplier__name")
            .annotate(
                subtotal=Sum("subtotal"),
                freight=Sum("freight_cost"),
                total=Sum("total_amount"),
                kilos=Sum("total_kilos"),
                num_invoices=Count("id"),
            )
            .order_by("-total")
        )

        # ── Ventas del mes ────────────────────────────────────────────────
        sales_invoices = SalesInvoice.objects.filter(
            invoice_date__year=year,
            invoice_date__month=month,
        ).select_related("customer").order_by("invoice_date", "id")

        stotals = sales_invoices.aggregate(
            total_amount=Sum("total_amount"),
            total_paid=Sum("amount_paid"),
            total_pending=Sum("balance_due"),
        )
        total_sold      = stotals.get("total_amount")  or Decimal("0.00")
        total_collected = stotals.get("total_paid")    or Decimal("0.00")
        total_pending   = stotals.get("total_pending") or Decimal("0.00")

        sales_by_customer = (
            sales_invoices
            .values("customer__name")
            .annotate(
                total=Sum("total_amount"),
                paid=Sum("amount_paid"),
                pending=Sum("balance_due"),
                num_invoices=Count("id"),
            )
            .order_by("-total")
        )

        from .models import SalesPayment
        payments_in_period = SalesPayment.objects.filter(
            payment_date__year=year,
            payment_date__month=month,
        ).aggregate(total=Sum("amount"))
        total_payments_received = payments_in_period.get("total") or Decimal("0.00")

        month_name   = MONTHS_ES[month]
        period_label = f"{month_name} {year}"

        context = {
            "mode": "monthly",
            "year": year,
            "month": month,
            "month_name": month_name,
            "period_label": period_label,
            "available_years": available_years,
            "prev_month": prev_month,
            "prev_myear": prev_myear,
            "next_month": next_month,
            "next_myear": next_myear,
            "can_go_next": can_go_next,
            # Compras
            "purchase_invoices": purchase_invoices,
            "purchases_by_supplier": purchases_by_supplier,
            "total_purchased": total_purchased,
            "total_kilos_purchased": total_kilos_purchased,
            "total_freight": total_freight,
            # Ventas
            "sales_invoices": sales_invoices,
            "sales_by_customer": sales_by_customer,
            "total_sold": total_sold,
            "total_collected": total_collected,
            "total_pending": total_pending,
            "total_payments_received": total_payments_received,
            # Balance
            "gross_margin": total_sold - total_purchased,
            # Compartidos
            "months": [(k, v) for k, v in MONTHS_ES.items()],
        }

    return render(request, "core/purchases/period_report.html", context)