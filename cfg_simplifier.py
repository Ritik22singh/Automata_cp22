import copy

class CFGSimplifier:
    def __init__(self, raw_grammar_str):
        self.raw_grammar = raw_grammar_str
        self.grammar, self.sequence = self.parse_input(raw_grammar_str)
        self.start_symbol = list(self.grammar.keys())[0] if self.grammar else "S"
        self.steps_output = []

    # ==========================================
    # PARSING
    # ==========================================

    def parse_input(self, input_str):
        """Parse grammar rules and an optional test sequence at the end."""
        # Normalise arrow variants
        for arrow in ('→', '⇒', '-->'):
            input_str = input_str.replace(arrow, '->')

        lines = input_str.strip().split('\n')
        grammar   = {}
        sequence  = None
        rule_lines  = []
        other_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if '->' in line:
                rule_lines.append(line)
            else:
                other_lines.append(line)

        if other_lines:
            sequence = other_lines[-1]

        for line in rule_lines:
            left, right = line.split('->', 1)
            left = left.strip()
            alternatives = [p.strip() for p in right.split('|')]

            grammar_prods = []
            for p in alternatives:
                if p in ('ε', 'e', '') or p.lower() == 'epsilon':
                    grammar_prods.append(['ε'])
                else:
                    tokens = p.split()
                    if not tokens:
                        grammar_prods.append(['ε'])
                    else:
                        # Split tokens that mix uppercase+lowercase chars
                        # e.g. "aB" → ['a','B'],  "AB" → ['A','B'],  "ab" → ['a','b']
                        refined = []
                        for t in tokens:
                            if len(t) > 1:
                                # split every character individually
                                for ch in t:
                                    refined.append(ch)
                            else:
                                refined.append(t)
                        grammar_prods.append(refined)

            if left not in grammar:
                grammar[left] = []
            grammar[left].extend(grammar_prods)

        return grammar, sequence

    def format_grammar(self, grammar):
        """Return a human-readable multi-line grammar string."""
        lines = []
        for A, prods in grammar.items():
            if not prods:
                continue
            rhs = [' '.join(p) for p in prods]
            lines.append(f"{A} -> {' | '.join(rhs)}")
        return '\n'.join(lines)

    # ==========================================
    # RULE 1A – REMOVE NON-GENERATING SYMBOLS
    # ==========================================

    def remove_non_generating(self, grammar):
        """Remove variables that cannot derive any terminal string."""
        non_terminals = set(grammar.keys())   # ← uses CURRENT grammar, not self.grammar
        generating    = set()

        changed = True
        while changed:
            changed = False
            for A, prods in grammar.items():
                if A in generating:
                    continue
                for prod in prods:
                    # ε itself is a valid terminal string
                    if prod == ['ε']:
                        if A not in generating:
                            generating.add(A)
                            changed = True
                        break
                    # All symbols must be terminals OR already generating NTs
                    if all(X not in non_terminals or X in generating for X in prod):
                        if A not in generating:
                            generating.add(A)
                            changed = True
                        break

        new_grammar = {}
        for A in generating:
            if A not in grammar:
                continue
            new_prods = [
                prod for prod in grammar[A]
                if prod == ['ε'] or
                   all(X not in non_terminals or X in generating for X in prod)
            ]
            if new_prods:
                new_grammar[A] = new_prods

        return new_grammar

    # ==========================================
    # RULE 1B – REMOVE NON-REACHABLE SYMBOLS
    # ==========================================

    def remove_unreachable(self, grammar, start):
        """Remove variables not reachable from the start symbol."""
        if start not in grammar:
            return {}

        non_terminals = set(grammar.keys())   # ← uses CURRENT grammar
        reachable = {start}

        changed = True
        while changed:
            changed = False
            for A in list(reachable):
                for prod in grammar.get(A, []):
                    for X in prod:
                        if X in non_terminals and X not in reachable:
                            reachable.add(X)
                            changed = True

        return {A: grammar[A] for A in reachable if A in grammar}

    # ==========================================
    # RULE 2 – REMOVE ε-PRODUCTIONS
    # ==========================================

    def remove_epsilon(self, grammar):
        """Remove ε-productions, keeping S → ε only if S is nullable."""
        non_terminals = set(grammar.keys())
        nullable = set()

        # Find all nullable variables
        changed = True
        while changed:
            changed = False
            for A, prods in grammar.items():
                if A in nullable:
                    continue
                for prod in prods:
                    if prod == ['ε']:
                        nullable.add(A); changed = True; break
                    # A non-empty production where every symbol is nullable
                    if prod and all(X in nullable for X in prod):
                        nullable.add(A); changed = True; break

        new_grammar = {}
        for A, prods in grammar.items():
            new_prods = set()
            for prod in prods:
                if prod == ['ε']:
                    continue   # strip ε-productions (re-add for start below)

                # Generate every subset by optionally omitting nullable symbols
                # Use tuples to allow hashing in a set
                subsets = [()]
                for X in prod:
                    if X in nullable:
                        subsets = [s + (X,) for s in subsets] + list(subsets)
                    else:
                        subsets = [s + (X,) for s in subsets]

                for p in subsets:
                    if p:                  # discard the empty combination
                        new_prods.add(p)

            new_grammar[A] = [list(p) for p in new_prods]

        # Special case: keep S → ε if start symbol was nullable
        if self.start_symbol in nullable:
            if self.start_symbol not in new_grammar:
                new_grammar[self.start_symbol] = []
            if ['ε'] not in new_grammar[self.start_symbol]:
                new_grammar[self.start_symbol].append(['ε'])

        return {A: prods for A, prods in new_grammar.items()
                if prods or A == self.start_symbol}

    # ==========================================
    # RULE 3 – REMOVE UNIT PRODUCTIONS
    # ==========================================

    def remove_unit(self, grammar):
        """Remove unit productions A → B using the unit-pair closure."""
        non_terminals = set(grammar.keys())   # ← uses CURRENT grammar

        # Initialise with reflexive pairs (A, A)
        unit = {(A, A) for A in grammar}

        # Add direct unit pairs and compute transitive closure
        changed = True
        while changed:
            changed = False

            # Direct: A → B where B is a non-terminal
            for A, prods in grammar.items():
                for prod in prods:
                    if len(prod) == 1 and prod[0] in non_terminals:
                        B = prod[0]
                        if (A, B) not in unit:
                            unit.add((A, B))
                            changed = True

            # Transitive closure: (A,B) ∧ (B,C) ⟹ (A,C)
            new_pairs = set()
            for (A, B) in unit:
                for (B2, C) in unit:
                    if B == B2 and (A, C) not in unit:
                        new_pairs.add((A, C))
            if new_pairs - unit:
                unit |= new_pairs
                changed = True

        # For each unit pair (A, B), copy B's non-unit productions to A
        new_grammar = {A: [] for A in grammar}
        for (A, B) in unit:
            if B not in grammar:
                continue
            for prod in grammar[B]:
                if len(prod) == 1 and prod[0] in non_terminals:
                    continue   # skip unit productions
                if prod not in new_grammar[A]:
                    new_grammar[A].append(prod)

        return {A: prods for A, prods in new_grammar.items() if prods}

    # ==========================================
    # CNF CONVERSION (for CYK)
    # ==========================================

    def to_cnf(self, grammar):
        """Convert a simplified grammar (no ε, no units) to Chomsky Normal Form."""
        non_terminals = set(grammar.keys())   # ← uses CURRENT grammar
        term_map  = {}
        counter   = [0]
        new_grammar = {}

        def fresh_nt(prefix):
            name = f"{prefix}_{counter[0]}"
            counter[0] += 1
            return name

        # Step 1: Replace terminals in long/binary productions with helper NTs
        for A, prods in grammar.items():
            new_grammar.setdefault(A, [])
            for prod in prods:
                if len(prod) == 1:
                    new_grammar[A].append(prod)
                else:
                    new_prod = []
                    for sym in prod:
                        if sym not in non_terminals:
                            if sym not in term_map:
                                nt = fresh_nt(f"T{sym}")
                                term_map[sym] = nt
                                new_grammar[nt] = [[sym]]
                            new_prod.append(term_map[sym])
                        else:
                            new_prod.append(sym)
                    new_grammar[A].append(new_prod)

        # Step 2: Break productions longer than 2 into binary rules
        final = {}
        for A, prods in new_grammar.items():
            final.setdefault(A, [])
            for prod in prods:
                if len(prod) <= 2:
                    if prod not in final[A]:
                        final[A].append(prod)
                else:
                    curr = A
                    for i in range(len(prod) - 2):
                        nxt = fresh_nt("X")
                        final.setdefault(curr, [])
                        final[curr].append([prod[i], nxt])
                        curr = nxt
                    final.setdefault(curr, [])
                    final[curr].append([prod[-2], prod[-1]])

        return final

    # ==========================================
    # CYK STRING MEMBERSHIP CHECK
    # ==========================================

    def check_sequence(self, sequence_str):
        """Check whether sequence_str is generated by the grammar using CYK."""
        # Deep-copy: never mutate self.grammar
        g = copy.deepcopy(self.grammar)

        # Full simplification pipeline before converting to CNF
        g = self.remove_non_generating(g)
        g = self.remove_unreachable(g, self.start_symbol)
        g = self.remove_epsilon(g)
        g = self.remove_unreachable(g, self.start_symbol)
        g = self.remove_unit(g)
        g = self.remove_non_generating(g)
        g = self.remove_unreachable(g, self.start_symbol)

        cnf_g = self.to_cnf(g)

        tokens = sequence_str.strip().split()
        n = len(tokens)

        if n == 0:
            return (['ε'] in g.get(self.start_symbol, []) or
                    ['ε'] in self.grammar.get(self.start_symbol, []))

        # CYK table: table[length-1][start_pos] = set of NTs that derive that span
        table = [[set() for _ in range(n)] for _ in range(n)]

        for i in range(n):
            for A, prods in cnf_g.items():
                for prod in prods:
                    if len(prod) == 1 and prod[0] == tokens[i]:
                        table[0][i].add(A)

        for length in range(2, n + 1):
            for i in range(n - length + 1):
                for k in range(1, length):
                    for A, prods in cnf_g.items():
                        for prod in prods:
                            if len(prod) == 2:
                                B, C = prod
                                if (B in table[k-1][i] and
                                        C in table[length-k-1][i+k]):
                                    table[length-1][i].add(A)

        return self.start_symbol in table[n-1][0]

    # ==========================================
    # FULL PIPELINE  (Rule 1A → 1B → 2 → 3)
    # ==========================================

    def simplify(self):
        try:
            if not self.grammar:
                return {"success": True, "steps": [], "final": ""}

            # Work on a deep copy so self.grammar stays pristine
            current = copy.deepcopy(self.grammar)

            # ── RULE 1A: Remove Non-Generating Symbols ──────────────────────
            current = self.remove_non_generating(current)
            self.steps_output.append({
                "title": "Step 1A: Removed Non-Generating Symbols",
                "grammar": self.format_grammar(current)
            })

            # ── RULE 1B: Remove Non-Reachable Symbols ───────────────────────
            current = self.remove_unreachable(current, self.start_symbol)
            self.steps_output.append({
                "title": "Step 1B: Removed Non-Reachable Symbols",
                "grammar": self.format_grammar(current)
            })

            # ── RULE 2: Remove ε-Productions ────────────────────────────────
            current = self.remove_epsilon(current)
            self.steps_output.append({
                "title": "Step 2: Removed ε-Productions (Null Productions)",
                "grammar": self.format_grammar(current)
            })

            # ── RULE 3: Remove Unit Productions ─────────────────────────────
            current = self.remove_unit(current)
            self.steps_output.append({
                "title": "Step 3: Removed Unit Productions",
                "grammar": self.format_grammar(current)
            })

            return {
                "success": True,
                "steps": self.steps_output,
                "final": self.format_grammar(current)
            }

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return {"success": False, "error": str(e)}


# ──────────────────────────────────────────────
# Public API used by app.py
# ──────────────────────────────────────────────

def simplify_cfg_steps(grammar_str):
    try:
        return CFGSimplifier(grammar_str).simplify()
    except Exception as e:
        return {"success": False, "error": f"Parsing error: {str(e)}"}


def check_cfg_derivation(grammar_str, sequence):
    try:
        simplifier = CFGSimplifier(grammar_str)
        target = sequence if sequence else simplifier.sequence
        if not target:
            return None
        return target, simplifier.check_sequence(target)
    except Exception:
        return None
