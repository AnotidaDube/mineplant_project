document.addEventListener("DOMContentLoaded", function () {
    const expectedField = document.getElementById("id_expected_tonnage");
    const tonnageField = document.getElementById("id_tonnage");
    const varianceField = document.getElementById("id_variance");
    const resultDisplay = document.getElementById("break-result");

    if (!expectedField || !tonnageField) {
        console.warn("Production variance script: inputs not found");
        return;
    }

    function updateValues() {
        const expected = parseFloat(expectedField.value);
        const actual = parseFloat(tonnageField.value);

        if (!isNaN(expected) && !isNaN(actual)) {
            const variance = actual - expected;

            // ✅ Update variance field
            if (varianceField) {
                varianceField.value = variance.toFixed(2);
            }

            // ✅ Update break status display
            if (resultDisplay) {
                if (variance > 0) {
                    resultDisplay.textContent = `⚠️ Overbreak (+${variance.toFixed(2)} t) — possible grade dilution.`;
                    resultDisplay.style.color = "orange";
                } else if (variance < 0) {
                    resultDisplay.textContent = `❗ Underbreak (${variance.toFixed(2)} t) — possible loss in tonnage.`;
                    resultDisplay.style.color = "red";
                } else {
                    resultDisplay.textContent = "✅ On Target (0.00 t)";
                    resultDisplay.style.color = "limegreen";
                }
            }
        } else {
            if (varianceField) varianceField.value = "";
            if (resultDisplay) resultDisplay.textContent = "";
        }
    }

    expectedField.addEventListener("input", updateValues);
    tonnageField.addEventListener("input", updateValues);
});
