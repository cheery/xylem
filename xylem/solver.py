from dataclasses import dataclass
from typing import Dict, Union

@dataclass(eq=False)
class AbstractVariable:
    pass

@dataclass(eq=False)
class Variable(AbstractVariable):
    slack : bool = False

@dataclass(eq=False)
class DVariable(AbstractVariable):
    pass

def dummy():
    x = DVariable()
    return LinearExpr({x: 1}, 0.0)

def flex():
    x = Variable(False)
    return LinearExpr({x: 1}, 0.0)

def slack():
    x = Variable(True)
    return LinearExpr({x: 1}, 0.0)

class Names:
    def __init__(self, names):
        self.names = names
        self.used  = set(names.values())
        self.counter = 0

    def get(self, var):
        if var in self.names:
            return self.names[var]
        while True:
            if isinstance(var, DVariable):
                candidate = f"d{self.counter}"
            elif var.slack:
                candidate = f"s{self.counter}"
            else:
                candidate = f"x{self.counter}"
            self.counter += 1
            if candidate not in self.used:
                self.names[var] = candidate
                self.used.add(candidate)
                return candidate

def promote(c):
    if isinstance(c, (int, float)):
        return LinearExpr({}, c)
    else:
        return c

@dataclass
class LinearExpr:
    coeffs: Dict[Variable, float]
    constant: float

    def __add__(self, other):
        other = promote(other)
        coeffs = self.coeffs.copy()
        for k, v in other.coeffs.items():
            coeffs[k] = coeffs.get(k, 0.0) + v
            if coeffs[k] == 0.0:
                coeffs.pop(k)
        return LinearExpr(coeffs, self.constant + other.constant)

    def __radd__(self, other):
        return promote(other) + self

    def __sub__(self, other):
        return self + promote(-other)

    def __rsub__(self, other):
        return promote(other) - self

    def __neg__(self):
        coeffs = {k: -v for k, v in self.coeffs.items()}
        return LinearExpr(coeffs, -self.constant)

    def __mul__(self, other):
        if not isinstance(other, (int, float)):
            raise TypeError("Can only multiply a LinearExpr by a scalar")
        coeffs = {k: v * other for k, v in self.coeffs.items()}
        return LinearExpr(coeffs, self.constant * other)

    def __rmul__(self, other):
        if not isinstance(other, (int, float)):
            raise TypeError("Can only multiply a LinearExpr by a scalar")
        coeffs = {k: other * v for k, v in self.coeffs.items()}
        return LinearExpr(coeffs, self.constant * other)

    def __truediv__(self, other):
        if not isinstance(other, (int, float)):
            raise TypeError("Can only multiply a LinearExpr by a scalar")
        coeffs = {k: v / other for k, v in self.coeffs.items()}
        return LinearExpr(coeffs, self.constant / other)

    @property
    def var(self):
        if len(self.coeffs) == 1:
            return next(iter(self.coeffs.keys()))
        raise Exception("constraint doesn't refer to one variable")

    def eval(self, results):
        constant = self.constant
        for k, s in self.coeffs.items():
            constant += results.get(k, 0.0)*s
        return constant

    def subs(self, *ms):
        coeffs  = {}
        constant = self.constant
        for k, s in self.coeffs.items():
            for m in ms:
                if k in m:
                    c = m[k]
                    for j, v in c.coeffs.items():
                        coeffs[j] = coeffs.get(j, 0.0) + v*s
                    constant += c.constant*s
                    break
            else:
                coeffs[k] = coeffs.get(k, 0.0) + s
        coeffs = {k: v for k, v in coeffs.items() if v != 0.0}
        return LinearExpr(coeffs, constant)

    def format(self, names):
        terms = []
        if self.constant != 0:
            terms.append(str(self.constant))
        for v in sorted(self.coeffs, key=id):
            coef = self.coeffs[v]
            nm = names.get(v)
            if coef < 0:
                if terms:
                    terms.append(" - ")
                else:
                    terms.append("-")
            elif terms:
                terms.append(" + ")
                
            if abs(coef) == 1:
                terms.append(nm)
            else:
                terms.append(f"{abs(coef)}*{nm}")
        if not terms:
            return "0"
        return "".join(terms)

    @property
    def is_zero(self):
        return self.constant == 0 and not self.coeffs

    def positive(self):
        if self.constant < 0:
            return -self
        else:
            return self

