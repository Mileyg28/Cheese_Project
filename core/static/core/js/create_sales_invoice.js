document.addEventListener("DOMContentLoaded", function () {

    const form       = document.getElementById("sales-invoice-form");
    const container  = document.getElementById("items-container");
    const addBtn     = document.getElementById("add-item-btn");
    const totalFormInput = document.querySelector("[name=items-TOTAL_FORMS]");
    const grandTotalEl   = document.getElementById("invoice-grand-total");

    const PRICING = typeof PRODUCTS_DATA !== "undefined" ? PRODUCTS_DATA : {};

    // ─── Modal de confirmación ─────────────────────────────────────────────────

    function createConfirmModal() {
        const overlay = document.createElement("div");
        overlay.id = "confirm-modal";
        overlay.className = [
            "fixed inset-0 z-50 flex items-center justify-center",
            "bg-black bg-opacity-40"
        ].join(" ");

        overlay.innerHTML = `
            <div class="bg-white rounded-2xl shadow-xl p-6 max-w-sm w-full mx-4">
                <h3 class="text-lg font-bold text-gray-800 mb-2">¿Confirmar factura?</h3>
                <p class="text-gray-600 text-sm mb-1">
                    Estás a punto de guardar la factura. Verifica que los datos sean correctos.
                </p>
                <p id="modal-total-summary" class="text-blue-700 font-bold text-xl mt-3 mb-5"></p>
                <div class="flex gap-3 justify-end">
                    <button id="modal-cancel"
                        class="px-4 py-2 rounded-xl border-2 border-gray-300 text-gray-700 font-medium hover:bg-gray-50">
                        Revisar
                    </button>
                    <button id="modal-confirm"
                        class="px-5 py-2 rounded-xl bg-blue-600 text-white font-semibold hover:bg-blue-700">
                        Sí, guardar
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);

        document.getElementById("modal-cancel").addEventListener("click", () => {
            overlay.remove();
        });

        document.getElementById("modal-confirm").addEventListener("click", () => {
            overlay.remove();
            form.submit();
        });
    }

    // ─── Mostrar error en un campo ─────────────────────────────────────────────

    function setFieldError(wrapper, message) {
        clearFieldError(wrapper);
        wrapper.classList.add("field-error");

        const input = wrapper.querySelector("input, select");
        if (input) input.classList.add("border-red-500");

        const err = document.createElement("p");
        err.className = "field-error-msg text-red-500 text-xs mt-1";
        err.textContent = message;
        wrapper.appendChild(err);
    }

    function clearFieldError(wrapper) {
        wrapper.classList.remove("field-error");
        wrapper.querySelector(".field-error-msg")?.remove();
        const input = wrapper.querySelector("input, select");
        if (input) input.classList.remove("border-red-500");
    }

    function clearAllErrors() {
        document.querySelectorAll(".field-error-msg").forEach(el => el.remove());
        document.querySelectorAll(".field-error").forEach(el => el.classList.remove("field-error"));
        document.querySelectorAll(".border-red-500").forEach(el => el.classList.remove("border-red-500"));
        document.getElementById("form-error-banner")?.remove();
    }

    function showErrorBanner(message) {
        document.getElementById("form-error-banner")?.remove();
        const banner = document.createElement("div");
        banner.id = "form-error-banner";
        banner.className = "bg-red-50 border-2 border-red-300 text-red-700 rounded-xl p-3 text-sm mb-4";
        banner.textContent = message;
        form.prepend(banner);
        banner.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    // ─── Validación del formulario ─────────────────────────────────────────────

    function validateForm() {
        clearAllErrors();
        let valid = true;
        const errors = [];

        // Validar cabecera de la factura
        const invoiceNumber = document.querySelector("[name=invoice_number]");
        const customer      = document.querySelector("[name=customer]");
        const invoiceDate   = document.querySelector("[name=invoice_date]");

        if (!invoiceNumber?.value.trim()) {
            setFieldError(invoiceNumber.closest("div"), "El número de factura es obligatorio.");
            errors.push("N° de factura");
            valid = false;
        }
        if (!customer?.value) {
            setFieldError(customer.closest("div"), "Debes seleccionar un cliente.");
            errors.push("Cliente");
            valid = false;
        }
        if (!invoiceDate?.value) {
            setFieldError(invoiceDate.closest("div"), "La fecha es obligatoria.");
            errors.push('Fecha');
            valid = false;
        }

        // Validar cada fila de producto
        const rows = container.querySelectorAll(".item-row");
        rows.forEach((row, i) => {
            const productSelect  = row.querySelector("[name$='-product']");
            const weightInput    = row.querySelector("[name$='-weight_kg']");
            const blocksInput    = row.querySelector("[name$='-blocks']");
            const priceInput     = row.querySelector("[name$='-unit_price']");
            const productInfo    = PRICING[productSelect?.value] || null;

            const rowLabel = rows.length > 1 ? ` (fila ${i + 1})` : "";

            if (!productSelect?.value) {
                setFieldError(productSelect.closest("div"), `Selecciona un producto${rowLabel}.`);
                valid = false;
                return; // no validar el resto de esta fila
            }

            if (productInfo?.requires_weight) {
                const weight = parseFloat(weightInput?.value || 0);
                if (!weight || weight <= 0) {
                    setFieldError(weightInput.closest("div"), `El peso es obligatorio${rowLabel}.`);
                    valid = false;
                }
            }

            if (productInfo?.requires_blocks) {
                const blocks = parseInt(blocksInput?.value || 0);
                if (!blocks || blocks <= 0) {
                    setFieldError(blocksInput.closest("div"), `Los bloques son obligatorios${rowLabel}.`);
                    valid = false;
                }
            }

            const price = parseFloat(priceInput?.value || 0);
            if (!price || price <= 0) {
                const priceWrapper = priceInput?.closest(".field-price");
                if (priceWrapper) {
                    setFieldError(priceWrapper, `El precio unitario es obligatorio${rowLabel}.`);
                }
                valid = false;
            }
        });

        if (!valid) {
            showErrorBanner("Corrige los campos marcados antes de guardar.");
        }

        return valid;
    }

    // ─── Solo números en campos numéricos ─────────────────────────────────────

    function enforceNumbersOnly(input, allowDecimals = true) {
        if (!input) return;

        input.addEventListener("keypress", (e) => {
            const char = String.fromCharCode(e.which);
            const allowed = allowDecimals ? /[\d.,]/ : /\d/;
            if (!allowed.test(char)) {
                e.preventDefault();
            }
            // Solo una coma decimal
            if ((char === "," || char === ".") && input.value.includes(",")) {
                e.preventDefault();
            }
        });

        input.addEventListener("paste", (e) => {
            const pasted = e.clipboardData.getData("text");
            if (allowDecimals ? !/^\d+([.,]\d*)?$/.test(pasted) : !/^\d+$/.test(pasted)) {
                e.preventDefault();
            }
        });
    }

    // ─── Formato de pesos ──────────────────────────────────────────────────────

    function formatPesos(raw) {
        const clean = String(raw).replace(/[^\d,]/g, "");
        const commaIndex = clean.indexOf(",");
        let intPart = commaIndex >= 0 ? clean.slice(0, commaIndex) : clean;
        const decPart = commaIndex >= 0 ? clean.slice(commaIndex + 1) : undefined;
        intPart = intPart.replace(/^0+(\d)/, "$1") || "";
        const intFormatted = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
        return decPart !== undefined ? `${intFormatted},${decPart}` : intFormatted;
    }

    function parsePesos(formatted) {
        return formatted.replace(/\./g, "").replace(",", ".") || "0";
    }

    function formatCurrency(value) {
        return new Intl.NumberFormat("es-CO", {
            style: "currency",
            currency: "COP",
            minimumFractionDigits: 0,
            maximumFractionDigits: 0,
        }).format(Number(value || 0));
    }

    function setupPesosInput(realInput) {
        if (!realInput || realInput.dataset.pesosSetup) return;
        realInput.dataset.pesosSetup = "true";

        const display = document.createElement("input");
        display.type = "text";
        display.className = realInput.className;
        display.placeholder = "0";
        enforceNumbersOnly(display, true);

        const initialVal = parseFloat(realInput.value || 0);
        if (initialVal !== 0) display.value = formatPesos(String(initialVal));

        realInput.type = "hidden";
        realInput.insertAdjacentElement("afterend", display);

        display.addEventListener("input", () => {
            const prevLen = display.value.length;
            const cursorPos = display.selectionStart;
            const formatted = formatPesos(display.value);
            display.value = formatted;
            const diff = formatted.length - prevLen;
            display.setSelectionRange(Math.max(0, cursorPos + diff), Math.max(0, cursorPos + diff));
            realInput.value = parsePesos(formatted);
            recalculateRow(realInput.closest(".item-row"));
            recalculateGrandTotal();
        });

        display.addEventListener("blur", () => {
            if (!display.value.trim()) {
                realInput.value = "0";
                recalculateRow(realInput.closest(".item-row"));
                recalculateGrandTotal();
            }
        });
    }

    // ─── Auto-calcular bloques según el peso ──────────────────────────────────

    function autoCalculateBlocks(row, productInfo) {
        if (!productInfo?.requires_blocks || !productInfo?.requires_weight) return;
        if (!productInfo?.kg_per_block) return;

        const weightInput = row.querySelector("[name$='-weight_kg']");
        const blocksInput = row.querySelector("[name$='-blocks']");
        if (!weightInput || !blocksInput) return;

        const weight = parseFloat(weightInput.value || 0);
        if (weight <= 0) { blocksInput.value = ""; return; }

        blocksInput.value = Math.max(1, Math.round(weight / productInfo.kg_per_block));
    }

    // ─── Mostrar / ocultar campos según el producto ───────────────────────────

    function applyProductFields(row, productInfo) {
        const blocksWrapper = row.querySelector(".field-blocks");
        const weightWrapper = row.querySelector(".field-weight");
        const priceWrappers = row.querySelectorAll(".field-price");
        const blocksInput   = row.querySelector("[name$='-blocks']");
        const weightInput   = row.querySelector("[name$='-weight_kg']");

        blocksWrapper?.classList.add("hidden");
        weightWrapper?.classList.add("hidden");
        priceWrappers.forEach(el => el.classList.add("hidden"));

        if (!productInfo) {
            if (blocksInput) blocksInput.value = "";
            if (weightInput) weightInput.value = "";
            recalculateRow(row);
            recalculateGrandTotal();
            return;
        }

        priceWrappers.forEach(el => el.classList.remove("hidden"));

        if (productInfo.requires_weight) {
            weightWrapper?.classList.remove("hidden");
        } else {
            if (weightInput) weightInput.value = "";
        }

        if (productInfo.requires_blocks) {
            blocksWrapper?.classList.remove("hidden");
            if (productInfo.requires_weight && productInfo.kg_per_block) {
                // Se calcula solo: mantener readonly
                if (blocksInput) {
                    blocksInput.readOnly = true;
                    blocksInput.classList.add("bg-slate-100", "cursor-not-allowed", "text-slate-500");
                }
                const label = blocksWrapper?.querySelector("label");
                if (label && !label.dataset.originalText) {
                    label.dataset.originalText = label.textContent;
                    label.textContent = `Bloques (≈ ${productInfo.kg_per_block} kg c/u)`;
                }
            } else {
                // Se ingresa manual: permitir edición
                if (blocksInput) {
                    blocksInput.readOnly = false;
                    blocksInput.classList.remove("bg-slate-100", "cursor-not-allowed", "text-slate-500");
                }
            }
        } else {
            if (blocksInput) blocksInput.value = "";
        }

        recalculateRow(row);
        recalculateGrandTotal();
    }

    // ─── Calcular total fila y gran total ─────────────────────────────────────

    function recalculateRow(row) {
        if (!row) return;
        const productSelect = row.querySelector("[name$='-product']");
        const productInfo   = PRICING[productSelect?.value] || null;
        const blocks = parseFloat(row.querySelector("[name$='-blocks']")?.value || 0);
        const weight = parseFloat(row.querySelector("[name$='-weight_kg']")?.value || 0);
        const price  = parseFloat(row.querySelector("[name$='-unit_price']")?.value || 0);

        let total = 0;
        if (productInfo?.pricing_type === "per_kg")    total = weight * price;
        if (productInfo?.pricing_type === "per_block") total = blocks * price;

        const rowTotalEl = row.querySelector(".row-total");
        if (rowTotalEl) rowTotalEl.textContent = formatCurrency(total);
    }

    function recalculateGrandTotal() {
        let grand = 0;
        container.querySelectorAll(".item-row").forEach(row => {
            const productSelect = row.querySelector("[name$='-product']");
            const productInfo   = PRICING[productSelect?.value] || null;
            const blocks = parseFloat(row.querySelector("[name$='-blocks']")?.value || 0);
            const weight = parseFloat(row.querySelector("[name$='-weight_kg']")?.value || 0);
            const price  = parseFloat(row.querySelector("[name$='-unit_price']")?.value || 0);
            if (productInfo?.pricing_type === "per_kg")    grand += weight * price;
            if (productInfo?.pricing_type === "per_block") grand += blocks * price;
        });
        if (grandTotalEl) grandTotalEl.textContent = formatCurrency(grand);
        return grand;
    }

    // ─── Inicializar una fila ─────────────────────────────────────────────────

    function initRow(row) {
        const productSelect = row.querySelector("[name$='-product']");
        const priceInput    = row.querySelector("[name$='-unit_price']");
        const weightInput   = row.querySelector("[name$='-weight_kg']");
        const blocksInput   = row.querySelector("[name$='-blocks']");

        if (priceInput) setupPesosInput(priceInput);

        // Solo números enteros en bloques y peso
        enforceNumbersOnly(weightInput, true);
        enforceNumbersOnly(blocksInput, false);

        // Bloques: readonly si se calcula automáticamente desde el peso
        if (blocksInput) {
            blocksInput.readOnly = true;
            blocksInput.classList.add("bg-slate-100", "cursor-not-allowed", "text-slate-500");
        }

        if (productSelect) {
            applyProductFields(row, PRICING[productSelect.value] || null);

            productSelect.addEventListener("change", () => {
                const wi = row.querySelector("[name$='-weight_kg']");
                const bi = row.querySelector("[name$='-blocks']");
                if (wi) wi.value = "";
                if (bi) bi.value = "";

                const label = row.querySelector(".field-blocks label");
                if (label?.dataset.originalText) {
                    label.textContent = label.dataset.originalText;
                    delete label.dataset.originalText;
                }

                applyProductFields(row, PRICING[productSelect.value] || null);
            });
        }

        if (weightInput) {
            weightInput.addEventListener("input", () => {
                const productInfo = PRICING[productSelect?.value] || null;
                autoCalculateBlocks(row, productInfo);
                recalculateRow(row);
                recalculateGrandTotal();
            });
        }

        blocksInput?.addEventListener("input", () => {
            recalculateRow(row);
            recalculateGrandTotal();
        });

        row.querySelector(".remove-item-btn")?.addEventListener("click", () => {
            if (container.querySelectorAll(".item-row").length > 1) {
                row.remove();
                renumberForms();
                recalculateGrandTotal();
            } else {
                alert("La factura debe tener al menos un producto.");
            }
        });
    }

    // ─── Renumerar formset ────────────────────────────────────────────────────

    function renumberForms() {
        container.querySelectorAll(".item-row").forEach((row, index) => {
            row.querySelectorAll("input, select, textarea").forEach(el => {
                ["name", "id"].forEach(attr => {
                    const val = el.getAttribute(attr);
                    if (val) el.setAttribute(attr, val.replace(/items-\d+-/, `items-${index}-`));
                });
            });
        });
        if (totalFormInput) totalFormInput.value = container.querySelectorAll(".item-row").length;
    }

    // ─── Clonar nueva fila ────────────────────────────────────────────────────

    function addNewRow() {
        const index = container.querySelectorAll(".item-row").length;
        const newRow = container.querySelector(".item-row").cloneNode(true);

        newRow.querySelectorAll("input, select, textarea").forEach(el => {
            ["name", "id"].forEach(attr => {
                const val = el.getAttribute(attr);
                if (val) el.setAttribute(attr, val.replace(/items-\d+-/, `items-${index}-`));
            });
            if (el.type !== "hidden") el.value = "";
            if (el.tagName === "SELECT") el.selectedIndex = 0;
        });

        newRow.querySelectorAll("input[type=text]:not([name])").forEach(el => el.remove());
        newRow.querySelectorAll("[data-pesos-setup]").forEach(el => {
            el.removeAttribute("data-pesos-setup");
            el.type = "number";
        });

        const label = newRow.querySelector(".field-blocks label");
        if (label?.dataset.originalText) {
            label.textContent = label.dataset.originalText;
            delete label.dataset.originalText;
        }

        newRow.querySelector(".field-blocks")?.classList.add("hidden");
        newRow.querySelector(".field-weight")?.classList.add("hidden");
        newRow.querySelectorAll(".field-price").forEach(el => el.classList.add("hidden"));
        newRow.querySelector(".row-total") && (newRow.querySelector(".row-total").textContent = "$0");

        // Limpiar errores de la fila clonada
        newRow.querySelectorAll(".field-error-msg").forEach(el => el.remove());
        newRow.querySelectorAll(".border-red-500").forEach(el => el.classList.remove("border-red-500"));

        container.appendChild(newRow);
        if (totalFormInput) totalFormInput.value = index + 1;
        initRow(newRow);
    }

    // ─── Interceptar envío del formulario ────────────────────────────────────

    form?.addEventListener("submit", (e) => {
        e.preventDefault();

        if (!validateForm()) return;

        // Mostrar modal con el total actual
        const grand = recalculateGrandTotal();
        createConfirmModal();
        document.getElementById("modal-total-summary").textContent =
            `Total a guardar: ${formatCurrency(grand)}`;
    });

    // ─── Arranque ─────────────────────────────────────────────────────────────

    container.querySelectorAll(".item-row").forEach(row => initRow(row));
    recalculateGrandTotal();
    if (addBtn) addBtn.addEventListener("click", addNewRow);
});