from importlib import resources
from lark import Lark, Transformer, Tree, v_args

from .nodes import (
    Root, Some, Child, Descendant, AnyChild, First, Last, OneOf,
    Arg, Self, Parameter, Op, Number, String,
    Dim, Descend, Match, AtEmpty, Adjacent, Anchor, VisualFormat, Many,
    Edge, Space, Cell, Relation
)
from .constraints import (
    Add, Sub, Mul, Div, Neg,
    eq, le, ge, les, ges
)

def _load_parser_():
    lark_file = resources.files(__package__).joinpath("stylesheet.lark")
    with lark_file.open("r", encoding="utf8") as f:
        grammar = f.read()
    return Lark(grammar, start="start", parser="lalr")

def parse(text):
    return ASTBuilder().transform(parser.parse(text))

def many(decls):
    if len(decls) == 1:
        return decls[0]
    return Many(decls)

class ASTBuilder(Transformer):
    def __init__(self):
        self.env = []
        self.inline_selectors = []
        self.inline_dims      = {}
        self.inline_index     = 0

    def __default__(self, x,y,z):
        raise SyntaxError(str((x,y,z)))

    # ---entering scope---
    @v_args(inline=True)
    def bind(self, name):
        self.env.append(name)
        return name

    @v_args(inline=True)
    def inline_selector(self, sel):
        self.inline_index += 1
        self.inline_selectors.append((sel, -self.inline_index))
        return Arg(-self.inline_index)

    @v_args(inline=True)
    def argument(self, name):
        for depth, n in enumerate(reversed(self.env)):
            if n == name:
                return Arg(depth)
        return self.inline_selector(Child(Root(), name))

    @v_args(inline=True)
    def itself(self):
        return Self()

    @v_args(inline=True)
    def spaced_ident(self, name):
        for depth, n in enumerate(reversed(self.env)):
            if n == name:
                return Arg(depth)
        if name not in self.inline_dims:
            self.inline_index += 1
            self.inline_dims[name] = -self.inline_index
        return Arg(self.inline_dims[name])
 
    # ---leaving scope, helpers---
    def mapper(self):
        shift = len(self.inline_selectors) + len(self.inline_dims)
        mapping = {}
        k = 0
        for index in self.inline_dims.values():
            mapping[index] = k
            k += 1
        for _, index in reversed(self.inline_selectors):
            mapping[index] = k
            k += 1
        def _f_(i):
            if i >= 0:
                return i + shift
            else:
                return mapping[i]
        return _f_
         
    def wrap(self, declaration):
        dims = self.inline_dims
        sels = self.inline_selectors
        self.inline_dims = {}
        self.inline_selectors = []
        self.inline_index = 0
        for dim in sorted(dims):
            declaration = Dim(declaration, slack=True)
        if sels:
            m = [sel for sel, _ in sels]
            return Match(m, declaration)
        else:
            return declaration 

    # ---tokens---
    def NUMBER(self, tok):
        return tok[:]

    def STRING(self, tok):
        return tok[1:-1]

    def IDENT(self, tok):
        return tok[:]

    def PERCENT_IDENT(self, tok):
        return tok[1:]

    # ---declarations---
    @v_args(inline=True)
    def empty(self):
        return Many([])

    @v_args(inline=True)
    def start(self, decls):
        return many(decls)

    @v_args(inline=True)
    def many(self, decls):
        return many(decls)

    @v_args(inline=True)
    def declarations(self, decl):
        return [decl]

    @v_args(inline=True)
    def prepend(self, decl, decls):
        decls.insert(0, decl)
        return decls

    # ---selectors---
    def selector(self, oneof):
        if len(oneof) == 1:
            return oneof[0]
        else:
            return OneOf(oneof)

    @v_args(inline=True)
    def anychild_root(self):
        return AnyChild(Root())

    @v_args(inline=True)
    def anychild(self, sel):
        return AnyChild(sel)

    @v_args(inline=True)
    def root(self):
        return Root()

    @v_args(inline=True)
    def tagged(self, name):
        return Child(Root(), name, False)

    @v_args(inline=True)
    def named(self, name):
        return Child(Root(), name, True)

    @v_args(inline=True)
    def some_tagged(self, name):
        return Some(name, False)

    @v_args(inline=True)
    def some_named(self, name):
        return Some(name, True)

    @v_args(inline=True)
    def first(self, sel):
        return First(sel)

    @v_args(inline=True)
    def last(self, sel):
        return Last(sel)

    @v_args(inline=True)
    def child_tagged(self, sel, name):
        return Child(sel, name, False)

    @v_args(inline=True)
    def child_named(self, sel, name):
        return Child(sel, name, True)

    @v_args(inline=True)
    def descendant_tagged(self, sel, name):
        return Descendant(sel, name, False)

    @v_args(inline=True)
    def descendant_named(self, sel, name):
        return Descendant(sel, name, True)

    # ---expressions---
    def add_op(self, items):
        return Op(Add, items)

    def sub_op(self, items):
        return Op(Sub, items)

    def mul_op(self, items):
        return Op(Mul, items)

    def div_op(self, items):
        return Op(Div, items)

    def neg(self, items):
        return Op(Neg, items)

    @v_args(inline=True)
    def number(self, text):
        return Number(float(text))

    @v_args(inline=True)
    def string(self, text):
        return String(text)

    @v_args(inline=True)
    def param(self, base, *names):
        for name in names:
            base = Parameter(base, name)
        return base

    # ---anchor---
    @v_args(inline=True)
    def anchor_req(self, lhs, relop, rhs):
        return self.anchor(None, lhs, relop, rhs)

    @v_args(inline=True)
    def anchor(self, s, lhs, relop, rhs):
        if relop == "=":
            relfn = eq
        elif relop == "<=":
            relfn = le
        elif relop == ">=":
            relfn = ge
        elif relop == "<|":
            relfn = les
        elif relop == ">|":
            relfn = ges
        f = self.mapper()
        lhs = lhs.shift(f)
        rhs = rhs.shift(f)
        if s is not None:
            return self.wrap(Anchor(relfn, [lhs, rhs, int(s)]))
        else:
            return self.wrap(Anchor(relfn, [lhs, rhs]))

    # ---relation---
    @v_args(inline=True)
    def relation_decl(self, name, args):
        if args is None:
            args = []
        f = self.mapper()
        args = [arg.shift(f) for arg in args]
        return self.wrap(Relation(name, args))

    def arg_list(self, args):
        return args

    # ---heads / vf ---
    def horizontal(self, tiles):
        f = self.mapper()
        tiles = [tile.shift(f) for tile in tiles]
        return self.wrap(VisualFormat(False, tiles))

    def vertical(self, tiles):
        f = self.mapper()
        tiles = [tile.shift(f) for tile in tiles]
        return self.wrap(VisualFormat(True, tiles))

    @v_args(inline=True)
    def at_empty(self, sel, body):
        return AtEmpty(sel, body)

    @v_args(inline=True)
    def descend(self, sel, body):
        return Descend(sel, body)

    @v_args(inline=True)
    def match(self, bindings, body):
        for _ in bindings:
            self.env.pop()
        return Match(bindings, body)

    def bindings(self, binds):
        return binds

    @v_args(inline=True)
    def binding(self, name, sel):
        return sel

    @v_args(inline=True)
    def adjacent_decl(self, x, y, sel, body):
        return Adjacent(sel, body)

    # ---tiles---
    @v_args(inline=True)
    def edge(self):
        return Edge()

    @v_args(inline=True)
    def space(self, expr):
        return Space(expr)

    @v_args(inline=True)
    def cell(self, expr):
        return Cell(expr)

    @v_args(inline=True)
    def dim_decl(self, dims, decl):
        for _ in dims:
            self.env.pop()
        decl = many(decl)
        for s in reversed(dims):
            decl = Dim(decl, slack=s)
        return decl

    def dim_name_list(self, items):
        return items

    def slack(self, tok):
        return True

    def flex(self, tok):
        return False

parser = _load_parser_()
