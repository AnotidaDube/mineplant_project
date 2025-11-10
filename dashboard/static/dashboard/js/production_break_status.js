document.addEventListener("DOMContentLoaded", function () {
    const expectedInput = document.querySelector("#id_expected_tonnage");
    const actualInput = document.querySelector("#id_tonnage");
    const resultDisplay = document.querySelector("#break-result");

    if (!expectedInput || !actualInput || !resultDisplay) {
        console.warn("Production Overbreak/Underbreak script: inputs not found");
        return;
    }

    function updateBreakStatus() {
        const expected = parseFloat(expectedInput.value);
        const actual = parseFloat(actualInput.value);

        if (!isNaN(expected) && !isNaN(actual)) {
            const diff = actual - expected;
            if (diff > 0) {
                resultDisplay.textContent = `⚠️ Overbreak (+${diff.toFixed(2)} t) — possible grade dilution.`;
                resultDisplay.style.color = "orange";
            } else if (diff < 0) {
                resultDisplay.textContent = `❗ Underbreak (${diff.toFixed(2)} t) — possible loss in tonnage.`;
                resultDisplay.style.color = "red";
            } else {
                resultDisplay.textContent = "✅ On Target (0.00 t)";
                resultDisplay.style.color = "limegreen";
            }
        } else {
            resultDisplay.textContent = "";
        }
    }

    expectedInput.addEventListener("input", updateBreakStatus);
    actualInput.addEventListener("input", updateBreakStatus);
});
