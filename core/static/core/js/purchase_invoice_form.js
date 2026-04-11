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

    function calculateTotals() {
        const selectedSupplierProductId = supplierProductField.value;
        const weight = parseFloat(weightField.value || 0);
        const freight = parseFloat(freightField.value || 0);

        let pricePerKilo = 0;

        if (
            selectedSupplierProductId &&
            supplierProductsMap[selectedSupplierProductId]
        ) {
            pricePerKilo = parseFloat(
                supplierProductsMap[selectedSupplierProductId].price_per_kilo || 0
            );
        }

        const subtotal = weight * pricePerKilo;
        const totalInvoice = subtotal + freight;

        pricePerKiloField.textContent = formatCurrency(pricePerKilo);
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
        supplierProductField.addEventListener("change", calculateTotals);
    }

    if (weightField) {
        weightField.addEventListener("input", calculateTotals);
    }

    // Aplicar el formato de pesos al campo de flete
    setupPesosInput(freightField);

    if (supplierField && supplierField.value) {
        loadSupplierProducts(supplierField.value);
    } else {
        resetSummary();
    }
});