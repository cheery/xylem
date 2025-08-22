import re
import operator
from .nodes import (
    Root, Some, Child, Descendant, AnyChild, First, Last, OneOf,
    Arg, Parameter, Op, Number,
    Dim, Descend, Match, AtEmpty, Adjacent, Anchor, VisualFormat, Many,
    Edge, Space, Cell,
)

class Context:
    def __init__(self, selectors, dims, index, expects_selector=False):
        self.selectors = selectors
        self.dims = dims
        self.index = index
        self.expects_selector = expects_selector

    def intros(self, selector):
        self.index += 1
        self.selectors.append((selector, -self.index))
        return Arg(-self.index)

    def lookup(self, name):
        if name not in self.dims:
            self.index += 1
            self.dims[name] = -self.index
        return Arg(self.dims[name])

    def mapper(self):
        shift = len(self.selectors) + len(self.dims)
        mapping = {}
        k = 0
        for index in self.dims.values():
            mapping[index] = k
            k += 1
        for _, index in reversed(self.selectors):
            mapping[index] = k
            k += 1
        def _f_(i):
            if i >= 0:
                return i + shift
            else:
                return mapping[i]
        return _f_
        
    def wrap(self, declaration):
        for dim in sorted(self.dims):
            declaration = Dim(declaration, slack=True)
        if self.selectors:
            m = [sel for sel, _ in self.selectors]
            return Match(m, declaration)
        else:
            return declaration 

TOKEN_RE = re.compile(
    r"""
    \s*(
        \#.* |
        \{ | \} | :empty | :first | :last |           # braces & pseudos
        H: | V: |                                     # visual format heads
        @\d+ | @ |                                    # anchor head
        <= | >= | <\| | >\| | = |                     # relation ops
        \(\) |                                        # root
        \(| \) |                                      # parens
        - | \| | ; | , | : | \. |                     # punctuation
        \* |                                          # wildcard
        %[_A-Za-z][_A-Za-z0-9]* |                     # %name
        [_A-Za-z][_A-Za-z0-9]* |                      # identifier
        \d+\.\d+ | \d+ |                              # number
        .                                             # catch remaining stuff
    )
    """,
    re.VERBOSE,
)

def tokenize(s: str):
    toks = [t for t in TOKEN_RE.findall(s) if t.strip() != ""]
    toks = [t for t in toks if not t.startswith("#")]
    return toks


def _is_ident(tok):
    return bool(tok) and re.match(r"^[_A-Za-z]", tok)

class SelParser:
    """Selector parser (no lookahead across declaration boundaries)."""

    def __init__(self, toks, i0=0):
        self.toks = toks
        self.i = i0

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self, expected=None):
        tok = self.peek()
        if tok is None:
            raise SyntaxError("Unexpected end of input (selector)")
        if expected is not None and tok != expected:
            raise SyntaxError(f"Expected {expected!r}, got {tok!r} (selector)")
        self.i += 1
        return tok

    def at_end(self): return self.i >= len(self.toks)

    def parse_primary(self):
        tok = self.peek()

        if tok == "&":
            self.take("&")
            nxt = self.peek()
            if nxt and nxt.startswith("%"):
                self.take()
                sel = Some(nxt[1:], hashed=True)
            elif _is_ident(nxt):
                self.take()
                sel = Some(nxt, hashed=False)
            else:
                raise SyntaxError("`&` must be followed by tag or %name")
            return self.apply_suffix(sel)

        tok = self.take()
        if tok == "()":
            base = Root()
        elif tok == "*":
            base = AnyChild(Root())
        elif tok.startswith("%"):
            base = Child(Root(), tok[1:], hashed=True)
        elif tok not in (":first", ":last", "-", "|", "{", "}", ";", ",", ":"):
            # identifier
            base = Child(Root(), tok, hashed=False)
        else:
            raise SyntaxError(f"Unexpected token {tok!r} in selector")

        return self.apply_suffix(base)

    def apply_suffix(self, sel):
        while self.peek() in (":first", ":last"):
            s = self.take()
            sel = First(sel) if s == ":first" else Last(sel)
        return sel

    def _is_primary_start(self, tok):
        if tok in (None, "|", "{", "}", ";", ",", ":empty"):
            return False
        if tok in ("()", "*", "&"):
            return True
        if tok.startswith("%"):
            return True
        # plain identifier
        return _is_ident(tok)

    # ---- rebasing helpers -------------------------------------------
    def _attach_child(self, lhs, rhs):
        if isinstance(rhs, First):
            return First(self._attach_child(lhs, rhs.parent))
        if isinstance(rhs, Last):
            return Last(self._attach_child(lhs, rhs.parent))
        if isinstance(rhs, OneOf):
            return OneOf([self._attach_child(lhs, s) for s in rhs.seq])
        if isinstance(rhs, AnyChild):
            return AnyChild(lhs)
        if isinstance(rhs, Child):
            return Child(lhs, rhs.pattern, getattr(rhs, "hashed", False))
        if isinstance(rhs, Root):
            return lhs
        raise SyntaxError(f"Cannot attach (child) {type(rhs).__name__}")

    def _attach_desc(self, lhs, rhs):
        if isinstance(rhs, First):
            return First(self._attach_desc(lhs, rhs.parent))
        if isinstance(rhs, Last):
            return Last(self._attach_desc(lhs, rhs.parent))
        if isinstance(rhs, OneOf):
            return OneOf([self._attach_desc(lhs, s) for s in rhs.seq])
        if isinstance(rhs, Child):
            return Descendant(lhs, rhs.pattern, getattr(rhs, "hashed", False))
        if isinstance(rhs, Root):
            return lhs
        if isinstance(rhs, AnyChild):
            raise SyntaxError("`foo - *` requires a DescendantAny node (not in IR).")
        raise SyntaxError(f"Cannot attach (descendant) {type(rhs).__name__}")

    # ---- chain (whitespace child / '-' descendant) ------------------
    def parse_chain(self):
        left = self.parse_primary()
        while True:
            nxt = self.peek()
            if nxt == "-":
                self.take("-")
                right = self.parse_primary()
                left = self._attach_desc(left, right)
            elif self._is_primary_start(nxt):
                right = self.parse_primary()
                left = self._attach_child(left, right)
            else:
                break
        return left

    # ---- disjunction -------------------------------------------------
    def parse_selector(self):
        sel = self.parse_chain()
        items = [sel]
        while self.peek() == "|":
            self.take("|")
            items.append(self.parse_chain())
        return items[0] if len(items) == 1 else OneOf(items)


