from cfg_simplifier import simplify_cfg_steps, check_cfg_derivation

def show(result):
    for s in result['steps']:
        print(f"  [{s['title']}]")
        print(f"  {s['grammar']}")
        print()
    print("  Final:", result['final'])

# ── Test 1: Non-Generating removal ──────────────────────────────────────────
print("=== TEST 1: Non-Generating removal ===")
g1 = "S -> A B | a\nA -> a\nB -> C\nC -> B C"
show(simplify_cfg_steps(g1))

# ── Test 2: Epsilon removal ──────────────────────────────────────────────────
print("\n=== TEST 2: Epsilon removal ===")
g2 = "S -> A B\nA -> a | e\nB -> b | e"
show(simplify_cfg_steps(g2))

# ── Test 3: Unit production removal ─────────────────────────────────────────
print("\n=== TEST 3: Unit production removal ===")
g3 = "S -> A | a b\nA -> B | c\nB -> d"
show(simplify_cfg_steps(g3))

# ── Test 4: All three rules ──────────────────────────────────────────────────
print("\n=== TEST 4: Full simplification ===")
g4 = "S -> A B C | a\nA -> a | e\nB -> b | e\nC -> D\nD -> d\nE -> e"
show(simplify_cfg_steps(g4))

# ── Test 5: CYK membership ───────────────────────────────────────────────────
print("\n=== TEST 5: CYK membership check ===")
g5 = "S -> A B | a\nA -> a\nB -> b"
for seq, expected in [("a b", True), ("a", True), ("b", False)]:
    res = check_cfg_derivation(g5, seq)
    status = "OK" if res[1] == expected else "FAIL"
    print(f"  [{status}] '{seq}' accepted={res[1]} (expected={expected})")
