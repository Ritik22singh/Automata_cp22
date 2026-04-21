function generate(){
    const regexInput = document.getElementById("regexInput");
    const regex = regexInput.value.trim();

    if (!regex) {
        alert("Please enter a valid regular expression.");
        regexInput.focus();
        return;
    }

    const generateBtn = document.getElementById("generateBtn");
    const btnText = document.querySelector(".btn-text");
    const loader = document.querySelector(".loader");
    const resultsSection = document.getElementById("resultsSection");

    // UI State Loading
    generateBtn.disabled = true;
    btnText.classList.add("hidden");
    loader.classList.remove("hidden");
    resultsSection.classList.add("hidden");

    fetch("/convert", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            regex: regex
        })
    })
    .then(res => {
        if (!res.ok) {
            throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
    })
    .then(data => {
        // Appending timestamp to avoid caching issues when generating multiple times
        document.getElementById("nfa").src = data.nfa + "?t=" + new Date().getTime();
        document.getElementById("dfa").src = data.dfa + "?t=" + new Date().getTime();
        document.getElementById("mindfa").src = data.mindfa + "?t=" + new Date().getTime();

        // Update UI State Finished
        resultsSection.classList.remove("hidden");
        generateBtn.disabled = false;
        btnText.classList.remove("hidden");
        loader.classList.add("hidden");

        // Make sure NFA is shown by default as that's the default checked toggle
        document.getElementById('nfa-toggle').checked = true;
        switchDiagram('nfa');
    })
    .catch(error => {
        console.error('Error generating automata:', error);
        alert("An error occurred while generating diagrams. Please try again.");
        generateBtn.disabled = false;
        btnText.classList.remove("hidden");
        loader.classList.add("hidden");
    });
}

function switchDiagram(type) {
    // Hide all containers
    const containers = document.querySelectorAll('.diagram-container');
    containers.forEach(container => {
        container.classList.remove('active');
    });

    // Show the selected container
    const selectedContainer = document.getElementById(`${type}-container`);
    if (selectedContainer) {
        selectedContainer.classList.add('active');
    }
}

// Add enter key support
document.getElementById('regexInput').addEventListener('keypress', function (e) {
    if (e.key === 'Enter') {
        generate();
    }
});

// ==========================================
// APP MODE SWITCHER (REGEX vs CFG)
// ==========================================
function switchAppMode(mode) {
    const regexApp = document.getElementById('app-regex');
    const cfgApp = document.getElementById('app-cfg');
    
    if (mode === 'regex') {
        regexApp.classList.remove('hidden');
        regexApp.classList.add('active');
        
        cfgApp.classList.add('hidden');
        cfgApp.classList.remove('active');
    } else {
        cfgApp.classList.remove('hidden');
        cfgApp.classList.add('active');
        
        regexApp.classList.add('hidden');
        regexApp.classList.remove('active');
    }
}

// ==========================================
// CFG SIMPLIFIER LOGIC
// ==========================================
function simplifyCFG() {
    const cfgInput = document.getElementById("cfgInput");
    const grammar = cfgInput.value.trim();

    if (!grammar) {
        alert("Please enter a Context-Free Grammar.");
        cfgInput.focus();
        return;
    }

    const simplifyBtn = document.getElementById("simplifyBtn");
    const btnText = simplifyBtn.querySelector(".btn-text");
    const loader = simplifyBtn.querySelector(".loader");
    const resultsSection = document.getElementById("cfgResultsSection");

    // UI Loading State
    simplifyBtn.disabled = true;
    btnText.classList.add("hidden");
    loader.classList.remove("hidden");
    resultsSection.classList.add("hidden");
    resultsSection.innerHTML = ""; // Clear old results

    fetch("/simplify_cfg", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            grammar: grammar
        })
    })
    .then(res => {
        if (!res.ok) {
            throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
    })
    .then(data => {
        if (!data.success) {
            alert("Failed to parse or simplify grammar: " + data.error);
            resetCFGButton();
            return;
        }

        // Generate Steps Cards Dynamically
        let htmlContent = "";
        
        // Add Derivation Result if applicable (at the top)
        if (data.derivation) {
            const isValid = data.derivation.valid;
            htmlContent += `
            <div class="step-card derivation-result ${isValid ? 'valid' : 'invalid'}" style="animation-delay: 0s; border-left: 5px solid ${isValid ? '#10b981' : '#ef4444'}">
                <h4>🔍 Sequence Derivation Check</h4>
                <p>Sequence: <code style="background: rgba(0,0,0,0.2); padding: 2px 5px; border-radius: 4px;">${data.derivation.sequence || "(empty)"}</code></p>
                <div class="status-badge" style="margin-top: 10px; font-weight: bold; color: ${isValid ? '#10b981' : '#ef4444'}">
                    ${isValid ? '✅ ACCEPTED' : '❌ REJECTED'}
                </div>
                <p style="font-size: 0.9rem; opacity: 0.8; margin-top: 5px;">${data.derivation.message}</p>
            </div>
            `;
        }

        data.steps.forEach((step, index) => {
            htmlContent += `
            <div class="step-card" style="animation-delay: ${(index + 1) * 0.15}s">
                <h4>${step.title}</h4>
                <pre>${step.grammar || "No productions"}</pre>
            </div>
            `;
        });

        // Add Final Output Card
        htmlContent += `
        <div class="step-card final-result" style="animation-delay: ${(data.steps.length + 1) * 0.15}s">
            <h4>✨ Final Simplified Grammar</h4>
            <pre>${data.final || "No productions"}</pre>
        </div>
        `;

        resultsSection.innerHTML = htmlContent;

        // Reveal Results
        resultsSection.classList.remove("hidden");
        resetCFGButton();
    })
    .catch(error => {
        console.error('Error simplifying CFG:', error);
        alert("An error occurred while simplifying. Please check formatting.");
        resetCFGButton();
    });
}

function resetCFGButton() {
    const simplifyBtn = document.getElementById("simplifyBtn");
    const btnText = simplifyBtn.querySelector(".btn-text");
    const loader = simplifyBtn.querySelector(".loader");
    
    simplifyBtn.disabled = false;
    btnText.classList.remove("hidden");
    loader.classList.add("hidden");
}