def parse_selector_from(tokens, i0=0):
    p = SelParser(tokens, i0)
    node = p.parse_selector()
    return node, p.i


# ==== EXPRESSION PARSER ==============================================


class ExprParser:
    def __init__(self, toks, i0, env_stack, context):
        self.toks = toks
        self.i = i0
        self.env_stack = env_stack
        self.context = context

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self, expected=None):
        tok = self.peek()
        if tok is None:
            raise SyntaxError("Unexpected end of input (expression)")
        if expected is not None and tok != expected:
            raise SyntaxError(f"Expected {expected!r}, got {tok!r} (expression)")
        self.i += 1
        return tok

    def _lookup_var(self, name):
        for depth, env in enumerate(reversed(self.env_stack)):
            if name in env:
                return Arg(depth)
        return None

    def parse_primary(self):
        tok = self.peek()
        if tok == "(":
            self.take("(")
            expr, j = parse_expression_from(self.toks, self.i, self.env_stack, self.context)
            self.i = j
            if self.peek() != ")":
                raise SyntaxError("Expected ')'")
            self.take(")")
            return expr
    
        if tok and re.match(r"^\d+(\.\d+)?$", tok):
            self.take()
            val = float(tok) if "." in tok else int(tok)
            return Number(val)
    
        # Identifiers / selectors
        if tok in ("()", "&") or tok.startswith("%") or re.match(r"^[_A-Za-z*]", tok):
            if tok == "*":
                self.take("*")
                expr = AnyChild(Root())
                expr = self.context.intros(expr)
            elif re.match(r"^[_A-Za-z]", tok) and not (tok in ("()", "&") or tok.startswith("%")):
                name = self.take()
                bound = self._lookup_var(name)
                if bound is not None:
                    expr = bound
                elif self.peek() == "." or self.context.expects_selector:
                    expr = Child(Root(), name)
                    expr = self.context.intros(expr)
                else:
                    expr = self.context.lookup(name)
            else:
                expr, j = parse_selector_from(self.toks, self.i)
                expr = self.context.intros(expr)
                self.i = j
            while self.peek() == ".":
                self.take(".")
                attr = self.take()
                expr = Parameter(expr, attr)
            return expr
    
        raise SyntaxError(f"Unexpected token {tok!r} in expression")

    # ---- unary -------------------------------------------------------
    def parse_unary(self):
        if self.peek() == "+":
            self.take("+")
            return self.parse_unary()
        if self.peek() == "-":
            self.take("-")
            return Op(operator.neg, [self.parse_unary()])
        return self.parse_primary()

    # ---- mul/div -----------------------------------------------------
    def parse_muldiv(self):
        expr = self.parse_unary()
        while self.peek() in ("*", "/"):
            op = self.take()
            rhs = self.parse_unary()
            expr = Op(operator.mul, [expr, rhs]) if op == "*" else Op(operator.truediv, [expr, rhs])
        return expr

    # ---- add/sub -----------------------------------------------------
    def parse_addsub(self):
        expr = self.parse_muldiv()
        while self.peek() in ("+", "-"):
            op = self.take()
            rhs = self.parse_muldiv()
            expr = Op(operator.add, [expr, rhs]) if op == "+" else Op(operator.sub, [expr, rhs])
        return expr

