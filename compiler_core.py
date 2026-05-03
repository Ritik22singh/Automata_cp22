import re

class SemanticAnalyzer:
    def __init__(self, ast):
        self.ast = ast
        self.errors = []
        # Scope stack: list of dicts {var_name: {"type": type, "line": line, "scope": scope_level}}
        self.scopes = [{}]
        self.symbol_table = []
        self.current_scope_level = 0
    
    def analyze(self):
        if not self.ast:
            return self.errors, self.symbol_table
        self.visit(self.ast)
        return self.errors, self.symbol_table
        
    def enter_scope(self):
        self.current_scope_level += 1
        self.scopes.append({})
        
    def exit_scope(self):
        self.current_scope_level -= 1
        self.scopes.pop()
        
    def declare_variable(self, name, var_type, line=None):
        scope_name = "Global" if self.current_scope_level == 0 else "Local"
        
        # Check duplicate in CURRENT scope only
        if name in self.scopes[-1]:
            self.errors.append({
                "message": f"Duplicate declaration of variable '{name}'",
                "line": line or 0,
                "col": 0
            })
            return
            
        self.scopes[-1][name] = {"type": var_type, "line": line, "scope": scope_name}
        
        # Add to symbol table for UI
        self.symbol_table.append({
            "name": name,
            "type": var_type,
            "scope": scope_name,
            "value": None,
            "line": line or 0
        })
        
    def lookup_variable(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None
        
    def update_symbol_value(self, name, value):
        for sym in self.symbol_table:
            if sym["name"] == name and sym["scope"] == ("Global" if self.lookup_variable(name) and self.lookup_variable(name)["scope"] == "Global" else "Local"):
                 # Update latest matching variable value for simple visualization
                 sym["value"] = value
                 
    def visit(self, node):
        if not node or not isinstance(node, dict): return
        
        ntype = node.get("type")
        
        if ntype == "Program":
            for child in node.get("children", []):
                self.visit(child)
                
        elif ntype == "FunctionDecl":
            # Function declaration creates a new scope
            label_parts = node.get("label", "").split()
            if len(label_parts) >= 2:
                func_type, func_name = label_parts[0], label_parts[1]
                self.declare_variable(func_name, f"function returning {func_type}")
            
            self.enter_scope()
            for child in node.get("children", []):
                self.visit(child)
            self.exit_scope()
            
        elif ntype == "Block":
            self.enter_scope()
            for child in node.get("children", []):
                self.visit(child)
            self.exit_scope()
            
        elif ntype == "Declaration":
            var_type = node.get("label", "")
            for child in node.get("children", []):
                if child.get("type") == "VarDecl":
                    var_name = child.get("label", "")
                    self.declare_variable(var_name, var_type)
                    for subchild in child.get("children", []):
                        if subchild.get("type") == "Assignment":
                            expr = subchild.get("children", [])[0] if subchild.get("children") else None
                            self.visit(expr)
                        # Basic type checking could happen here
                        
        elif ntype in ["AssignmentStmt", "Assignment"]:
            label = node.get("label", "")
            var_name = label.split()[0] if label else ""
            
            if var_name and not self.lookup_variable(var_name):
                self.errors.append({
                    "message": f"Undeclared variable '{var_name}'",
                    "line": 0, "col": 0
                })
                
            for child in node.get("children", []):
                self.visit(child)
                
        elif ntype == "Identifier":
            var_name = node.get("label", "")
            if not self.lookup_variable(var_name):
                self.errors.append({
                    "message": f"Undeclared variable '{var_name}'",
                    "line": 0, "col": 0
                })
                
        elif ntype in ["IfStatement", "WhileLoop", "ForLoop"]:
            # These don't create scope on their own unless they have a Block,
            # but we visit their children.
            for child in node.get("children", []):
                self.visit(child)
                
        elif ntype == "CallExpr" or ntype == "FunctionCall":
            func_name = node.get("label", "").replace("()", "")
            # we allow 'print' as a built-in
            if func_name not in ["print", "printf", "scanf"] and not self.lookup_variable(func_name):
                self.errors.append({
                    "message": f"Call to undeclared function '{func_name}'",
                    "line": 0, "col": 0
                })
            for child in node.get("children", []):
                self.visit(child)
                
        else:
            for child in node.get("children", []):
                self.visit(child)

class Interpreter:
    def __init__(self, ast):
        self.ast = ast
        self.variables = {}
        self.output = []
        self.error = None
        self.steps = 0
        self.MAX_STEPS = 500
        
    def run(self):
        try:
            self.visit(self.ast)
        except Exception as e:
            self.error = str(e)
        return self.output, self.error
        
    def check_steps(self):
        self.steps += 1
        if self.steps > self.MAX_STEPS:
            raise Exception("Execution limits exceeded (infinite loop?)")
            
    def evaluate(self, node):
        if not node: return None
        
        ntype = node.get("type")
        label = node.get("label", "")
        children = node.get("children", [])
        
        if ntype == "Number":
            try:
                return int(label) if '.' not in label else float(label)
            except:
                return 0
        elif ntype == "String":
            # remove quotes and process simple escapes
            s = label[1:-1]
            return s.encode('utf-8').decode('unicode_escape')
        elif ntype == "Identifier":
            if label not in self.variables:
                raise Exception(f"Runtime Error: Variable '{label}' not initialized")
            return self.variables[label]
        elif ntype == "BinaryOp":
            left = self.evaluate(children[0]) if len(children) > 0 else 0
            right = self.evaluate(children[1]) if len(children) > 1 else 0
            
            if label == '+': return left + right
            if label == '-': return left - right
            if label == '*': return left * right
            if label == '/': 
                if right == 0: raise Exception("Division by zero")
                return int(left / right) if isinstance(left, int) and isinstance(right, int) else left / right
            if label == '%':
                if right == 0: raise Exception("Modulo by zero")
                return left % right
            if label == '>': return int(left > right)
            if label == '<': return int(left < right)
            if label == '>=': return int(left >= right)
            if label == '<=': return int(left <= right)
            if label == '==': return int(left == right)
            if label == '!=': return int(left != right)
            
        elif ntype in ["UnaryMinus", "UnaryOp"]:
            val = self.evaluate(children[0]) if children else 0
            if label == '-': return -val
            if label == '+': return val
            if label == '!': return int(not val)
            if label == '~': return ~val
            if label == '&': return val # simplify: just return the var value
            if label == '*': return val
            return -val
            
        return None

    def visit(self, node):
        if not node or self.error: return
        self.check_steps()
        
        ntype = node.get("type")
        label = node.get("label", "")
        children = node.get("children", [])
        
        if ntype == "Program":
            for child in children:
                self.visit(child)
                
        elif ntype == "FunctionDecl":
            # For simplicity, we just execute the body of 'main' immediately
            # In a real compiler, we'd store it and wait for a call
            for child in children:
                self.visit(child)
                
        elif ntype == "Block":
            for child in children:
                self.visit(child)
                
        elif ntype == "Declaration":
            for child in children:
                if child.get("type") == "VarDecl":
                    var_name = child.get("label", "")
                    self.variables[var_name] = 0
                    for subchild in child.get("children", []):
                        if subchild.get("type") == "Assignment":
                            expr = subchild.get("children", [])[0] if subchild.get("children") else None
                            self.variables[var_name] = self.evaluate(expr)
                        
        elif ntype == "AssignmentStmt":
            var_name = label.split()[0]
            expr = children[0] if children else None
            self.variables[var_name] = self.evaluate(expr)
            
        elif ntype == "IfStatement":
            cond_node = None
            then_node = None
            else_node = None
            for child in children:
                if child.get("type") == "Condition": cond_node = child.get("children", [None])[0]
                elif child.get("type") == "Then": then_node = child.get("children", [None])[0]
                elif child.get("type") == "Else": else_node = child.get("children", [None])[0]
                
            cond_val = self.evaluate(cond_node)
            if cond_val:
                self.visit(then_node)
            elif else_node:
                self.visit(else_node)
                
        elif ntype == "WhileLoop":
            cond_node = None
            body_node = None
            for child in children:
                if child.get("type") == "Condition": cond_node = child.get("children", [None])[0]
                elif child.get("type") == "Body": body_node = child.get("children", [None])[0]
                
            while self.evaluate(cond_node) and not self.error:
                self.visit(body_node)
                
        elif ntype == "FunctionCall" or ntype == "CallExpr":
            func_name = label.replace("()", "")
            if func_name in ("print", "printf"):
                if len(children) > 0:
                    first_val = self.evaluate(children[0])
                    if isinstance(first_val, str) and '%' in first_val and len(children) > 1:
                        import re
                        out_str = first_val
                        for arg in children[1:]:
                            val = self.evaluate(arg)
                            out_str = re.sub(r'%[a-zA-Z]', str(val), out_str, count=1)
                        out_str = out_str.replace('\\n', '\n')
                        self.output.append(out_str)
                    else:
                        out_str = " ".join(str(self.evaluate(arg)) for arg in children).replace('\\n', '\n')
                        self.output.append(out_str)
            elif func_name == "scanf":
                if len(children) > 1:
                    target = children[1]
                    if target.get("type") in ("UnaryOp", "UnaryMinus") and target.get("label") == "&":
                        target = target.get("children", [{}])[0]
                    if target.get("type") == "Identifier":
                        var_name = target.get("label")
                        self.variables[var_name] = 121
                        self.output.append(f"[System: scanf simulated input '121' to '&{var_name}']")
        
        elif ntype == "ReturnStatement":
            # We just stop execution for this simple interpreter
            pass
