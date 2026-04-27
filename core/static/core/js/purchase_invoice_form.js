document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("purchase-invoice-form");
    if (!form) return;

    const productsUrl = form.dataset.productsUrl;

    const supplierField = document.getElementById("id_supplier");
    const supplierProductField = document.getElementById("id_supplier_product");
    const weightField = document.getElementById("id_weight_kg");
    const freightField = document.getElementById("id_freight_cost");

    const pricePerKiloField = document.getElementById("price_per_kilo");
    const subtotalField = document.getElementById("subtotal");
    const totalInvoiceField = document.getElementById("total_invoice");

    let supplierProductsMap = {};

    // ─── Formato de pesos ──────────────────────────────────────────────────────

    /**
     * Convierte un número a formato de pesos colombianos para mostrar.
     * Ej: 1400000 → "1.400.000"  /  1400000.50 → "1.400.000,50"
     */
    function formatPesos(raw) {
        // Solo dígitos y coma
        const clean = String(raw).replace(/[^\d,]/g, "");

        // Separar parte entera y decimal por la coma
        const commaIndex = clean.indexOf(",");
        let intPart = commaIndex >= 0 ? clean.slice(0, commaIndex) : clean;
        const decPart = commaIndex >= 0 ? clean.slice(commaIndex + 1) : undefined;

        // Quitar ceros a la izquierda (pero dejar al menos un dígito)
        intPart = intPart.replace(/^0+(\d)/, "$1") || "";

        // Agregar puntos de miles
        const intFormatted = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ".");

        return decPart !== undefined ? `${intFormatted},${decPart}` : intFormatted;
    }

    function parsePesos(formatted) {
        return formatted
            .replace(/\./g, "")
            .replace(",", ".");
    }

    function setupPesosInput(realInput) {
        if (!realInput) return;

        const display = document.createElement("input");
        display.type = "text";
        display.className = realInput.className;
        display.placeholder = "0";
        display.id = realInput.id + "_display";

        // Mostrar valor inicial solo si es distinto de cero
        const initialVal = parseFloat(realInput.value || 0);
        if (initialVal !== 0) {
            display.value = formatPesos(String(initialVal));
        }

        // Ocultar el input real
        realInput.type = "hidden";
        realInput.insertAdjacentElement("afterend", display);

        display.addEventListener("input", () => {
            const prevLen = display.value.length;
            const cursorPos = display.selectionStart;

            const formatted = formatPesos(display.value);
            display.value = formatted;

            // Reposicionar cursor compensando los puntos que se agregaron/quitaron
            const diff = formatted.length - prevLen;
            const newCursor = Math.max(0, cursorPos + diff);
            display.setSelectionRange(newCursor, newCursor);

            realInput.value = parsePesos(formatted) || "0";
            calculateTotals();
        });

        display.addEventListener("blur", () => {
            if (!display.value.trim()) {
                realInput.value = "0";
                calculateTotals();
            }
        });
    }

    // ─── Resumen ───────────────────────────────────────────────────────────────

    function formatCurrency(value) {
        const number = parseFloat(value || 0);
        return new Intl.NumberFormat("es-CO", {
            style: "currency",
            currency: "COP",
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(number);
    }

    function resetSummary() {
        pricePerKiloField.textContent = formatCurrency(0);
        subtotalField.textContent = formatCurrency(0);
        totalInvoiceField.textContent = formatCurrency(0);
    }

    // ─── Mostrar / ocultar campos según tipo de producto ─────────────────────

    const fieldWeightWrapper = document.getElementById("field-weight-kg");
    const fieldBasketWrapper = document.getElementById("field-basket-quantity");
    const fieldBlockWrapper  = document.getElementById("field-block-quantity");
    const labelBasket        = document.getElementById("label-basket-quantity");
    const labelPricePerUnit  = document.getElementById("label-price-per-unit");

    function applyProductFields(product) {
        if (!product) {
            fieldWeightWrapper?.classList.remove("hidden");
            fieldBasketWrapper?.classList.remove("hidden");
            fieldBlockWrapper?.classList.remove("hidden");
            if (labelBasket) labelBasket.textContent = "Total de canastas";
            if (labelPricePerUnit) labelPricePerUnit.textContent = "Valor por kilo";
            return;
        }

        const isPerBlock = product.purchase_pricing_type === "per_block";
        const blockInput = document.getElementById("id_block_quantity");
        const basketInput = document.getElementById("id_basket_quantity");

        if (isPerBlock) {
            // Solo mostrar block_quantity, ocultar el resto
            fieldWeightWrapper?.classList.add("hidden");
            fieldBasketWrapper?.classList.add("hidden");      // ← ocultar canastas
            fieldBlockWrapper?.classList.remove("hidden");    // ← mostrar bloques directamente

            if (blockInput) blockInput.disabled = false;      // ← NO deshabilitar
            if (weightField) weightField.value = "0";
            if (basketInput) basketInput.value = "0";

            if (labelPricePerUnit) labelPricePerUnit.textContent = "Valor por bloque";
        } else {
            // Mostrar todo: kilos, canastas y bloques
            fieldWeightWrapper?.classList.remove("hidden");
            fieldBasketWrapper?.classList.remove("hidden");
            fieldBlockWrapper?.classList.remove("hidden");

            if (blockInput) blockInput.disabled = false;
            if (labelBasket) labelBasket.textContent = "Total de canastas";
            if (labelPricePerUnit) labelPricePerUnit.textContent = "Valor por kilo";
        }
    }

    function calculateTotals() {
        const selectedSupplierProductId = supplierProductField.value;
        const product = supplierProductsMap[selectedSupplierProductId] || null;
        const freight = parseFloat(freightField.value || 0);

        let pricePerUnit = 0;
        let subtotal = 0;

        if (product) {
            pricePerUnit = parseFloat(product.price_per_kilo || 0);
            const isPerBlock = product.purchase_pricing_type === "per_block";

            if (isPerBlock) {
                // Usar directamente block_quantity
                const blocks = parseFloat(
                    document.getElementById("id_block_quantity")?.value || 0
                );
                subtotal = blocks * pricePerUnit;
            } else {
                const weight = parseFloat(weightField.value || 0);
                subtotal = weight * pricePerUnit;
            }
        }

        const totalInvoice = subtotal + freight;
        pricePerKiloField.textContent = formatCurrency(pricePerUnit);
        subtotalField.textContent = formatCurrency(subtotal);
        totalInvoiceField.textContent = formatCurrency(totalInvoice);
    }

    // ─── Productos del proveedor ───────────────────────────────────────────────

    function clearProductOptions() {
        supplierProductField.innerHTML = '<option value="">Selecciona un producto</option>';
        supplierProductsMap = {};
        resetSummary();
    }

    function loadSupplierProducts(supplierId) {
        clearProductOptions();

        if (!supplierId) return;

        fetch(`${productsUrl}?supplier_id=${supplierId}`)
            .then((response) => response.json())
            .then((data) => {
                const products = data.products || [];

                products.forEach((item) => {
                    supplierProductsMap[item.id] = item;

                    const option = document.createElement("option");
                    option.value = item.id;
                    option.textContent = item.name;
                    supplierProductField.appendChild(option);
                });

                // Si ya hay un producto preseleccionado (ej. al recargar con error)
                const selected = supplierProductsMap[supplierProductField.value] || null;
                applyProductFields(selected);
                calculateTotals();
            })
            .catch((error) => {
                console.error("Error loading supplier products:", error);
                clearProductOptions();
            });
    }

    // ─── Listeners ────────────────────────────────────────────────────────────

    if (supplierField) {
        supplierField.addEventListener("change", (event) => {
            loadSupplierProducts(event.target.value);
        });
    }

    if (supplierProductField) {
        supplierProductField.addEventListener("change", () => {
            const product = supplierProductsMap[supplierProductField.value] || null;
            applyProductFields(product);
            calculateTotals();
        });
    }

    if (weightField) {
        weightField.addEventListener("input", calculateTotals);
    }

    // Listener para productos por bloque (cantidad de bloques)
    const basketField = document.getElementById("id_basket_quantity");
    if (basketField) {
        basketField.addEventListener("input", calculateTotals);
    }

    // Agregar junto a los otros listeners al final del archivo
    const blockField = document.getElementById("id_block_quantity");
    if (blockField) {
        blockField.addEventListener("input", calculateTotals);
    }

    // Aplicar el formato de pesos al campo de flete
    setupPesosInput(freightField);

    if (supplierField && supplierField.value) {
        loadSupplierProducts(supplierField.value);
    } else {
        resetSummary();
    }
});