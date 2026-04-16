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