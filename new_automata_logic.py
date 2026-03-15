import os
import json
import graphviz

# ==========================================
# 1. PARSER & POSTFIX CONVERSION
# ==========================================

def insert_explicit_concat(regex):
    """
    Inserts a '.' character for implicit concatenation.
    Examples:
    'ab' -> 'a.b'
    '(a)(b)' -> '(a).(b)'
    'a*b' -> 'a*.b'
    """
    res = []
    for i, c in enumerate(regex):
        res.append(c)
        if i + 1 < len(regex):
            c1, c2 = regex[i], regex[i+1]
            # Conditions for concatenation:
            # c1 is a character, '*', or ')'
            # c2 is a character or '('
            if (c1.isalnum() or c1 in '*)+') and (c2.isalnum() or c2 == '('):
                # Only insert concat if it's not a union symbol
                if c1 != '+' and c2 != '+':
                    res.append('.')
    return ''.join(res)

def get_precedence(op):
    if op == '*': return 3
    if op == '.': return 2
    if op == '+': return 1
    return 0

def to_postfix(regex):
    """ Converts infix regex with explicit conctenation to postfix notation. """
    postfix = []
    stack = []
    for c in regex:
        if c.isalnum() or c == 'ε':
            postfix.append(c)
        elif c == '(':
            stack.append(c)
        elif c == ')':
            while stack and stack[-1] != '(':
                postfix.append(stack.pop())
            stack.pop() # Remove '('
        else: # c is an operator
            while stack and get_precedence(stack[-1]) >= get_precedence(c):
                postfix.append(stack.pop())
            stack.append(c)
    while stack:
        postfix.append(stack.pop())
    return ''.join(postfix)


# ==========================================
# 2. ε-NFA (THOMPSON'S CONSTRUCTION)
# ==========================================

class State:
    _id = 0
    def __init__(self):
        self.id = State._id
        State._id += 1
        self.transitions = {} # symbol: set(State)

    def add_transition(self, symbol, state):
        if symbol not in self.transitions:
            self.transitions[symbol] = set()
        self.transitions[symbol].add(state)

class NFA:
    def __init__(self, start: State, end: State):
        self.start = start
        self.end = end

def build_nfa(postfix):
    State._id = 0
    stack = []
    
    if not postfix:
        # Empty regex returns epsilon NFA
        start = State()
        end = State()
        start.add_transition('ε', end)
        return NFA(start, end)

    for c in postfix:
        if c.isalnum() or c == 'ε':
            start = State()
            end = State()
            start.add_transition(c, end)
            stack.append(NFA(start, end))
        
        elif c == '.':
            nfa2 = stack.pop()
            nfa1 = stack.pop()
            # Connect nfa1 end to nfa2 start
            nfa1.end.add_transition('ε', nfa2.start)
            stack.append(NFA(nfa1.start, nfa2.end))
            
        elif c == '+':
            nfa2 = stack.pop()
            nfa1 = stack.pop()
            start = State()
            end = State()
            
            start.add_transition('ε', nfa1.start)
            start.add_transition('ε', nfa2.start)
            nfa1.end.add_transition('ε', end)
            nfa2.end.add_transition('ε', end)
            
            stack.append(NFA(start, end))
            
        elif c == '*':
            nfa1 = stack.pop()
            start = State()
            end = State()
            
            start.add_transition('ε', nfa1.start)
            start.add_transition('ε', end)
            nfa1.end.add_transition('ε', nfa1.start)
            nfa1.end.add_transition('ε', end)
            
            stack.append(NFA(start, end))

    # Error handling for empty / invalid postfix pops
    if len(stack) != 1:
        raise ValueError("Invalid postfix expression or empty stack")
        
    return stack.pop()

def get_nfa_states_and_alphabet(nfa_start):
    visited = set()
    alphabet = set()
    queue = [nfa_start]
    
    while queue:
        state = queue.pop(0)
        if state not in visited:
            visited.add(state)
            for symbol, next_states in state.transitions.items():
                if symbol != 'ε':
                    alphabet.add(symbol)
                for ns in next_states:
                    if ns not in visited:
                        queue.append(ns)
    return visited, alphabet