class System:
    def __init__(self, fixed):
        self.fixed = {k: dummy() + v for k, v in fixed.items()}
        self.constraints = set()
        self.Cu = {}
        self.Cv = {}
        self.O = {}
        self.resolve = False

    def add(self, constraint):
        self.constraints.add(constraint)
        _insert_equation_(self.Cu, self.Cv, constraint.expr.subs(self.fixed))
        _insert_objective_(self.O, constraint.objective)
        self.resolve = True

    def discard(self, constraint):
        if constraint in self.constraints:
            _remove_objective_(self.O, constraint.objective)
            _remove_equation_(self.Cu, self.Cv, self.O, constraint.marker)
            self.constraints.discard(constraint)
            self.resolve = True

    def results(self):
        self.solve()
        results = {}
        for k, c in self.Cv.items():
            results[k] = c.constant
        for k, c in self.Cu.items():
            results[k] = c.constant
        return results

    def solve(self):
        if self.resolve:
            _minimize_(self.Cu, self.Cv, self.O)
            self.resolve = False

    def refine(self, fixed):
        subs = {}
        for k, v in fixed.items():
            if k in self.fixed:
                subs[k] = k - self.fixed[k]
                self.fixed[k] = LinearExpr(self.fixed[k].coeffs, v)
            else:
                self.fixed[k] = dummy() + v
        _subs_(subs, self.Cu, self.Cv, self.O)
        _dual_simplex_(Cu, Cv, O)

    def format(self, names):
        out = ["objective:"]
        for k, c in self.O.items():
            out.append(f"  [{k}] = {c.format(names)}")
        out.append("equations:")
        for k, c in self.Cu.items():
            out.append(f"  {names.get(k)} = {c.format(names)}")
        out.append('  ----')
        for k, c in self.Cv.items():
            out.append(f"  {names.get(k)} = {c.format(names)}")
        return "\n".join(out)

def _insert_equation_(Cu, Cv, c):
    c = c.subs(Cu, Cv)
    for k, v in c.coeffs.items():
        if not isinstance(k, DVariable) and not k.slack:
            _pivot_(Cu, c, k, Cu, Cv)
            break
    else:
        c = c.positive()
        while c.constant > 0.0:
            k = min(_entering_variable_(c), key=id, default=None)
            if k is None:
                raise Exception("unsatisfiable")
            p = c.constant / -c.coeffs[k]
            j = min(_leaving_variable_(Cv, k, lambda q: q < p), key=_lvf_, default=(p,None))[1]
            if j is None:
                _pivot_(Cv, c, k, Cu, Cv)
            else:
                _pivot_(Cv, remove(Cv,j), k, Cu, Cv)
            c = c.subs(Cv)

def _entering_variable_(c):
    for k, s in c.coeffs.items():
        if isinstance(k, DVariable):
            continue
        if s >= 0.0:
            continue
        yield k

def _insert_objective_(O, o):
    zero = promote(0.0)
    for s, c in o.items():
        O[s] = O.get(s, zero) + c

def _remove_objective_(O, o):
    zero = promote(0.0)
    for s, c in o.items():
        O[s] = O.get(s, zero) - c

def _minimize_(Cu, Cv, O):
    for s in O:
        O[s] = O[s].subs(Cu, Cv)
    k = min(_lex_entering_variable_(O), key=id, default=None)
    while k is not None:
        j = min(_leaving_variable_(Cv, k, lambda q: True), key=_lvf_, default=(0,None))[1]
        if j is None:
            raise Exception("unbounded")
        _pivot_(Cv, _remove_(Cv, j), k, Cu, Cv, O)
        k = min(_lex_entering_variable_(O), default=None, key=id)

def _lex_entering_variable_(O):
    strengths = tuple(sorted(O))
    zero_vec = tuple(0.0 for _ in strengths)
    for k in set().union(*[o.coeffs.keys() for o in O.values()]):
        if isinstance(k, DVariable):
            continue
        vec = tuple(O[s].coeffs.get(k, 0.0) for s in strengths)
        if vec < zero_vec:
            yield k

