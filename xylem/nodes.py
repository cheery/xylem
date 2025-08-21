from dataclasses import dataclass, field
from typing import Any, List, Dict, Union, Optional
from .solver import LinearExpr, flex, slack
from itertools import product

@dataclass(eq=False)
class Node:
    children : List['Node'] = field(default_factory=list)
    name     : str = ""
    tag      : str = ""
    left   : LinearExpr = field(default_factory=flex)
    top    : LinearExpr = field(default_factory=flex)
    width  : LinearExpr = field(default_factory=flex)
    height : LinearExpr = field(default_factory=flex)
    parent : Optional['Node'] = None
    computed_layout : str = "free"

    def __post_init__(self):
        for child in self.children:
            child.parent = self

    @property
    def bottom(self):
        return self.top + self.height

    @property
    def right(self):
        return self.left + self.width

    @property
    def xcenter(self):
        return self.left + self.width*0.5

    @property
    def ycenter(self):
        return self.top + self.height*0.5

    def orient_x(self, ancestor, x):
        if self == ancestor:
            return x
        while self.parent != ancestor:
            x += self.parent.left
            self = self.parent
        return x

    def orient_y(self, ancestor, y):
        if self == ancestor:
            return y
        while self.parent != ancestor:
            y += self.parent.top
            self = self.parent
        return y

    def relative_to(self):
        def _match_(node):
            result = []
            while node != self:
                result.append(node.parent.children.index(node))
                node = node.parent
            return result
        return _match_

@dataclass(eq=False)
class Selector:
    pass

@dataclass(eq=False)
class Expression:
    pass

@dataclass(eq=False)
class Declaration:
    pass

@dataclass(eq=False)
class Root(Selector):
    def match(self, root):
        yield root

@dataclass(eq=False)
class Some(Selector):
    pattern : str
    hashed : bool = False

    def match(self, root):
        m = matcher(self.hashed, self.pattern)
        if m(root):
            yield root
        yield from dfs(m, root, [])

@dataclass(eq=False)
class Descendant(Selector):
    parent : Selector
    pattern : str
    hashed : bool = False

    def match(self, root):
        m = matcher(self.hashed, self.pattern)
        for node in self.parent.match(root):
            yield from dfs(m, node, [])

@dataclass(eq=False)
class Child(Selector):
    parent : Selector
    pattern : str
    hashed : bool = False

    def match(self, root):
        m = matcher(self.hashed, self.pattern)
        for node in self.parent.match(root):
            for child in node.children:
                if m(child):
                    yield child

@dataclass(eq=False)
class First(Selector):
    parent : Selector

    def match(self, root):
        for node in self.parent.match(root):
            if node.parent is None:
                yield node
            elif node.parent.children.index(node) == 0:
                yield node

@dataclass(eq=False)
class Last(Selector):
    parent : Selector

    def match(self, root):
        for node in self.parent.match(root):
            if node.parent is None:
                yield node
            elif node.parent.children.index(node) == len(node.parent.children) - 1:
                yield node

@dataclass(eq=False)
class OneOf(Selector):
    seq : List[Selector]
    def match(self, root):
        for sel in self.seq:
            yield from sel.match(root)

def dfs(f, node, output=[]):
    for child in node.children:
        if f(child):
            output.append(child)
        else:
            dfs(f, child, output)
    return output

def matcher(hashed, pattern):
    if hashed:
        return lambda node: node.name == pattern
    else:
        return lambda node: node.tag == pattern

@dataclass(eq=False)
class Arg(Expression):
    base : Expression
    index : int

    def eval(self, env, root):
        return env[-1-self.index]

@dataclass(eq=False)
class Parameter(Expression):
    base : Expression
    name : str

    def eval(self, env, root):
        base = self.base.eval(env, root)
        x = getattr(base, self.name)
        if name in ("left", "right", "xcenter"):
            x = base.orient_x(root, x)
        elif name in ("top", "bottom", "ycenter"):
            x = base.orient_y(root, x)
        return x

@dataclass(eq=False)
class Op(Expression): # Use with operator interface.
    op   : Any
    args : List[Expression]

    def eval(self, env, root):
        return self.op(*(x.eval(env, root) for x in self.args))

@dataclass(eq=False)
class Dim(Declaration):
    body : Declaration
    slack : bool = False

    def resolve(self, env, root):
        x = slack() if self.slack else flex()
        self.body.resolve(env + (x,), root)

@dataclass(eq=False)
class Descend(Declaration):
    sel  : Selector
    body : Declaration

    def resolve(self, system, env, root):
        for node in self.sel.match(root):
            self.body.resolve(system, env, node)

@dataclass(eq=False)
class Match(Declaration):
    args : List[Selector]
    body : Declaration

    def resolve(self, system, env, root):
        for p in product(*(sel.match(root) for sel in self.args)):
            self.body.resolve(system, env + p, root)

@dataclass(eq=False)
class AtEmpty(Declaration):
    sel  : Selector
    body : Declaration

    def resolve(self, system, env, root):
        first = next(self.sel.match(root), None)
        if first is None:
            self.body.resolve(system, env, root)

@dataclass(eq=False)
class Adjacent(Declaration):
    sel  : Selector
    body : Declaration

    def resolve(self, system, env, root):
        seq = list(self.sel.match(root))
        seq.sort(key=root.relative_to())
        for a, b in zip(seq, seq[1:]):
            self.body.resolve(system, env + (a,b), root)

@dataclass(eq=False)
class AddToSystem:
    op   : Any
    args : List[Any]

    def resolve(self, system, env, root):
        args =  [arg.eval(env, root) if isinstance(arg, Expression) else arg for arg in args]
        c = self.op(*args)
        system.add(c)
