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
        self.nudgets = set()

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

    def add_node(self, node):
        if node.nudgeteer is not None:
            self.nudgets.add(node)
        for child in node.children:
            self.add_node(child)

    def solvers(self):
        for node, mod in self.layouts.items():
            yield mod(node)
        for node in self.nudgets:
            yield node.nudgeteer(node)

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
        
        for g in self.solvers():
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