def nfa_to_dict(nfa_start, nfa_end, states):
    nfa_dict = {"startingState": str(nfa_start.id)}
    for s in states:
        str_id = str(s.id)
        nfa_dict[str_id] = {
            "isTerminatingState": s.id == nfa_end.id
        }
        for symbol, next_states in s.transitions.items():
            sym = 'epsilon' if symbol == 'ε' else symbol
            nfa_dict[str_id][sym] = [str(ns.id) for ns in next_states]
    return nfa_dict


# ==========================================
# 3. NFA to DFA (SUBSET CONSTRUCTION)
# ==========================================

def epsilon_closure(states):
    closure = set(states)
    queue = list(states)
    while queue:
        state = queue.pop(0)
        if 'ε' in state.transitions:
            for ns in state.transitions['ε']:
                if ns not in closure:
                    closure.add(ns)
                    queue.append(ns)
    return frozenset(closure)

def move(states, symbol):
    next_states = set()
    for state in states:
        if symbol in state.transitions:
            for ns in state.transitions[symbol]:
                next_states.add(ns)
    return next_states

class DFA:
    def __init__(self, start_state, accept_states, transitions, alphabet):
        self.start_state = start_state
        self.accept_states = accept_states
        self.transitions = transitions
        self.alphabet = alphabet

def nfa_to_dfa(nfa, nfa_states, alphabet):
    dfa_transitions = {}
    dfa_accept_states = set()
    dfa_states_map = {} # frozenset(NFA States) -> int id
    
    start_closure = epsilon_closure({nfa.start})
    dfa_start_id = 0
    dfa_states_map[start_closure] = dfa_start_id
    
    if nfa.end in start_closure:
        dfa_accept_states.add(dfa_start_id)
        
    queue = [start_closure]
    state_counter = 1
    
    while queue:
        current_set = queue.pop(0)
        current_id = dfa_states_map[current_set]
        dfa_transitions[current_id] = {}
        
        for symbol in alphabet:
            move_set = move(current_set, symbol)
            if not move_set:
                continue
            
            closure_set = epsilon_closure(move_set)
            
            if closure_set not in dfa_states_map:
                dfa_states_map[closure_set] = state_counter
                if nfa.end in closure_set:
                    dfa_accept_states.add(state_counter)
                queue.append(closure_set)
                state_counter += 1
                
            dfa_transitions[current_id][symbol] = dfa_states_map[closure_set]
            
    return DFA(dfa_start_id, dfa_accept_states, dfa_transitions, alphabet), dfa_states_map

def dfa_to_dict(dfa):
    dfa_dict = {"startingState": str(dfa.start_state)}
    for state_id in dfa.transitions.keys():
        str_id = str(state_id)
        dfa_dict[str_id] = {
            "isTerminatingState": state_id in dfa.accept_states
        }
        for symbol, next_state in dfa.transitions[state_id].items():
            dfa_dict[str_id][symbol] = str(next_state)
            
    # Add states with no outbound transitions if any
    for state_id in dfa.accept_states:
        if state_id not in dfa.transitions:
            dfa_dict[str(state_id)] = {"isTerminatingState": True}
    return dfa_dict


# ==========================================
# 4. DFA MINIMIZATION (HOPCROFT / PARTITION)
# ==========================================

