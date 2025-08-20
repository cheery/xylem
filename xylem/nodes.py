from dataclasses import dataclass, field
from typing import List, Dict, Union, Optional
from .solver import LinearExpr, flex

@dataclass(eq=False)
class Node:
    children : List['Node'] = field(default_factory=list)
    name     : str = ""
    tag      : str = ""
    x : LinearExpr = field(default_factory=flex)
    y : LinearExpr = field(default_factory=flex)
    w : LinearExpr = field(default_factory=flex)
    h : LinearExpr = field(default_factory=flex)
    parent : Optional['Node'] = None
    computed_layout : str = "free"

    def __post_init__(self):
        for child in self.children:
            child.parent = self

@dataclass(eq=False)
class Selector:
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
        yield from dfs(m, node, [])

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
class Parameter:
    base : Selector
    name : str

@dataclass(eq=False)
class Relation:
    name : str
    args : List[Union[Selector, Parameter, str, int, float]]

