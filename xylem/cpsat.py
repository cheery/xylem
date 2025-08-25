from ortools.sat.python import cp_model
from .constraints import Names, Slack, Flex, Dummy

class LineWrapper:
    def __init__(self, node):
        self.node = node

    def constrain(self, system):
        root = self.node
        first = root.children[0]
        system.model.Add(0 == system.get(first.left))
        system.model.Add(0 == system.get(first.top))
        pline = system.model.NewIntVar(0, 10000, "a")
        system.model.Add(system.get(first.bottom) <= pline)

        for prev, this in zip(root.children, root.children[1:]):
            br = system.model.NewBoolVar("br")
            line = system.model.NewIntVar(0, 10000, "a")
            system.model.Add(system.get(prev.right) == system.get(this.left)).OnlyEnforceIf(br.Not())
            system.model.Add(system.get(prev.top) == system.get(this.top)).OnlyEnforceIf(br.Not())
            system.model.Add(pline == line).OnlyEnforceIf(br.Not())
            system.model.Add(system.get(this.bottom) <= line)

            system.model.Add(pline == system.get(this.top)).OnlyEnforceIf(br)
            system.model.Add(0 == system.get(this.left)).OnlyEnforceIf(br)

            #system.model.Add(system.get(this.bottom) <= line)
            #system.add_objective({0: line})
            pline = line
        system.model.Add(pline == system.get(root.height))
        #system.add_objective({0: system.get(root.height)})

default_layouts = {
    "wrap": LineWrapper
}

class System:
    def __init__(self, layout_modules=None):
        self.layout_modules = default_layouts if layout_modules is None else layout_modules
        self.model = cp_model.CpModel()
        self.names = Names({})
        self.variables = {}
        self.objective = {}

    def get(self, expr):
        return expr.eval(self.get_var)

    def get_var(self, var):
        try:
            return self.variables[var]
        except KeyError:
            name = self.names.get(var)
            if isinstance(var, Flex):
                lb = -10000
                ub = +10000
            elif isinstance(var, Slack):
                lb = 0
                ub = +10000
            elif isinstance(var, Dummy):
                lb = 0
                ub = 0
            self.variables[var] = iv = self.model.NewIntVar(lb, ub, name)
            return iv

    def add_constraint(self, constraint):
        lhs = self.get(constraint.lhs)
        rhs = self.get(constraint.rhs)
        if constraint.comparator == "EQ":
            expr = lhs == rhs
        if constraint.comparator == "LE":
            expr = lhs <= rhs
        if constraint.comparator == "GE":
            expr = lhs >= rhs
        self.model.Add(expr)
        self.add_objective({k: self.get(v) for k, v in constraint.objective.items()})

    def add_objective(self, objective):
        for s, v in objective.items():
            obj = self.objective.setdefault(s, [])
            obj.append(v)

    def add_relation(self, name, root, args):
        if name == "layout":
            layout_name, = args
            mod = self.layout_modules[layout_name](root)
            mod.constrain(self)

    def results(self):
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 5.0
        solver.parameters.num_search_workers = 8

        for s in sorted(self.objective):
            obj = sum(self.objective[s])
            self.model.Minimize(obj)
            res = solver.Solve(self.model)
            if not (res == cp_model.OPTIMAL or res == cp_model.FEASIBLE):
                raise Exception("Unsatisfiable")
            self.model.Add(obj == int(solver.objective_value))
        return lambda var: solver.Value(self.get_var(var))