def parse_expression_from(tokens, i0, env_stack, context, in_dim=False):
    p = ExprParser(tokens, i0, env_stack, context)
    if in_dim:
        expr = p.parse_primary()
    else:
        expr = p.parse_addsub()
    return expr, p.i

# ==== VISUAL FORMAT (tiles) ==========================================

class VFParser:
    def __init__(self, toks, i0=0, env_stack=None):
        self.toks = toks
        self.i = i0
        self.env_stack = env_stack or []
        self.context = Context([], {}, 0)

    def peek(self): return self.toks[self.i] if self.i < len(self.toks) else None
    def take(self, expected=None):
        tok = self.peek()
        if tok is None: raise SyntaxError("Unexpected end in visual format")
        if expected is not None and tok != expected:
            raise SyntaxError(f"Expected {expected!r}, got {tok!r} in visual format")
        self.i += 1
        return tok

    def parse(self):
        head = self.take()
        if head not in ("H:", "V:"):
            raise SyntaxError("VisualFormat must start with H: or V:")
        column = (head == "V:")

        tiles = []
        # tile list until end of line / declaration boundary (handled by caller)
        while True:
            tok = self.peek()
            if tok in (None, "}", "{"):
                break
            if tok == "Edge":
                self.take()
                tiles.append(Edge())
                continue
            if tok == "-":
                # - expr -
                self.take("-")
                self.context.expects_selector = False
                expr, j = parse_expression_from(self.toks, self.i, self.env_stack, self.context, True)
                self.i = j
                if self.peek() != "-":
                    raise SyntaxError("Expected closing '-' for space")
                self.take("-")
                tiles.append(Space(expr))
                continue
            if tok == "(":
                # ( expr ) as Cell
                self.take("(")
                self.context.expects_selector = True
                expr, j = parse_expression_from(self.toks, self.i, self.env_stack, self.context)
                self.i = j
                if self.peek() != ")":
                    raise SyntaxError("Expected ')'")
                self.take(")")
                tiles.append(Cell(expr))
                continue
            break
        f = self.context.mapper()
        tiles = [tile.shift(f) for tile in tiles]
        return self.context.wrap(VisualFormat(column, tiles)), self.i


def parse_visual_format_from(tokens, i0=0, env_stack=None):
    p = VFParser(tokens, i0, env_stack)
    node, j = p.parse()
    return node, j


# ==== DECLARATION PARSER =============================================

