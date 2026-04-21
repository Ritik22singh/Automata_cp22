from cfg_simplifier import CFGSimplifier, check_cfg_derivation
import traceback

def test_cfg():
    print("=== STARTING CFG TESTS ===")
    
    try:
        # Test Case 1: Standard grammar
        print("\n--- Test Case 1: Standard grammar ---")
        grammar_str = "S -> A B | a B\nA -> a\nB -> b"
        simplifier = CFGSimplifier(grammar_str)
        result = simplifier.simplify()
        print(f"Simplified:\n{result['final']}")
        
        # Test explicit check
        res_ab = check_cfg_derivation(grammar_str, "a b")
        print(f"Check 'a b': {res_ab[1] if res_ab else 'None'}")
        
        # Test extraction from grammar_str
        grammar_with_seq = grammar_str + "\na c"
        res_ac = check_cfg_derivation(grammar_with_seq, "")
        print(f"Check 'a c' (extracted): {res_ac[1] if res_ac else 'None'}")
    except Exception:
        print("Error in Test Case 1:")
        traceback.print_exc()

    try:
        # Test Case 2: Multi-character symbols
        print("\n--- Test Case 2: Multi-character symbols ---")
        grammar_str2 = "Expr -> Term | Expr + Term\nTerm -> Factor | Term * Factor\nFactor -> id"
        simplifier2 = CFGSimplifier(grammar_str2)
        result2 = simplifier2.simplify()
        print(f"Simplified:\n{result2['final']}")
        print(f"Check 'id + id': {check_cfg_derivation(grammar_str2, 'id + id')}")
        print(f"Check 'id * id': {check_cfg_derivation(grammar_str2, 'id * id')}")
        print(f"Check 'id +': {check_cfg_derivation(grammar_str2, 'id +')}")
    except Exception:
        print("Error in Test Case 2:")
        traceback.print_exc()

    print("\n=== TESTS COMPLETE ===")

if __name__ == "__main__":
    test_cfg()
