document.addEventListener('DOMContentLoaded', () => {
    const codeInput = document.getElementById('code-input');
    const codeHighlighter = document.getElementById('code-highlighter');
    const tokenStream = document.getElementById('token-stream');
    const bracketLog = document.getElementById('bracket-log');
    const parseTreePanel = document.getElementById('parse-tree');
    const syntaxStatus = document.getElementById('syntax-status');
    
    const symbolTablePanel = document.getElementById('symbol-table');
    const consolePanel = document.getElementById('console-output');
    const languageSelect = document.getElementById('language-select');
    const runBtn = document.getElementById('run-btn');
    
    const statusTokens = document.getElementById('status-tokens');
    const statusErrors = document.getElementById('status-errors');

    // Debounce to prevent spamming the backend
    let timeoutId;
    
    // Sync scrolling between textarea and highlighter
    codeInput.addEventListener('scroll', () => {
        codeHighlighter.scrollTop = codeInput.scrollTop;
        codeHighlighter.scrollLeft = codeInput.scrollLeft;
    });

    codeInput.addEventListener('input', () => {
        // Sync text immediately for responsive typing
        const rawCode = codeInput.value;
        
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => analyzeCode(rawCode), 150); // Fast 150ms debounce
    });
    languageSelect.addEventListener('change', () => {
        analyzeCode(codeInput.value);
    });

    runBtn.addEventListener('click', async () => {
        const code = codeInput.value;
        const lang = languageSelect.value;
        if (!code.trim()) return;
        
        consolePanel.innerHTML = '<div class="console-line">Executing...</div>';
        
        try {
            const res = await fetch('/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code, language: lang })
            });
            const data = await res.json();
            
            let html = '';
            if (data.error) {
                html += `<div class="console-line console-error">${escapeHtml(data.error)}</div>`;
            } else {
                for (let line of data.output) {
                    html += `<div class="console-line console-prompt">${escapeHtml(line)}</div>`;
                }
                html += `<div class="console-line" style="color: #61afef; margin-top: 8px;">Process finished.</div>`;
            }
            consolePanel.innerHTML = html;
            
        } catch(e) {
            consolePanel.innerHTML = `<div class="console-line console-error">Error connecting to interpreter.</div>`;
        }
    });


    async function analyzeCode(code) {
        if (!code.trim()) {
            clearPanels();
            return;
        }

        try {
            const lang = document.getElementById('language-select').value;
            const response = await fetch('/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code, language: lang })
            });
            
            const data = await response.json();
            updateUI(data, code);
        } catch (err) {
            console.error("Analysis failed", err);
        }
    }

    function updateUI(data, rawCode) {
        const { tokens, bracketLogs, errors, ast, syntaxError, semanticErrors, symbolTable } = data;
        
        // Merge semantic errors into bracket log display
        let allLogs = [...bracketLogs];
        let allErrors = [...errors];
        
        if (semanticErrors) {
            for (let e of semanticErrors) {
                allLogs.push({ action: 'SEMANTIC_ERROR', msg: e.message, line: e.line, col: e.col });
                allErrors.push(e);
            }
        }
        
        // Render Symbol Table
        renderSymbolTable(symbolTable);

        
        // 1. Update Syntax Highlighter (Top Right)
        renderHighlighter(tokens, rawCode);
        
        // 2. Update Token Stream (Middle Right)
        renderTokenStream(tokens);
        
        // 3. Update Bracket Log (Bottom)
        renderBracketLog(allLogs, allErrors);
        
        // 4. Update Parse Tree (Middle Left)
        renderParseTree(ast, syntaxError);
        
        // Update Status Bar
        statusTokens.textContent = `Tokens: ${tokens.length}`;
        statusErrors.textContent = `Errors: ${errors.length}`;
        if (errors.length > 0) {
            statusErrors.classList.add('error');
        } else {
            statusErrors.classList.remove('error');
        }
    }

    function renderHighlighter(tokens, rawCode) {
        // We need to rebuild the string with span tags for colors
        // Since tokens don't include all whitespace perfectly in our simple regex,
        // we'll slice the original string based on token start/end index.
        let html = '';
        let lastEnd = 0;
        
        for (const t of tokens) {
            // Add any missing whitespace between tokens
            if (t.start > lastEnd) {
                html += escapeHtml(rawCode.slice(lastEnd, t.start));
            }
            
            html += `<span class="token-${t.type}">${escapeHtml(t.value)}</span>`;
            lastEnd = t.end;
        }
        // Add trailing whitespace
        if (lastEnd < rawCode.length) {
            html += escapeHtml(rawCode.slice(lastEnd));
        }
        
        codeHighlighter.innerHTML = html;
    }

    function renderTokenStream(tokens) {
        if (tokens.length === 0) {
            tokenStream.innerHTML = '<div class="empty-state">No tokens yet...</div>';
            return;
        }
        
        tokenStream.innerHTML = tokens.map(t => {
            if (t.type === 'WHITESPACE') return '';
            return `
                <div class="token-badge" data-type="${t.type}">
                    <span class="type">${t.type}</span>
                    <span class="value">${escapeHtml(t.value)}</span>
                </div>
            `;
        }).join('');
    }

    function renderBracketLog(logs, errors) {
        if (logs.length === 0 && errors.length === 0) {
            bracketLog.innerHTML = '<div class="empty-state">Stack empty...</div>';
            return;
        }
        
        let html = '';
        
        for (const log of logs) {
            let cssClass = '';
            let msg = '';
            
            if (log.action === 'PUSH') {
                cssClass = 'push';
                msg = `Pushed <strong>${log.char}</strong> onto stack`;
            } else if (log.action === 'POP') {
                cssClass = 'pop';
                msg = `Matched <strong>${log.char}</strong> with <strong>${log.matched}</strong>`;
            } else if (log.action === 'MISMATCH') {
                cssClass = 'error';
                msg = log.expected 
                    ? `Mismatch! Expected <strong>${log.expected}</strong> but found <strong>${log.found}</strong>`
                    : `Mismatch! ${log.detail}`;
            } else if (log.action === 'UNCLOSED') {
                cssClass = 'error';
                msg = `Unclosed bracket <strong>${log.char}</strong> remains on stack`;
            } else if (log.action === 'SEMANTIC_ERROR') {
                cssClass = 'error';
                msg = `Semantic Error: <strong>${escapeHtml(log.msg)}</strong>`;
            }
            
            html += `
                <div class="log-entry ${cssClass}">
                    <span class="loc">[Ln ${log.line}, Col ${log.col}]</span>
                    <span class="msg">${msg}</span>
                </div>
            `;
        }
        
        bracketLog.innerHTML = html;
        // Scroll to bottom
        bracketLog.scrollTop = bracketLog.scrollHeight;
    }

    function renderParseTree(ast, syntaxError) {
        if (syntaxError) {
            syntaxStatus.style.display = 'inline-block';
            syntaxStatus.className = 'badge error';
            syntaxStatus.textContent = '❌ Syntax Error';
            // Do not return here, we want to render the partial AST!
        } else if (!ast || !ast.children || ast.children.length === 0) {
            syntaxStatus.style.display = 'none';
            parseTreePanel.innerHTML = '<div class="empty-state">Start typing to build parse tree...</div>';
            return;
        } else {
            syntaxStatus.style.display = 'inline-block';
            syntaxStatus.className = 'badge success';
            syntaxStatus.textContent = '✔️ Syntax Correct';
        }

        function buildTreeHtml(node) {
            if (!node) return '';
            
            let html = `<div class="tree-node animated-node">`;
            let label = node.label ? escapeHtml(node.label) : '';
            
            let labelClass = "tree-label";
            if (node.type === "Error") {
                labelClass += " error-node";
            }
            
            html += `<div class="${labelClass}"><span class="type">${node.type}</span> ${label}</div>`;
            
            if (node.children && node.children.length > 0) {
                html += `<div class="tree-children">`;
                for (const child of node.children) {
                    html += buildTreeHtml(child);
                }
                html += `</div>`;
            }
            html += `</div>`;
            return html;
        }

        parseTreePanel.innerHTML = buildTreeHtml(ast);
        
        // Step-by-step animation trigger
        const animatedNodes = parseTreePanel.querySelectorAll('.animated-node');
        let delay = 0;
        animatedNodes.forEach((node) => {
            setTimeout(() => {
                node.classList.add('node-visible');
            }, delay);
            delay += 50; // 50ms per node for a compiler-like visual
        });
    }

    function clearPanels() {
        codeHighlighter.innerHTML = '';
        tokenStream.innerHTML = '<div class="empty-state">No tokens yet...</div>';
        bracketLog.innerHTML = '<div class="empty-state">Stack empty...</div>';
        parseTreePanel.innerHTML = '<div class="empty-state">Start typing to build parse tree...</div>';
        syntaxStatus.style.display = 'none';
        statusTokens.textContent = 'Tokens: 0';
        statusErrors.textContent = 'Errors: 0';
        statusErrors.classList.remove('error');
    }

    function escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function renderSymbolTable(table) {
        if (!table || table.length === 0) {
            symbolTablePanel.innerHTML = '<div class="empty-state">No symbols declared...</div>';
            return;
        }
        
        let html = '<table class="sym-table"><thead><tr><th>Name</th><th>Type</th><th>Scope</th><th>Value</th></tr></thead><tbody>';
        for (let sym of table) {
            let val = sym.value !== null && sym.value !== undefined ? sym.value : '-';
            html += `<tr>
                <td>${escapeHtml(sym.name)}</td>
                <td><span class="type-badge">${escapeHtml(sym.type)}</span></td>
                <td><span class="scope-badge">${escapeHtml(sym.scope)}</span></td>
                <td>${escapeHtml(String(val))}</td>
            </tr>`;
        }
        html += '</tbody></table>';
        symbolTablePanel.innerHTML = html;
    }
});
