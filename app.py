from flask import Flask, render_template, request, jsonify
import subprocess
import shutil
import sys
from cfg_simplifier import simplify_cfg_steps, check_cfg_derivation

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/convert", methods=["POST"])
def convert():

    regex = request.json["regex"]

    # save regex for generator
    with open("regex_input.txt","w", encoding="utf-8") as f:
        f.write(regex)

    # Run new_automata_logic.py directly (fixed version, avoids notebook bugs)
    result = subprocess.run(
        [sys.executable, "new_automata_logic.py"],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        print("Script STDERR:", result.stderr)
        print("Script STDOUT:", result.stdout)
        return jsonify({"error": "Automata generation failed", "details": result.stderr or result.stdout}), 500

    # move new diagrams to static
    import os
    missing = []
    for fname in ["nfa_graph.png", "dfa_graph.png", "minimized_dfa_graph.png"]:
        if not os.path.exists(fname):
            missing.append(fname)
    if missing:
        return jsonify({"error": f"Missing output files: {missing}"}), 500

    shutil.copy("nfa_graph.png","static/nfa_graph.png")
    shutil.copy("dfa_graph.png","static/dfa_graph.png")
    shutil.copy("minimized_dfa_graph.png","static/minimized_dfa_graph.png")

    return jsonify({
        "nfa":"/static/nfa_graph.png",
        "dfa":"/static/dfa_graph.png",
        "mindfa":"/static/minimized_dfa_graph.png"
    })

@app.route("/simplify_cfg", methods=["POST"])
def simplify_cfg():
    data = request.json
    grammar_str = data.get("grammar", "")
    sequence = data.get("sequence", "")
    
    # Process grammar through the 3 algorithms
    result = simplify_cfg_steps(grammar_str)
    
    if not result.get("success", False):
        return jsonify({"success": False, "error": result.get("error", "Unknown error")}), 400
    
    # Optional sequence check (can be from JSON or extracted from grammar_str)
    derivation_info = check_cfg_derivation(grammar_str, sequence)
    derivation_result = None
    if derivation_info:
        seq, is_valid = derivation_info
        derivation_result = {
            "sequence": seq,
            "valid": is_valid,
            "message": "String accepted" if is_valid else "String not accepted"
        }
        
    return jsonify({
        "success": True,
        "steps": result["steps"],
        "final": result["final"],
        "derivation": derivation_result
    })

if __name__ == "__main__":
    app.run(debug=True)