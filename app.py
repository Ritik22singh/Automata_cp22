from flask import Flask, render_template, request, jsonify
import subprocess
import shutil
import sys
import re
from cfg_simplifier import simplify_cfg_steps, check_cfg_derivation
from compiler_core import SemanticAnalyzer, Interpreter

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

# ==========================================
# ANTIGRAVITY IDE BACKEND LOGIC
# ==========================================

# Phase 1: Simple Regex Tokenizer
LANGUAGE_PROFILES = {
    'c': r'\b(?:int|float|double|char|void|if|else|while|for|return|break|continue)\b',
    'java': r'\b(?:int|float|double|boolean|char|void|if|else|while|for|return|break|continue|public|private|class|static|new|String|System|out|println)\b',
    'python': r'\b(?:int|float|str|bool|if|elif|else|while|for|return|break|continue|def|class|print|True|False|None)\b',
}

def get_token_regex(language):
    kw_pattern = LANGUAGE_PROFILES.get(language, LANGUAGE_PROFILES['c'])
    spec = [
        ('PREPROCESSOR', r'#.*'),
        ('KEYWORD',    kw_pattern),
        ('STRING',     r'"[^"\\]*(?:\\.[^"\\]*)*"|\'[^\'\\]*(?:\\.[^\'\\]*)*\''),
        ('NUMBER',     r'\d+(\.\d*)?'),
        ('IDENTIFIER', r'[a-zA-Z_][a-zA-Z_0-9]*'),
        ('OPERATOR',   r'[+\-*/=><!%&]+'),
        ('SYMBOL',     r'[(){}\[\];,:.]'),
        ('WHITESPACE', r'\s+'),
        ('UNKNOWN',    r'.')
    ]
    return re.compile('|'.join(f'(?P<{name}>{pattern})' for name, pattern in spec))

def strip_preprocessor(code):
    """Remove preprocessor lines (#include, #define, etc.) to avoid UNKNOWN tokens."""
    result = []
    for line in code.split('\n'):
        if line.strip().startswith('#'):
            result.append('')
        else:
            result.append(line)
    return '\n'.join(result)

def tokenize(code, language='c'):
    tokens = []
    line_num = 1
    line_start = 0
    
    for mo in get_token_regex(language).finditer(code):
        kind = mo.lastgroup
        value = mo.group()
        column = mo.start() - line_start
        
        if kind == 'WHITESPACE':
            if '\n' in value:
                line_num += value.count('\n')
                line_start = mo.end()
            continue
            
        tokens.append({
            'type': kind,
            'value': value,
            'line': line_num,
            'column': column,
            'start': mo.start(),
            'end': mo.end()
        })
    return tokens

# Phase 1: PDA Bracket Matcher
def analyze_brackets(code):
    stack = []
    logs = []
    errors = []
    
    pairs = {')': '(', '}': '{', ']': '['}
    
    line_num = 1
    line_start = 0
    
    for i, char in enumerate(code):
        if char == '\n':
            line_num += 1
            line_start = i + 1
            continue
            
        col = i - line_start
        
        if char in '({[':
            stack.append((char, line_num, col))
            logs.append({'action': 'PUSH', 'char': char, 'line': line_num, 'col': col})
        elif char in ')}]':
            if not stack:
                logs.append({'action': 'MISMATCH', 'char': char, 'line': line_num, 'col': col, 'detail': 'Extra closing bracket'})
                errors.append({'line': line_num, 'col': col, 'message': f'Extra closing bracket "{char}"'})
            else:
                top, top_line, top_col = stack.pop()
                if pairs[char] == top:
                    logs.append({'action': 'POP', 'char': char, 'matched': top, 'line': line_num, 'col': col})
                else:
                    logs.append({'action': 'MISMATCH', 'char': char, 'expected': pairs[char], 'found': top, 'line': line_num, 'col': col})
                    errors.append({'line': line_num, 'col': col, 'message': f'Mismatched bracket. Expected "{pairs[char]}", found "{char}"'})
                    
    while stack:
        top, top_line, top_col = stack.pop()
        logs.append({'action': 'UNCLOSED', 'char': top, 'line': top_line, 'col': top_col})
        errors.append({'line': top_line, 'col': top_col, 'message': f'Unclosed bracket "{top}"'})
        
    return logs, errors

# ==========================================
# Phase 3: CFG Syntax Checker (Recursive Descent Parser)
# ==========================================
class ParserError(Exception):
    def __init__(self, message, line, col):
        self.message = message
        self.line = line
        self.col = col

