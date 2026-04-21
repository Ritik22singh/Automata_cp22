from cfg_simplifier import CFGSimplifier
import json

grammar_str = """
S -> A B | C
A -> aA | ε
B -> b
C -> D
D -> E
E -> e
F -> f
""".strip()

print("--- REPRODUCING ISSUE ---")
simplifier = CFGSimplifier(grammar_str)
print(f"Parsed Grammar: {simplifier.grammar}")
print(f"Detected Sequence: {simplifier.sequence}")

result = simplifier.simplify()
if result['success']:
    print("\nSimplification Steps:")
    for step in result['steps']:
        print(f"\n[{step['title']}]")
        print(step['grammar'])
    print("\nFinal Result:")
    print(result['final'])
else:
    print(f"Error: {result['error']}")
