from dataclasses import dataclass
from typing import Dict, Union

@dataclass(eq=False)
class Expression:
    def __add__(self, other):
        return Add(self, other)

    def __sub__(self, other):
        return Sub(self, other)

    def __mul__(self, other):
        return Mul(self, other)

    def __truediv__(self, other):
        return Div(self, other)

    def __neg__(self):
        return Neg(self)

@dataclass(eq=False)
class AbstractVariable(Expression):
    def eval(self, f):
        return f(self)

@dataclass(eq=False)
class Flex(AbstractVariable):
    pass

@dataclass(eq=False)
class Slack(AbstractVariable):
    pass

@dataclass(eq=False)
class Dummy(AbstractVariable):
    pass

class Names:
    def __init__(self, names):
        self.names = names
        self.used  = set(names.values())
        self.counter = 0

    def get(self, var):
        if var in self.names:
            return self.names[var]
        while True:
            if isinstance(var, Dummy):
                candidate = f"d{self.counter}"
            elif isinstance(var, Slack):
                candidate = f"s{self.counter}"
            elif isinstance(var, Flex):
                candidate = f"x{self.counter}"
            self.counter += 1
            if candidate not in self.used:
                self.names[var] = candidate
                self.used.add(candidate)
                return candidate

@dataclass(eq=False)
class Constant(Expression):
    value : Union[float, int]

    def eval(self, f):
        return self.value

@dataclass(eq=False)
class BinaryOp(Expression):
    lhs : Expression
    rhs : Expression

@dataclass(eq=False)
class UnaryOp(Expression):
    rhs : Expression

@dataclass(eq=False)
class Add(BinaryOp):
    def eval(self, f):
        return self.lhs.eval(f) + self.rhs.eval(f)

@dataclass(eq=False)
class Sub(BinaryOp):
    def eval(self, f):
        return self.lhs.eval(f) - self.rhs.eval(f)

@dataclass(eq=False)
class Mul(BinaryOp):
    def eval(self, f):
        return self.lhs.eval(f) * self.rhs.eval(f)

@dataclass(eq=False)
class Div(BinaryOp):
    def eval(self, f):
        return self.lhs.eval(f) / self.rhs.eval(f)

@dataclass(eq=False)
class Neg(UnaryOp):
    def eval(self, f):
        return -self.rhs.eval(f)

@dataclass(eq=False)
class Constraint:
    lhs : Expression
    rhs : Expression
    comparator : str # "LE", "GE", "EQ"
    objective : Dict[int, Expression]

def eq(lhs, rhs, strength=None):
    if strength is None:
        return Constraint(lhs, rhs, "EQ", {})
    else:
        s1 = Slack()
        s2 = Slack()
        return Constraint(
            Add(lhs, s1), Add(rhs, s2),
            "EQ", {strength: Add(s1, s2)})

def le(lhs, rhs, strength=None):
    if strength is None:
        return Constraint(lhs, rhs, "LE", {})
    else:
        s1 = Slack()
        return Constraint(
            lhs, Add(rhs, s1),
            "LE", {strength: s1})

def ge(lhs, rhs, strength=None):
    if strength is None:
        return Constraint(lhs, rhs, "GE", {})
    else:
        s1 = Slack()
        return Constraint(
            Add(lhs, s1), rhs,
            "GE", {strength: s1})

def les(lhs, rhs, strength=None):
    if strength is None:
        return eq(lhs, rhs)
    s1 = Slack()
    return Constraint(
        Add(lhs, s1), rhs,
        "EQ", {strength: s1})

def ges(lhs, rhs, strength=None):
    if strength is None:
        return eq(lhs, rhs)
    s1 = Slack()
    return Constraint(
        lhs, Add(rhs, s1),
        "EQ", {strength: s1})
