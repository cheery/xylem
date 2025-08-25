from . import knuthplass
from . import solver

default_layouts = {
    "knuth-plass": knuthplass.Solver
}

class System:
    def __init__(self, layout_modules=None):
        self.connected = ConnectedVariables()
        self.layout_modules = default_layouts if layout_modules is None else layout_modules
        self.layouts = {}

    def add_constraint(self, constraint):
        group = self.connected.get(constraint.marker)
        group.constraints.add(constraint)
        for var in constraint.expr.coeffs:
            self.connected.union(group, self.connected.get(var))
        for c in constraint.objective.values():
            for var in c.coeffs:
                self.connected.union(group, self.connected.get(var))

    def add_relation(self, name, root, args):
        if name == "layout":
            layout_name, = args
            self.layouts[root] = self.layout_modules[layout_name]

    def results(self):
        systems = {}
        graph = {}
        marks = {}
        covers = {}
        for group in self.connected.groups:
            if group.constraints:
                sys = solver.System()
                for c in group.constraints:
                    sys.add(c)
                systems[group] = sys
            graph[group] = set()
            marks[group] = set()
            covers[group] = group.cover
        for node, mod in self.layouts.items():
            g = mod(node)
            consumes, produces = g.details()
            gconsumes = set(self.connected.get(x) for x in consumes)
            gproduces = set(self.connected.get(x) for x in produces)
            for src in gconsumes:
                adj = graph[src]
                adj.add(g)
            adj = graph.setdefault(g, set())
            adj.update(gproduces)
            for dst in gproduces:
                if dst in marks:
                    marks[dst].update(produces & dst.cover)
                else:
                    marks[dst] = produces & dst.cover
                    covers[dst] = dst.cover
            marks[g] = consumes
            covers[g] = consumes | produces

        fixed = {}
        for comp in reversed(tarjans_scc(graph)):
            frozen = set()
            def solver_step(old):
                new = old.copy()
                notdone = False
                for g in comp:
                    if isinstance(g, Group):
                        if g.constraints:
                            sys = systems[g]
                            mrk = marks[g] | frozen
                            notdone |= sys.refine({x: old[x] for x in mrk if x in old})
                            new.update(sys.results())
                    else:
                        if all(x in old for x in marks[g]):
                            frozen.update(marks[g])
                            new.update(g.solve(old))
                        else:
                            notdone = True
                return notdone, new
            notdone = True
            while notdone:
                notdone, new = solver_step(fixed)
                fixed.update(new)

            #fixed_comp = {x: fixed[x] for g in comp for x in marks[g] if x in fixed}
            #def has_grip(xs):
            #    grip = True
            #    for g in comp:
            #        if not isinstance(g, Group):
            #            grip &= all(x in xs for x in marks[g])
            #    return grip
            #def bracketed_fixed_point(var, lo, hi, solver_step, xs, tol, max_iter=50):
            #    for _ in range(max_iter):
            #        mid = 0.5*(lo+hi)
            #        trial = solver_step(xs | {var: mid})
            #        fmid = trial[var] - mid
            #        if abs(fmid) < tol:
            #            return trial[var]
            #        if fmid > 0:
            #            lo = mid
            #        else:
            #            hi = mid
            #    print("panicking")
            #    return 0.5*(lo+hi)
            #feedback = set.union(*(covers[g] for g in comp))
            #feedback &= set.union(*(marks[g] for g in comp))
            #for _ in range(10):
            #    good = False
            #    lo_bound = fixed_comp.copy()
            #    hi_bound = fixed_comp.copy()
            #    for _ in range(100):
            #        old = fixed_comp.copy()
            #        # raw update pass
            #        new = solver_step(old)
            #        # apply relaxation uniformly
            #        for k, v in new.items():
            #            fixed_comp[k] = a*v + (1-a)*old.get(k, v)
            #            lo_bound[k] = min(lo_bound.get(k,v), v)
            #            hi_bound[k] = max(hi_bound.get(k,v), v)
            #        # check convergence
            #        if any(k not in old for k in new):
            #            continue
            #        if max((abs(fixed_comp[k] - old[k]) for k in new), default=0.0) < tol:
            #            good = True
            #            break
            #    else:
            #        print("no convergence")
            #        for var in feedback:
            #            lo = lo_bound[var]
            #            hi = hi_bound[var]
            #            print("BRACKETING", lo, hi)
            #            val = bracketed_fixed_point(var, lo, hi, solver_step, fixed_comp, tol=tol)
            #            fixed_comp[var] = val
            #        fixed_comp |= solver_step(fixed_comp)
            #    if good: break
            #else:
            #    print("complete failure")
            #fixed.update(fixed_comp)
        return fixed

class Group:
    def __init__(self):
        self.parent = None
        self.constraints = set()
        self.cover = set()

class ConnectedVariables:
    def __init__(self):
        self.variables = {}
        self.groups = set()

    def fresh_group(self):
        self.groups.add(group := Group())
        return group

    def get(self, variable):
        group = self.variables.get(variable)
        if group is None:
            self.variables[variable] = group = self.fresh_group()
            group.cover.add(variable)
            return group
        return self.find(group)

    def find(self, group):
        if group.parent is None:
            return group
        while group.parent.parent is not None:
            group.parent = group.parent.parent
        return group.parent

    def union(self, group1, group2):
        group1 = self.find(group1)
        group2 = self.find(group2)
        if group1 is group2:
            return group1
        group2.parent = group1
        group1.constraints.update(group2.constraints)
        group2.constraints = None
        group1.cover.update(group2.cover)
        group2.cover = None
        self.groups.discard(group2)
        return group1

def tarjans_scc(graph):
    index = 0
    stack = []
    on_stack = set()
    indices = {}
    lowlink = {}
    result = []

    def strongconnect(v):
        nonlocal index
        indices[v] = index
        lowlink[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)

        for w in graph.get(v, []):
            if w not in indices:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], indices[w])

        if lowlink[v] == indices[v]:
            comp = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                comp.append(w)
                if w == v:
                    break
            result.append(comp)

    for v in graph:
        if v not in indices:
            strongconnect(v)

    return result

