class CFGSimplifier:
    def __init__(self, raw_grammar_str):
        self.raw_grammar = raw_grammar_str
        self.grammar = self.parse_grammar(raw_grammar_str)
        self.start_symbol = list(self.grammar.keys())[0] if self.grammar else "S"
        self.steps_output = [] # Store output of each step
        
    def parse_grammar(self, grammar_str):
        """ Converts text S -> AB | a into dict format """
        grammar = {}
        lines = grammar_str.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line or '->' not in line: continue
            
            left, right = line.split('->')
            left = left.strip()
            
            # Extract productions separated by '|'
            productions = [p.strip() for p in right.split('|')]
            
            # Map into list of list of chars, treating 'ε' as an entire symbol
            grammar_prods = []
            for p in productions:
                if p == 'ε' or p == 'e':
                    grammar_prods.append(['ε'])
                else:
                    # Treat multi letters separately (assuming single char non-terminals)
                    # For a simple parser, we list() the string. A -> aA becomes ["a", "A"]
                    grammar_prods.append(list(p.replace(' ', '')))
            
            if left not in grammar:
                grammar[left] = []
            grammar[left].extend(grammar_prods)
            
        return grammar

    def format_grammar(self, grammar):
        """ Converts dict back to string S -> AB | a """
        lines = []
        for A, prods in grammar.items():
            if not prods: continue
            rhs = ["".join(p) for p in prods]
            lines.append(f"{A} -> {' | '.join(rhs)}")
        return "\n".join(lines)


    # ==========================================
    # STEP 1: REMOVE USELESS SYMBOLS
    # ==========================================
    
    def remove_non_generating(self, grammar):
        generating = set()
        changed = True
        
        while changed:
            changed = False
            for A, productions in grammar.items():
                for prod in productions:
                    # A symbol is generating if it's a terminal (lowercase) or already in generating set
                    # 'ε' is considered a terminal for generation
                    is_generating = True
                    for symbol in prod:
                        if symbol.isupper() and symbol not in generating:
                            is_generating = False
                            break
                            
                    if is_generating and A not in generating:
                        generating.add(A)
                        changed = True

        new_grammar = {}
        for A in generating:
            if A not in grammar: continue
            new_prods = []
            for prod in grammar[A]:
                is_prod_generating = True
                for symbol in prod:
                    if symbol.isupper() and symbol not in generating:
                        is_prod_generating = False
                        break
                if is_prod_generating:
                    new_prods.append(prod)
            if new_prods:
                new_grammar[A] = new_prods

        return new_grammar


    def remove_unreachable(self, grammar, start):
        if start not in grammar: return {}
        
        reachable = set([start])
        changed = True
        
        while changed:
            changed = False
            for A in list(reachable):
                for prod in grammar.get(A, []):
                    for symbol in prod:
                        if symbol.isupper() and symbol not in reachable:
                            reachable.add(symbol)
                            changed = True

        new_grammar = {A: grammar[A] for A in reachable if A in grammar}
        return new_grammar


    # ==========================================
    # STEP 2: REMOVE EPSILON PRODUCTIONS
    # ==========================================

    def remove_epsilon(self, grammar):
        nullable = set()

        # find nullable variables
        changed = True
        while changed:
            changed = False
            for A, prods in grammar.items():
                for prod in prods:
                    if prod == ["ε"] or all((sym in nullable) for sym in prod):
                        if A not in nullable:
                            nullable.add(A)
                            changed = True

        new_grammar = {}
        for A, prods in grammar.items():
            new_prods = set()

            for prod in prods:
                if prod == ["ε"]:
                    continue # Skip direct epsilon unless it's the start state later
                
                # Compute all combinations of nullable symbol removal
                subsets = [[]]
                for sym in prod:
                    if sym in nullable:
                        # Branch: include AND exclude the nullable symbol
                        subsets = subsets + [s + [sym] for s in subsets]
                    else:
                        # Must include non-nullable symbols
                        subsets = [s + [sym] for s in subsets]

                for s in subsets:
                    if s: # Don't add completely empty productions
                        new_prods.add(tuple(s))

            if new_prods:
                new_grammar[A] = [list(p) for p in new_prods]
            else:
                new_grammar[A] = []

        # Start state check for pure epsilon language
        if self.start_symbol in nullable:
            # Reintroduce new start state if required, or keep epsilon in start
            # A simple rule for now: if start is nullable, S -> epsilon is kept
            if self.start_symbol in new_grammar and ["ε"] not in new_grammar[self.start_symbol]:
                new_grammar[self.start_symbol].append(["ε"])

        return {k: v for k, v in new_grammar.items() if v}


    # ==========================================
    # STEP 3: REMOVE UNIT PRODUCTIONS
    # ==========================================

    def remove_unit(self, grammar):
        unit = {A: set() for A in grammar}

        # Base case: direct unit productions
        for A in grammar:
            for prod in grammar[A]:
                if len(prod) == 1 and prod[0].isupper():
                    unit[A].add(prod[0])

        # Transitive closure
        changed = True
        while changed:
            changed = False
            for A in grammar:
                for B in list(unit[A]):
                    if B in unit:
                        old_len = len(unit[A])
                        unit[A] |= unit[B]
                        if len(unit[A]) > old_len:
                            changed = True

        new_grammar = {}
        for A in grammar:
            new_prods = []

            # Add original non-unit productions
            for prod in grammar.get(A, []):
                if not (len(prod) == 1 and prod[0].isupper()):
                    if prod not in new_prods:
                        new_prods.append(prod)

            # Add derived non-unit productions from unit dependencies
            for B in unit[A]:
                for prod in grammar.get(B, []):
                    if not (len(prod) == 1 and prod[0].isupper()):
                        if prod not in new_prods:
                            new_prods.append(prod)

            if new_prods:
                new_grammar[A] = new_prods

        return new_grammar


    # ==========================================
    # FULL PIPELINE EXECUTION
    # ==========================================

    def simplify(self):
        try:
            current_grammar = self.grammar
            
            # Step 1: Remove Useless
            current_grammar = self.remove_non_generating(current_grammar)
            current_grammar = self.remove_unreachable(current_grammar, self.start_symbol)
            self.steps_output.append({
                "title": "Step 1: Removed Useless Symbols (Non-generating & Unreachable)",
                "grammar": self.format_grammar(current_grammar)
            })

            # Step 2: Remove Epsilon
            current_grammar = self.remove_epsilon(current_grammar)
            # Cleanup unreachable again which might occur after epsilons are gone
            current_grammar = self.remove_unreachable(current_grammar, self.start_symbol)
            self.steps_output.append({
                "title": "Step 2: Removed ε-productions",
                "grammar": self.format_grammar(current_grammar)
            })

            # Step 3: Remove Unit
            current_grammar = self.remove_unit(current_grammar)
            # Final cleanup
            current_grammar = self.remove_non_generating(current_grammar)
            current_grammar = self.remove_unreachable(current_grammar, self.start_symbol)
            self.steps_output.append({
                "title": "Step 3: Removed Unit productions",
                "grammar": self.format_grammar(current_grammar)
            })
            
            return {
                "success": True,
                "steps": self.steps_output,
                "final": self.format_grammar(current_grammar)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

def simplify_cfg_steps(grammar_str):
    simplifier = CFGSimplifier(grammar_str)
    return simplifier.simplify()
