from RegexToNfaDfa import *

# read regex
with open("regex_input.txt") as f:
    regex = f.read().strip()

print("Generating automata for:", regex)

lexer = regexLexer(regex)
tokenStream = lexer.lexer()

parser = ParseRegex(tokenStream)
ast = parser.parse()

thompson = ThompsonConstruction(ast)
nfa = thompson.construct()

nfa_dict = nfa.to_dict()

save_json(nfa_dict,"nfa.json")
display_and_save_image(nfa_dict,"nfa_graph")

dfa_converter = NFAtoDFA(nfa_dict)
dfa = dfa_converter.convert()

save_json(dfa,"dfa.json")
display_and_save_image(dfa,"dfa_graph")

minimizer = DFAMinimizer(dfa)
min_dfa = minimizer.minimize()

save_json(min_dfa,"minimized_dfa.json")
display_and_save_image(min_dfa,"minimized_dfa_graph")