def minimize_dfa(dfa):
    all_states = set(dfa.transitions.keys()).union(dfa.accept_states)
    
    # Also discover any sink states mapped in transitions
    for transitions in dfa.transitions.values():
        for next_state in transitions.values():
            all_states.add(next_state)
            
    # Ensure all states exist in transitions map (even if empty)
    for state in all_states:
        if state not in dfa.transitions:
            dfa.transitions[state] = {}
            
    non_accept_states = all_states - dfa.accept_states
    
    # Step 1: Initial Partition
    partitions = []
    if dfa.accept_states: partitions.append(frozenset(dfa.accept_states))
    if non_accept_states: partitions.append(frozenset(non_accept_states))
    
    # Track which partition a state belongs to
    def get_partition_idx(state, current_partitions):
        for i, p in enumerate(current_partitions):
            if state in p:
                return i
        return -1 # Sink state
        
    # Step 2 & 3: Refine Partitions
    while True:
        new_partitions = []
        for group in partitions:
            if len(group) <= 1:
                new_partitions.append(group)
                continue
                
            # Maps characteristic tuple -> list of states
            split_map = {}
            for state in group:
                char_tuple = []
                for symbol in sorted(list(dfa.alphabet)):
                    if symbol in dfa.transitions[state]:
                        target = dfa.transitions[state][symbol]
                        char_tuple.append(get_partition_idx(target, partitions))
                    else:
                        char_tuple.append(-1) # Null transition distinct marker
                
                tup = tuple(char_tuple)
                if tup not in split_map:
                    split_map[tup] = set()
                split_map[tup].add(state)
                
            for subset in split_map.values():
                new_partitions.append(frozenset(subset))
                
        if set(partitions) == set(new_partitions):
            break
        partitions = new_partitions

    # Step 4: Build Minimized DFA
    min_start_id = get_partition_idx(dfa.start_state, partitions)
    min_accept_states = set()
    min_transitions = {}
    
    for i, group in enumerate(partitions):
        rep_state = next(iter(group))
        if rep_state in dfa.accept_states:
            min_accept_states.add(i)
            
        min_transitions[i] = {}
        for symbol in dfa.alphabet:
            if symbol in dfa.transitions[rep_state]:
                target = dfa.transitions[rep_state][symbol]
                target_partition = get_partition_idx(target, partitions)
                min_transitions[i][symbol] = target_partition
                
    return DFA(min_start_id, min_accept_states, min_transitions, dfa.alphabet)

def save_json(data, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def draw_automaton(data, filename):
    dot = graphviz.Digraph(comment='Automaton')
    dot.attr(rankdir='LR')
    dot.node('startingStateH', 'startingStateH', style='invis')
    
    for key, val in data.items():
        if key == 'startingState':
            continue
        if val.get('isTerminatingState', False):
            dot.node(key, key, shape='doublecircle')
        else:
            dot.node(key, key, shape='circle')
            
    for key, val in data.items():
        if key == 'startingState':
            continue
        for symbol, next_states in val.items():
            if symbol == 'isTerminatingState':
                continue
            
            # Label fixing for epsilon
            label = 'ε' if symbol == 'epsilon' else symbol
            
            if isinstance(next_states, list): # NFA structure
                for ns in next_states:
                    dot.edge(key, ns, label=label)
            else: # DFA structure
                dot.edge(key, next_states, label=label)
                
    dot.edge('startingStateH', str(data['startingState']))
    dot.format = 'png'
    dot.render(filename)


# ==========================================
# 7. PIPELINE FLOW EXECUTION
# ==========================================

def generate_automata(regex):
    print(f"Generating for regex: {regex}")
    
    # 1. Parsing
    formatted_regex = insert_explicit_concat(regex)
    print(f"Formatted Regex: {formatted_regex}")
    postfix = to_postfix(formatted_regex)
    print(f"Postfix: {postfix}")
    
    # 2. ε-NFA
    nfa = build_nfa(postfix)
    nfa_states, alphabet = get_nfa_states_and_alphabet(nfa.start)
    nfa_dict = nfa_to_dict(nfa.start, nfa.end, nfa_states)
    
    save_json(nfa_dict, "nfa.json")
    draw_automaton(nfa_dict, "nfa_graph")
    
    # 3. NFA -> DFA
    dfa, _ = nfa_to_dfa(nfa, nfa_states, alphabet)
    dfa_dict = dfa_to_dict(dfa)
    
    save_json(dfa_dict, "dfa.json")
    draw_automaton(dfa_dict, "dfa_graph")
    
    # 4. DFA -> Minimized DFA
    min_dfa = minimize_dfa(dfa)
    min_dfa_dict = dfa_to_dict(min_dfa)
    
    save_json(min_dfa_dict, "minimized_dfa.json")
    draw_automaton(min_dfa_dict, "minimized_dfa_graph")
    
    print("Generation complete!")

# Execution wrapper for Jupyter Injection
if __name__ == "__main__":
    if os.path.exists("regex_input.txt"):
        with open("regex_input.txt", "r") as f:
            regex_input = f.read().strip()
            print("Received input from regex_input.txt:", regex_input)
            if regex_input:
                generate_automata(regex_input)
            else:
                print("Empty API regex format. Generating default ε.")
                generate_automata("")
    else:
        # User requested Example Test Regex
        generate_automata("(a+b)a*")
