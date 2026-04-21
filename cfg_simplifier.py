class CFGSimplifier:
    def __init__(self, raw_grammar_str):
        self.raw_grammar = raw_grammar_str
        self.grammar, self.sequence = self.parse_input(raw_grammar_str)
        self.start_symbol = list(self.grammar.keys())[0] if self.grammar else "S"
        self.steps_output = [] # Store output of each step
        
    def parse_input(self, input_str):
        """ Extracts grammar rules and an optional sequence at the end """
        # Clean up common unicode arrow variants
        input_str = input_str.replace('→', '->').replace('⇒', '->')
        lines = input_str.strip().split('\n')
        grammar = {}
        sequence = None
        
        rule_lines = []
        other_lines = []
        
        for line in lines:
            line = line.strip()
            if not line: continue
            # Handle both '->' and '→' (already replaced above, but being safe)
            if '->' in line:
                rule_lines.append(line)
            else:
                other_lines.append(line)
        
        # Last non-rule line is the sequence
        if other_lines:
            sequence = other_lines[-1]
            
        for line in rule_lines:
            left, right = line.split('->')
            left = left.strip()
            productions = [p.strip() for p in right.split('|')]
            
            grammar_prods = []
            for p in productions:
                if p == 'ε' or p == '' or p.lower() == 'epsilon':
                    grammar_prods.append(['ε'])
                else:
                    # Tokenize: if symbols are joined like 'aA', we should ideally split them.
                    # As a heuristic, if a token has no spaces, we'll try to split 
                    # single-letter terminals from single-letter variables.
                    tokens = p.split()
                    if not tokens:
                        grammar_prods.append(['ε'])
                    else:
                        refined_tokens = []
                        for t in tokens:
                            # Heuristic: split if it's a mix of upper/lower case symbols joined together
                            # unless it's just a variable name like 'Var1' (starts with upper).
                            # For simplicity: split if it contains both upper and lower and doesn't look like a single name.
                            if any(c.isupper() for c in t) and any(c.islower() for c in t):
                                for char in t:
                                    refined_tokens.append(char)
                            else:
                                refined_tokens.append(t)
                        grammar_prods.append(refined_tokens)
            
            if left not in grammar: grammar[left] = []
            grammar[left].extend(grammar_prods)
            
        return grammar, sequence

    def parse_grammar(self, grammar_str):
        # Deprecated: use parse_input. Kept for compatibility if needed.
        g, s = self.parse_input(grammar_str)
        return g

    def format_grammar(self, grammar):
        """ Converts dict back to string S -> A B | a """
        lines = []
        for A, prods in grammar.items():
            if not prods: continue
            # Join symbols with space for readability and multi-char support
            rhs = [" ".join(p) for p in prods]
            lines.append(f"{A} -> {' | '.join(rhs)}")
        return "\n".join(lines)


    # ==========================================
    # STEP 1: REMOVE USELESS SYMBOLS
    # ==========================================
    
    def remove_non_generating(self, grammar):
        generating = set()
        non_terminals = set(self.grammar.keys()) # Original NTs for reference

        changed = True
        while changed:
            changed = False
            for A, prods in grammar.items():
                for prod in prods:
                    # check if all symbols in prod are terminals or in generating
                    is_gen = True
                    for X in prod:
                        if X in non_terminals and X not in generating:
                            is_gen = False
                            break
                    if is_gen:
                        if A not in generating:
                            generating.add(A)
                            changed = True

        new_grammar = {}
        for A in generating:
            if A not in grammar: continue
            new_prods = []
            for prod in grammar[A]:
                is_prod_gen = True
                for X in prod:
                    if X in non_terminals and X not in generating:
                        is_prod_gen = False
                        break
                if is_prod_gen:
                    new_prods.append(prod)
            if new_prods:
                new_grammar[A] = new_prods

        return new_grammar

    def remove_unreachable(self, grammar, start):
        if start not in grammar: return {start: []} if start in self.grammar else {}
        
        reachable = {start}
        non_terminals = set(self.grammar.keys())

        changed = True
        while changed:
            changed = False
            for A in list(reachable):
                for prod in grammar.get(A, []):
                    for X in prod:
                        if X in non_terminals and X not in reachable:
                            reachable.add(X)
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
                    if prod == ["ε"] or all((X in nullable) for X in prod):
                        if A not in nullable:
                            nullable.add(A)
                            changed = True

        new_grammar = {}
        for A, prods in grammar.items():
            new_prods = set()
            for prod in prods:
                if prod == ["ε"]: continue
                
                # generate_nullable_subsets logic
                subsets = [[]]
                for X in prod:
                    if X in nullable:
                        # Append X or don't append X
                        new_subsets = []
                        for s in subsets:
                            new_subsets.append(s + [X])
                            new_subsets.append(s)
                        subsets = new_subsets
                    else:
                        for s in subsets:
                            s.append(X)
                
                for p in subsets:
                    if p: new_prods.add(tuple(p))

            new_grammar[A] = [list(p) for p in new_prods]

        # start derives ε special case
        if self.start_symbol in nullable:
            if self.start_symbol not in new_grammar: new_grammar[self.start_symbol] = []
            if ["ε"] not in new_grammar[self.start_symbol]:
                new_grammar[self.start_symbol].append(["ε"])

        return {A: prods for A, prods in new_grammar.items() if prods or A == self.start_symbol}


    # ==========================================
    # STEP 3: REMOVE UNIT PRODUCTIONS
    # ==========================================

    def remove_unit(self, grammar):
        non_terminals = set(self.grammar.keys())
        unit = set()

        for A in grammar:
            unit.add((A, A))

        changed = True
        while changed:
            changed = False
            for A, prods in grammar.items():
                for prod in prods:
                    if len(prod) == 1 and prod[0] in non_terminals:
                        B = prod[0]
                        if (A, B) not in unit:
                            unit.add((A, B))
                            changed = True
            
            # Transitive closure: if (A,B) and (B,C) then (A,C)
            # Efficient update
            for A, B in list(unit):
                for B2, C in list(unit):
                    if B == B2:
                        if (A, C) not in unit:
                            unit.add((A, C))
                            changed = True

        new_grammar = {A: [] for A in grammar}
        for A, B in unit:
            if B not in grammar: continue
            for prod in grammar[B]:
                if not (len(prod) == 1 and prod[0] in non_terminals):
                    if prod not in new_grammar[A]:
                        new_grammar[A].append(prod)

        return {A: prods for A, prods in new_grammar.items() if prods}

    # ==========================================
    # CYK ALGORITHM & CNF CONVERSION
    # ==========================================

    def to_cnf(self, grammar):
        """ Converts a simplified grammar (no epsilon, no unit) to Chomsky Normal Form """
        new_grammar = {}
        non_terminals = set(self.grammar.keys())
        term_map = {}
        counter = 0

        # Step 1: Assign non-terminals to terminals in mixed/long productions
        for A, prods in grammar.items():
            new_prods = []
            for prod in prods:
                if len(prod) == 1:
                    new_prods.append(prod)
                else:
                    processed_prod = []
                    for symbol in prod:
                        if symbol not in non_terminals:
                            if symbol not in term_map:
                                t_name = f"T_{symbol}"
                                term_map[symbol] = t_name
                                new_grammar[t_name] = [[symbol]]
                            processed_prod.append(term_map[symbol])
                        else:
                            processed_prod.append(symbol)
                    new_prods.append(processed_prod)
            if A not in new_grammar: new_grammar[A] = []
            new_grammar[A].extend(new_prods)

        # Step 2: Break down long productions
        final_grammar = {}
        for A, prods in new_grammar.items():
            for prod in prods:
                if len(prod) <= 2:
                    if A not in final_grammar: final_grammar[A] = []
                    if prod not in final_grammar[A]: final_grammar[A].append(prod)
                else:
                    curr = A
                    for i in range(len(prod) - 2):
                        new_v = f"X_{counter}"
                        counter += 1
                        if curr not in final_grammar: final_grammar[curr] = []
                        final_grammar[curr].append([prod[i], new_v])
                        curr = new_v
                    if curr not in final_grammar: final_grammar[curr] = []
                    final_grammar[curr].append([prod[-2], prod[-1]])
        
        return final_grammar

    def check_sequence(self, sequence_str):
        """ String derivation check using CYK algorithm """
        # We need a simplified version for CNF
        g = self.grammar
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
            return (["ε"] in g.get(self.start_symbol, []) or ["ε"] in self.grammar.get(self.start_symbol, []))

        # table[length-1][start_pos]
        table = [[set() for _ in range(n)] for _ in range(n)]

        # Base case: length 1
        for i in range(n):
            for A, prods in cnf_g.items():
                for prod in prods:
                    if len(prod) == 1 and prod[0] == tokens[i]:
                        table[0][i].add(A)

        # Recurrence: length 2 to n
        for length in range(2, n + 1):
            for i in range(n - length + 1):
                for k in range(1, length):
                    # split into k and length-k
                    for A, prods in cnf_g.items():
                        for prod in prods:
                            if len(prod) == 2:
                                B, C = prod
                                if B in table[k-1][i] and C in table[length-k-1][i+k]:
                                    table[length-1][i].add(A)

        return self.start_symbol in table[n-1][0]

    # ==========================================
    # FULL PIPELINE EXECUTION
    # ==========================================

    def simplify(self):
        try:
            if not self.grammar:
                return {"success": True, "steps": [], "final": ""}

            current_grammar = self.grammar
            
            # Step 1: Remove Epsilon
            current_grammar = self.remove_epsilon(current_grammar)
            self.steps_output.append({
                "title": "Step 1: Removed ε-productions",
                "grammar": self.format_grammar(current_grammar)
            })

            # Step 2: Remove Unit
            current_grammar = self.remove_unit(current_grammar)
            self.steps_output.append({
                "title": "Step 2: Removed Unit productions",
                "grammar": self.format_grammar(current_grammar)
            })

            # Step 3: Remove Useless Symbols (Non-generating followed by Unreachable)
            # (a) Remove Non-generating
            current_grammar = self.remove_non_generating(current_grammar)
            self.steps_output.append({
                "title": "Step 3a: Removed Non-generating symbols",
                "grammar": self.format_grammar(current_grammar)
            })

            # (b) Remove Unreachable
            current_grammar = self.remove_unreachable(current_grammar, self.start_symbol)
            self.steps_output.append({
                "title": "Step 3b: Removed Unreachable symbols",
                "grammar": self.format_grammar(current_grammar)
            })
            
            return {
                "success": True,
                "steps": self.steps_output,
                "final": self.format_grammar(current_grammar)
            }
            
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return {
                "success": False,
                "error": str(e)
            }

def simplify_cfg_steps(grammar_str):
    try:
        simplifier = CFGSimplifier(grammar_str)
        return simplifier.simplify()
    except Exception as e:
        return {"success": False, "error": f"Initial parsing error: {str(e)}"}

def check_cfg_derivation(grammar_str, sequence):
    try:
        simplifier = CFGSimplifier(grammar_str)
        # Use provided sequence or fallback to one found in grammar_str
        target = sequence if sequence else simplifier.sequence
        if not target:
            return None
        
        is_valid = simplifier.check_sequence(target)
        return target, is_valid
    except Exception:
        return None