def _remove_equation_(Cu, Cv, O, marker):
    j = min(_leaving_variable_(Cv, marker, lambda q: True), key=_lvf_, default=(0,None))[1]
    if j is not None:
        return _pivot_({}, remove(Cv, j), marker, Cu, Cv, O)
    j = min(_leaving_variable_p_(Cv, marker), key=_lvf_, default=(0,None))[1]
    if j is not None:
        return _pivot_({}, remove(Cv, j), marker, Cu, Cv, O)
    j = min((j for j in Cu if marker in Cu[j].coeffs), key=id, default=None)
    if j is not None:
        return _pivot_({}, remove(Cu, j), marker, Cu, Cv, O)

def _remove_(C, k):
    return C.pop(k) - LinearExpr({k: 1.0}, 0.0)

def _leaving_variable_(Cv, k, cutoff):
    for j, d in Cv.items():
        if (w := d.coeffs.get(k, 0.0)) < 0.0:
            q = d.constant / -w
            if cutoff(q):
                yield q, j

def _leaving_variable_p_(Cv, k):
    for j, d in Cv.items():
        if (w := d.coeffs.get(k, 0.0)) > 0.0:
            q = d.constant / w
            yield q, j

def _dual_simplex_(Cu, Cv, O):
    j = min((k for k,c in Cv.items() if c.constant < 0.0), key=id, default=None)
    while j is not None:
        k = min(_dual_simplex_entering_variable_(Cv[j], O), key=_lvf_, default=(0,None))[1]
        if k is None:
            raise Exception("Infeasible")
        _pivot_(Cv, _remove_(Cv, j), k, Cu, Cv, O)
        j = min((k for k,c in Cv.items() if c.constant < 0.0), key=id, default=None)

def _dual_simplex_entering_variable_(row, O):
    strengths = tuple(sorted(O))
    for k, a_ik in row.coeffs.items():
        if isinstance(k, DVariable) or a_ik <= 0.0:
            continue
        vec = tuple(O[s].coeffs.get(k, 0.0) / a_ik for s in strengths)
        yield vec, k

def _pivot_(C, c, k, *Upd):
    coeffs = c.coeffs.copy()
    constant = c.constant
    s = coeffs.pop(k)
    for h in coeffs.keys():
        coeffs[h] = coeffs[h] / -s
    constant /= -s
    C[k] = LinearExpr(coeffs, constant)
    _subs_(C, *Upd)

def _subs_(C, *Upd):
    for U in Upd:
        for i in U:
            U[i] = U[i].subs(C)

def _lvf_(p):
    x, y = p
    return x, id(y)

@dataclass(eq=False)
class Constraint:
    expr      : LinearExpr
    objective : Dict[int, LinearExpr]
    marker    : AbstractVariable

def eq(expr, strength=None):
    if strength is None:
        marker = dummy()
        return Constraint(expr + marker, {}, marker)
    else:
        s1 = slack()
        s2 = slack()
        return Constraint(expr + s1 - s2, {strength: s1 + s2}, s1)

def le(expr, strength=None):
    if strength is None:
        s1 = slack()
        return Constraint(expr + s1, {}, s1)
    else:
        s1 = slack()
        s2 = slack()
        return Constraint(expr + s1 - s2, {strength: s2}, s1)

def ge(expr, strength=None):
    if strength is None:
        s1 = slack()
        return Constraint(expr - s1, {}, s1)
    else:
        s1 = slack()
        s2 = slack()
        return Constraint(expr - s1 + s2, {strength: s2}, s1)

def les(expr, strength):
    s1 = slack()
    return Constraint(expr + s1, {strength: s1}, s1)

def ges(expr, strength):
    s1 = slack()
    return Constraint(expr - s1, {strength: s1}, s1)

def system1():
    xl = flex()
    xr = flex()
    xm = flex()
    sys = System({})

    sys.add(Constraint(xl + xr - 2*xm,     {}, None))
    sys.add(Constraint((xr - 90) - flex(), {}, None))
    sys.add(Constraint((xl - 50) - flex(), {}, None))
    sys.add(Constraint((xr - xm - 50) - flex(), {}, None))

    names = Names({xl.var: 'xl', xr.var: 'xr', xm.var: 'xm'})

    print(sys.format(names))

if __name__ == "__main__":
    system1()
