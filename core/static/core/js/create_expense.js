document.addEventListener("DOMContentLoaded", function () {

    // ── Formato de pesos ──────────────────────────────────────────────────────

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

    function setupPesosInput(realInput) {
        if (!realInput) return;

        const display = document.createElement("input");
        display.type = "text";
        display.className = realInput.className;
        display.placeholder = "0";

        const initialVal = parseFloat(realInput.value || 0);
        if (initialVal !== 0) display.value = formatPesos(String(initialVal));

        realInput.type = "hidden";
        realInput.insertAdjacentElement("afterend", display);

        display.addEventListener("input", () => {
            const prev   = display.value.length;
            const cursor = display.selectionStart;
            display.value = formatPesos(display.value);
            const diff = display.value.length - prev;
            display.setSelectionRange(Math.max(0, cursor + diff), Math.max(0, cursor + diff));
            realInput.value = parsePesos(display.value);
        });

        display.addEventListener("blur", () => {
            if (!display.value.trim()) realInput.value = "0";
        });
    }

    // ── Toggle campo moto ─────────────────────────────────────────────────────

    const categorySelect   = document.getElementById("id_category");
    const motorcycleField  = document.getElementById("motorcycle-field");
    const motorcycleSelect = document.getElementById("id_motorcycle");

    function toggleMotorcycle() {
        const isFuel = categorySelect.value === "fuel";
        motorcycleField.classList.toggle("hidden", !isFuel);
        if (!isFuel && motorcycleSelect) motorcycleSelect.value = "";
    }

    categorySelect?.addEventListener("change", toggleMotorcycle);
    toggleMotorcycle();

    // ── Inicializar campo amount ───────────────────────────────────────────────

    setupPesosInput(document.getElementById("id_amount"));
});