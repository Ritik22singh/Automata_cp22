from flask import Flask, render_template, request, jsonify
import subprocess
import shutil
from cfg_simplifier import simplify_cfg_steps

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/convert", methods=["POST"])
def convert():

    regex = request.json["regex"]

    # save regex for generator
    with open("regex_input.txt","w") as f:
        f.write(regex)

    # Execute Jupyter Notebook instead of a separate python script
    # and wait for it to finish creating the NFA/DFA diagram assets
    subprocess.run(["jupyter", "nbconvert", "--execute", "--to", "notebook", "--inplace", "RegexToNfaDfa.ipynb"])

    # move new diagrams to static
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
    grammar_str = request.json.get("grammar", "")
    
    # Process grammar through the 3 algorithms
    result = simplify_cfg_steps(grammar_str)
    
    if not result.get("success", False):
        return jsonify({"success": False, "error": result.get("error", "Unknown error")}), 400
        
    return jsonify({
        "success": True,
        "steps": result["steps"],
        "final": result["final"]
    })

if __name__ == "__main__":
    app.run(debug=True)