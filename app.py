from flask import Flask, render_template, request, jsonify
import subprocess
import shutil
import os

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/convert", methods=["POST"])
def convert():

    regex = request.json["regex"]

    # run python script to generate automata diagrams
    subprocess.run(["python", "generate_automata.py", regex])

    if os.path.exists("nfa_graph.png"):
        shutil.copy("nfa_graph.png", "static/nfa_graph.png")

    if os.path.exists("dfa_graph.png"):
        shutil.copy("dfa_graph.png", "static/dfa_graph.png")

    if os.path.exists("minimized_dfa_graph.png"):
        shutil.copy("minimized_dfa_graph.png", "static/minimized_dfa_graph.png")

    return jsonify({
        "nfa": "/static/nfa_graph.png",
        "dfa": "/static/dfa_graph.png",
        "mindfa": "/static/minimized_dfa_graph.png"
    })


if __name__ == "__main__":
    app.run(debug=True)