class DeclParser:
    def __init__(self, toks, i0=0, env_stack=None):
        self.toks = toks
        self.i = i0
        # env_stack is a list of dicts (scope), for Arg binding
        self.env_stack = env_stack or []

    def peek(self): return self.toks[self.i] if self.i < len(self.toks) else None
    def take(self, expected=None):
        tok = self.peek()
        if tok is None: raise SyntaxError("Unexpected end in declaration")
        if expected is not None and tok != expected:
            raise SyntaxError(f"Expected {expected!r}, got {tok!r} in declaration")
        self.i += 1
        return tok

    # ---- block body: { decl* } --------------------------------------
    def parse_block_body(self, env_ext):
        env_stack, self.env_stack = self.env_stack, self.env_stack + env_ext
        self.take("{")
        decls = []
        while True:
            tok = self.peek()
            if tok is None:
                raise SyntaxError("Unterminated block")
            if tok == "}":
                self.take("}")
                break
            decls.append(self.parse_declaration())
        self.env_stack = env_stack
        return Many([d for d in decls if d is not None])

    # ---- Dim a,b,!c: body -------------------------------------------
    def parse_dim(self):
        self.take("Dim")
        names = []
        # list a , b , !c  :
        while True:
            tok = self.peek()
            if tok == ":":
                self.take(":")
                break
            if tok == ",":
                self.take(",")
                continue
            if not tok:
                raise SyntaxError("Unexpected end in Dim")
            names.append(self.take())
        # Introduce one Dim per name and parse body once *inside* each Dim scope
        # We parse the body text after ':' once per var (as in your IR).
        
        env_stack, self.env_stack = self.env_stack, self.env_stack + names
        body = self.parse_declaration() #if self.peek() == "{" else self.parse_declaration(env)
        self.env_stack = env_stack
        # Note: The IR Dim(node, slack=bool) wraps a body expecting it to use the arg.
        # Binding: when entering Dim we push a new arg name into scope, then parse body.
        # But your IR handles the runtime var introduction; we just emit Dim nodes.
        decls = []
        for nm in names:
            slack = True
            if nm.startswith("!"):
                slack = False
                nm = nm[1:]
            # For De Bruijn binding in body, we *could* parse body under extended scope,
            # but your runtime Dim will inject the arg. Keep parse-time scope as-is,
            # and rely on runtime to wire env (simplifies mutual nesting).
            decls.append(Dim(body, slack=slack))
        return Many(decls)

    # ---- @ … anchors -------------------------------------------------
    def parse_anchor(self):
        tok = self.take()
        if tok == "@":
            strength = None
        else:
            # @N
            strength = int(tok[1:])
        context = Context([], {}, 0)
        # parse: expr ( = | <= | >= | <| | >| ) expr
        lhs, j = parse_expression_from(self.toks, self.i, self.env_stack, context)
        self.i = j
        rel = self.take()  # =, <=, >=, <|, >|
        rhs, j = parse_expression_from(self.toks, self.i, self.env_stack, context)
        self.i = j

        # map operator
        if   rel == "=":  relfn = eval("eq")
        elif rel == "<=": relfn = eval("le")
        elif rel == ">=": relfn = eval("ge")
        elif rel == "<|": relfn = eval("les")
        elif rel == ">|": relfn = eval("ges")
        else:
            raise SyntaxError(f"Unknown relation {rel}")

        f = context.mapper()
        args = [Op(operator.sub, [lhs.shift(f), rhs.shift(f)])]
        if strength is not None:
            args.append(strength)
        return context.wrap(Anchor(relfn, args))

    # ---- Head forms before { body } ---------------------------------
    # Forms:
    #   selector { … }
    #   selector :empty { … }
    #   x=sel1 , y=sel2 { … }     (Match)
    #   x ; y = selector { … }    (Adjacent)
    #   H: …   |  V: …            (VisualFormat)
    def parse_head_or_vf(self):
        tok = self.peek()

        # VisualFormat
        if tok in ("H:", "V:"):
            node, j = parse_visual_format_from(self.toks, self.i, self.env_stack)
            self.i = j
            return node

        # Try selector head (possibly followed by :empty)
        try:
            sel, j = parse_selector_from(self.toks, self.i)
        except Exception:
            sel = None

        # Otherwise: bindings head
        # 1) x=sel , y=sel { … }
        # 2) x ; y = sel  { … }
        # Parse name or names
        names = []
        if _is_ident(self.peek()):

            names.append(self.take())  # first name
            if self.peek() == ";":
                # Adjacent: x ; y = selector
                self.take(";")
                names.append(self.take())  # second name
                self.take("=")
                sel, j = parse_selector_from(self.toks, self.i)
                self.i = j
                body = self.parse_block_body(names)
                return Adjacent(sel, body)

            # Else, Match bindings list: x=sel , y=sel2
            if self.peek() == "=":
                selectors = []
                self.take("=")
                sel, j = parse_selector_from(self.toks, self.i)
                self.i = j
                selectors.append(sel)
                while self.peek() == ",":
                    self.take(",")
                    nm = self.take()
                    names.append(nm)
                    self.take("=")
                    sel, j = parse_selector_from(self.toks, self.i)
                    self.i = j
                    selectors.append(sel)
                body = self.parse_block_body(names)
                return Match(selectors, body)

        if sel is not None:
            self.i = j
            # optional :empty { … }
            if self.peek() == ":empty":
                self.take(":empty")
                body = self.parse_block_body([])
                return AtEmpty(sel, body)
            # Plain Descend
            body = self.parse_block_body([])
            return Descend(sel, body)
        raise SyntaxError(f"Expected head (selector or bindings), got {self.peek()!r}")

    # ---- Single declaration (one of the above) ----------------------
    def parse_declaration(self):
        tok = self.peek()
        if tok is None:
            return None

        if tok == "Dim":
            return self.parse_dim()

        if tok.startswith("@") or tok == "@":
            return self.parse_anchor()

        node = self.parse_head_or_vf()
        return node


def parse_declarations(source: str):
    tokens = tokenize(source)
    p = DeclParser(tokens, 0, env_stack=[])
    decls = []
    while p.peek() is not None:
        decls.append(p.parse_declaration())
    return Many([d for d in decls if d is not None])


