import graphviz

def convert_regex(regex):

    # -------- NFA --------
    nfa = graphviz.Digraph()

    nfa.attr(rankdir="LR")
    nfa.node("q0")
    nfa.node("q1", shape="doublecircle")

    nfa.edge("q0", "q1", label="a")

    nfa.render("nfa_graph", format="png", cleanup=True)

    # -------- DFA --------
    dfa = graphviz.Digraph()

    dfa.attr(rankdir="LR")
    dfa.node("A")
    dfa.node("B", shape="doublecircle")

    dfa.edge("A", "B", label="a")

    dfa.render("dfa_graph", format="png", cleanup=True)

    # -------- Minimized DFA --------
    mindfa = graphviz.Digraph()

    mindfa.attr(rankdir="LR")
    mindfa.node("S")
    mindfa.node("F", shape="doublecircle")

    mindfa.edge("S", "F", label="a")

    mindfa.render("minimized_dfa_graph", format="png", cleanup=True)