class Parser:
    def __init__(self, tokens):
        # Filter out whitespace and unknown tokens for parsing
        self.tokens = [t for t in tokens if t['type'] not in ('WHITESPACE', 'UNKNOWN', 'PREPROCESSOR')]
        self.pos = 0
        self.errors = []

    def current(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def advance(self):
        if self.pos < len(self.tokens):
            self.pos += 1

    def match(self, expected_type, expected_value=None):
        tok = self.current()
        if not tok:
            raise ParserError("Unexpected end of input", -1, -1)
        if tok['type'] == expected_type and (expected_value is None or tok['value'] == expected_value):
            self.advance()
            return tok
        
        msg = f"Expected {expected_type}" + (f" '{expected_value}'" if expected_value else "") + f", found '{tok['value']}'"
        raise ParserError(msg, tok['line'], tok['column'])

    def parse(self):
        node = {"type": "Program", "children": []}
        if not self.tokens:
            return node
            
        while self.pos < len(self.tokens) and not self.errors:
            try:
                stmt = self.parse_statement()
                if stmt: node['children'].append(stmt)
            except ParserError as e:
                node['children'].append({"type": "Error", "label": f"❌ {e.message}"})
                self.errors.append(e)
                break # stop on first unhandled error
        return node

    def parse_statement(self):
        tok = self.current()
        if not tok:
            raise ParserError("Expected statement", -1, -1)
            
        if tok['type'] == 'KEYWORD':
            if tok['value'] in ('int', 'float', 'double', 'char', 'void'):
                return self.parse_declaration()
            elif tok['value'] == 'if':
                return self.parse_if()
            elif tok['value'] == 'while':
                return self.parse_while()
            elif tok['value'] == 'for':
                return self.parse_for()
            elif tok['value'] == 'return':
                return self.parse_return()
            elif tok['value'] in ('break', 'continue'):
                node = {"type": tok['value'].capitalize(), "label": tok['value']}
                self.advance()
                try:
                    self.match('SYMBOL', ';')
                except ParserError:
                    pass
                return node
        
        if tok['type'] == 'IDENTIFIER':
            # peek ahead: if next is '(' it's a function call statement
            next_tok = self.tokens[self.pos + 1] if self.pos + 1 < len(self.tokens) else None
            if next_tok and next_tok['value'] == '(':
                return self.parse_call_statement()
            return self.parse_assignment()
            
        if tok['type'] == 'SYMBOL' and tok['value'] == '{':
            return self.parse_block()
            
        raise ParserError(f"Unexpected token '{tok['value']}'", tok['line'], tok['column'])

    def parse_declaration(self):
        type_tok = self.current()
        self.advance() # consume type
        
        node = {"type": "Declaration", "label": type_tok['value'], "children": []}
        
        try:
            tok = self.current()
            if not tok or tok['type'] != 'IDENTIFIER':
                line = tok['line'] if tok else -1
                col = tok['column'] if tok else -1
                raise ParserError(f"Identifier expected after type '{type_tok['value']}'", line, col)
                
            id_tok = self.match('IDENTIFIER')
            
            # Check for Function Declaration: int main () { }
            if self.current() and self.current()['value'] == '(':
                node['type'] = "FunctionDecl"
                node['label'] += f" {id_tok['value']}"
                self.match('SYMBOL', '(')
                self.match('SYMBOL', ')')
                block = self.parse_block()
                node['children'].append(block)
                return node
                
            # Variable Declaration: int a = 5;
            var_node = {"type": "VarDecl", "label": id_tok['value'], "children": []}
            if self.current() and self.current()['value'] == '=':
                self.advance()
                expr = self.parse_expression()
                var_node['children'].append({"type": "Assignment", "label": "=", "children": [expr]})
            node['children'].append(var_node)
            
            # Handle comma-separated
            while self.current() and self.current()['value'] == ',':
                self.advance() # consume ','
                next_id = self.match('IDENTIFIER')
                var_node = {"type": "VarDecl", "label": next_id['value'], "children": []}
                if self.current() and self.current()['value'] == '=':
                    self.advance()
                    expr = self.parse_expression()
                    var_node['children'].append({"type": "Assignment", "label": "=", "children": [expr]})
                node['children'].append(var_node)
                
            self.match('SYMBOL', ';')
        except ParserError as e:
            node['children'].append({"type": "Error", "label": f"❌ {e.message}"})
            self.errors.append(e)
            
        return node

    def parse_assignment(self):
        id_tok = self.current()
        node = {"type": "AssignmentStmt", "label": id_tok['value'], "children": []}
        
        try:
            self.match('IDENTIFIER')
            self.match('OPERATOR', '=')
            node['label'] += " ="
            expr = self.parse_expression()
            node['children'].append(expr)
            self.match('SYMBOL', ';')
        except ParserError as e:
            node['children'].append({"type": "Error", "label": f"❌ {e.message}"})
            self.errors.append(e)
            
        return node

    def parse_while(self):
        node = {"type": "WhileLoop", "label": "while", "children": []}
        try:
            self.match('KEYWORD', 'while')
            self.match('SYMBOL', '(')
            expr = self.parse_expression()
            node['children'].append({"type": "Condition", "label": "condition", "children": [expr]})
            self.match('SYMBOL', ')')
            body = self.parse_statement()
            node['children'].append({"type": "Body", "label": "body", "children": [body]})
        except ParserError as e:
            node['children'].append({"type": "Error", "label": f"❌ {e.message}"})
            self.errors.append(e)
        return node

    def parse_for(self):
        node = {"type": "ForLoop", "label": "for", "children": []}
        try:
            self.match('KEYWORD', 'for')
            self.match('SYMBOL', '(')
            # init: either declaration, assignment, or empty
            if self.current() and self.current()['value'] != ';':
                if self.current()['type'] == 'KEYWORD':
                    init = self.parse_declaration()
                else:
                    init = self.parse_assignment()
            else:
                init = {"type": "Empty", "label": ""}
                self.match('SYMBOL', ';')
            node['children'].append({"type": "Init", "label": "init", "children": [init]})
            # condition
            if self.current() and self.current()['value'] != ';':
                cond = self.parse_expression()
            else:
                cond = {"type": "Empty", "label": ""}
            self.match('SYMBOL', ';')
            node['children'].append({"type": "Condition", "label": "condition", "children": [cond]})
            # update
            if self.current() and self.current()['value'] != ')':
                upd_id = self.current()
                self.advance()
                upd_node = {"type": "Update", "label": upd_id['value'], "children": []}
                if self.current() and self.current()['type'] == 'OPERATOR':
                    op = self.current()['value']
                    self.advance()
                    if self.current() and self.current()['value'] != ')':
                        expr = self.parse_expression()
                        upd_node['children'].append({"type": "BinaryOp", "label": op, "children": [expr]})
                    else:
                        upd_node['label'] += op  # i++ style
            else:
                upd_node = {"type": "Empty", "label": ""}
            self.match('SYMBOL', ')')
            node['children'].append({"type": "Update", "label": "update", "children": [upd_node]})
            body = self.parse_statement()
            node['children'].append({"type": "Body", "label": "body", "children": [body]})
        except ParserError as e:
            node['children'].append({"type": "Error", "label": f"❌ {e.message}"})
            self.errors.append(e)
        return node

    def parse_if(self):
        node = {"type": "IfStatement", "label": "if", "children": []}
        try:
            self.match('KEYWORD', 'if')
            self.match('SYMBOL', '(')
            expr = self.parse_expression()
            node['children'].append({"type": "Condition", "label": "condition", "children": [expr]})
            self.match('SYMBOL', ')')
            then_stmt = self.parse_statement()
            node['children'].append({"type": "Then", "label": "then", "children": [then_stmt]})
            # Handle optional else
            if self.current() and self.current()['type'] == 'KEYWORD' and self.current()['value'] == 'else':
                self.advance()
                else_stmt = self.parse_statement()
                node['children'].append({"type": "Else", "label": "else", "children": [else_stmt]})
        except ParserError as e:
            node['children'].append({"type": "Error", "label": f"❌ {e.message}"})
            self.errors.append(e)
        return node

    def parse_call_statement(self):
        id_tok = self.current()
        node = {"type": "FunctionCall", "label": id_tok['value'] + "()", "children": []}
        try:
            self.advance()  # consume identifier
            self.match('SYMBOL', '(')
            # parse comma-separated arguments
            while self.current() and self.current()['value'] != ')':
                arg = self.parse_expression()
                node['children'].append(arg)
                if self.current() and self.current()['value'] == ',':
                    self.advance()
            self.match('SYMBOL', ')')
            # optional semicolon
            if self.current() and self.current()['value'] == ';':
                self.advance()
        except ParserError as e:
            node['children'].append({"type": "Error", "label": f"❌ {e.message}"})
            self.errors.append(e)
        return node

    def parse_return(self):
        node = {"type": "ReturnStatement", "label": "return", "children": []}
        try:
            self.match('KEYWORD', 'return')
            expr = self.parse_expression()
            node['children'].append(expr)
            self.match('SYMBOL', ';')
        except ParserError as e:
            node['children'].append({"type": "Error", "label": f"❌ {e.message}"})
            self.errors.append(e)
        return node

    def parse_block(self):
        node = {"type": "Block", "label": "{ }", "children": []}
        try:
            self.match('SYMBOL', '{')
            while self.current() and self.current()['value'] != '}' and not self.errors:
                stmt = self.parse_statement()
                if stmt: node['children'].append(stmt)
            self.match('SYMBOL', '}')
        except ParserError as e:
            node['children'].append({"type": "Error", "label": f"❌ {e.message}"})
            self.errors.append(e)
        return node

    def parse_expression(self):
        left = self.parse_term()
        while self.current() and self.current()['type'] == 'OPERATOR' and self.current()['value'] in ('+', '-', '>', '<', '==', '!=', '>=', '<='):
            op = self.current()['value']
            self.advance()
            right = self.parse_term()
            left = {"type": "BinaryOp", "label": op, "children": [left, right]}
        return left

    def parse_term(self):
        left = self.parse_factor()
        while self.current() and self.current()['type'] == 'OPERATOR' and self.current()['value'] in ('*', '/', '%'):
            op = self.current()['value']
            self.advance()
            right = self.parse_factor()
            left = {"type": "BinaryOp", "label": op, "children": [left, right]}
        return left

    def parse_factor(self):
        tok = self.current()
        if not tok:
            raise ParserError("Expected expression", -1, -1)
            
        if tok['type'] == 'NUMBER':
            self.advance()
            return {"type": "Number", "label": tok['value']}
        elif tok['type'] == 'STRING':
            self.advance()
            return {"type": "String", "label": tok['value']}
        elif tok['type'] == 'IDENTIFIER':
            self.advance()
            # check for function call in expression: foo(...)
            if self.current() and self.current()['value'] == '(':
                call_node = {"type": "CallExpr", "label": tok['value'] + "()", "children": []}
                self.advance()  # consume '('
                while self.current() and self.current()['value'] != ')':
                    arg = self.parse_expression()
                    call_node['children'].append(arg)
                    if self.current() and self.current()['value'] == ',':
                        self.advance()
                if self.current() and self.current()['value'] == ')':
                    self.advance()
                return call_node
            return {"type": "Identifier", "label": tok['value']}
        elif tok['value'] == '(':
            self.advance()
            expr = self.parse_expression()
            if self.current() and self.current()['value'] == ')':
                self.advance()
            return expr
        # Handle unary operators
        elif tok['type'] == 'OPERATOR' and tok['value'] in ('-', '+', '&', '*', '!', '~'):
            op = tok['value']
            self.advance()
            operand = self.parse_factor()
            return {"type": "UnaryOp", "label": op, "children": [operand]}
        else:
            raise ParserError(f"Unexpected token in expression: '{tok['value']}'", tok['line'], tok['column'])

@app.route("/ide")
def ide_view():
    return render_template("ide.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.json
    code = data.get('code', '')
    language = data.get('language', 'c')
    
    tokens = tokenize(code, language)
    bracket_logs, bracket_errors = analyze_brackets(code)
    
    # Check for lexical errors
    for t in tokens:
        if t['type'] == 'UNKNOWN':
            bracket_errors.append({'line': t['line'], 'col': t['column'], 'message': f"Invalid character: {t['value']}"})
            
    # Syntax Analysis (CFG Parsing) — always run, even if bracket errors exist
    ast = None
    parser_error = None
    parser = Parser(tokens)
    ast = parser.parse()
    if parser.errors:
        # Grab the first error to report overall status
        e = parser.errors[0]
        parser_error = {
            "message": e.message,
            "line": e.line,
            "col": e.col
        }
        bracket_errors.append({'line': e.line, 'col': e.col, 'message': e.message})
            
    # Semantic Analysis
    semantic_errors = []
    symbol_table = []
    if ast: # Run semantic analysis even if parser threw errors
        semantic_analyzer = SemanticAnalyzer(ast)
        semantic_errors, symbol_table = semantic_analyzer.analyze()
        
    return jsonify({
        'tokens': tokens,
        'bracketLogs': bracket_logs,
        'errors': bracket_errors,
        'ast': ast,
        'syntaxError': parser_error,
        'semanticErrors': semantic_errors,
        'symbolTable': symbol_table
    })


@app.route("/run", methods=["POST"])
def run_code():
    data = request.json
    code = data.get('code', '')
    language = data.get('language', 'c')
    
    tokens = tokenize(code, language)
    parser = Parser(tokens)
    ast = parser.parse()
    
    if parser.errors:
        return jsonify({"output": [], "error": "Syntax Error: " + parser.errors[0].message})
        
    semantic_analyzer = SemanticAnalyzer(ast)
    sem_errors, _ = semantic_analyzer.analyze()
    if sem_errors:
        return jsonify({"output": [], "error": "Semantic Error: " + sem_errors[0]['message']})
        
    interpreter = Interpreter(ast)
    output, error = interpreter.run()
    
    return jsonify({
        "output": output,
        "error": error
    })

if __name__ == "__main__":
    app.run(debug=True)