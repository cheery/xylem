from . import knuthplass
from . import solver

default_layouts = {
    "knuth-plass": knuthplass
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
            consumes, produces = mod.details(node)
            gconsumes = set(self.connected.get(x) for x in consumes)
            gproduces = set(self.connected.get(x) for x in produces)
            for src in gconsumes:
                adj = graph[src]
                adj.add((mod, node))
            adj = graph.setdefault((mod, node), set())
            adj.update(gproduces)
            for dst in gproduces:
                if dst in marks:
                    marks[dst].update(produces & dst.cover)
                else:
                    marks[dst] = produces & dst.cover
                    covers[dst] = dst.cover
            marks[mod, node] = consumes
            covers[mod, node] = consumes | produces

        fixed = {}
        #a = 0.1
        #tol = 1e-4
        for comp in reversed(tarjans_scc(graph)):
            def solver_step(old):
                new = old.copy()
                for g in comp:
                    if isinstance(g, Group):
                        if g.constraints:
                            sys = systems[g]
                            mrk = marks[g]
                            sys.refine({x: old[x] for x in mrk if x in old})
                            new.update(sys.results())
                    else:
                        mod = g[0]
                        if all(x in old for x in marks[g]):
                            new.update(mod.solve(*g[1:], old))
                return new
            def has_grip(xs):
                grip = True
                for g in comp:
                    if not isinstance(g, Group):
                        mod = g[0]
                        grip &= all(x in xs for x in marks[g])
                return grip
            fixed_comp = {x: fixed[x] for g in comp for x in marks[g] if x in fixed}
            while not has_grip(fixed_comp):
                fixed_comp.update(solver_step(fixed_comp))
            fixed_comp.update(solver_step(fixed_comp))
            if len(comp) > 1:
                fixed_comp.update(solver_step(fixed_comp))
                print("trying global solver")
                fixed_comp = powell_minimize(solver_step, fixed_comp)
                #fixed_comp = cma_es_minimize(solver_step, fixed_comp)
                print("done")
            fixed.update(fixed_comp)

        #def bracketed_fixed_point(var, lo, hi, solver_step, xs, tol, max_iter=50):
        #    # classic bisection
        #    for _ in range(max_iter):
        #        mid = 0.5*(lo+hi)
        #        trial = solver_step(xs | {var: mid})
        #        fmid = trial[var] - mid
        #        if abs(fmid) < tol:
        #            return trial[var]
        #        if fmid > 0:
        #            lo = mid   # solver wants bigger
        #        else:
        #            hi = mid   # solver wants smaller
        #    print("panicking")
        #    return 0.5*(lo+hi)
        #for comp in reversed(tarjans_scc(graph)):
        #    feedback = set.union(*(covers[g] for g in comp))
        #    feedback &= set.union(*(marks[g] for g in comp))
        #    fixed_comp = {x: fixed[x] for g in comp for x in marks[g] if x in fixed}
        #    for _ in range(10):
        #        good = False
        #        lo_bound = fixed_comp.copy()
        #        hi_bound = fixed_comp.copy()
        #        for _ in range(100):
        #            old = fixed_comp.copy()
        #            # raw update pass
        #            new = solver_step(old)
        #            # apply relaxation uniformly
        #            for k, v in new.items():
        #                fixed_comp[k] = a*v + (1-a)*old.get(k, v)
        #                lo_bound[k] = min(lo_bound.get(k,v), v)
        #                hi_bound[k] = max(hi_bound.get(k,v), v)
        #            # check convergence
        #            if any(k not in old for k in new):
        #                continue
        #            if max((abs(fixed_comp[k] - old[k]) for k in new), default=0.0) < tol:
        #                good = True
        #                break
        #        else:
        #            print("no convergence")
        #            for var in feedback:
        #                lo = lo_bound[var]
        #                hi = hi_bound[var]
        #                print("BRACKETING", lo, hi)
        #                val = bracketed_fixed_point(var, lo, hi, solver_step, fixed_comp, tol=tol)
        #                fixed_comp[var] = val
        #            fixed_comp |= solver_step(fixed_comp)
        #        if good: break
        #    else:
        #        print("complete failure")
        #    fixed.update(fixed_comp)

        #def update(xs):
        #    for k, v in xs.items():
        #        if k in fixed:
        #            fixed[k] = v*a + (1-a)*fixed[k]
        #        else:
        #            fixed[k] = v
        #    notdone = True
        #    count = 0
        #    while notdone:
        #        notdone = False
        #        count += 1
        #        if count >= 1000:
        #            break
        #        for g in comp:
        #            if isinstance(g, Group):
        #                if g in systems:
        #                    sys = systems[g]
        #                    mrk = marks[g]
        #                    notdone |= sys.refine({x:v for x,v in fixed.items() if x in mrk}, tol)
        #                    update(sys.results())
        #            else:
        #                mod = g[0]
        #                if all(x in fixed for x in marks[g]):
        #                    update(mod.solve(*g[1:], fixed))
        #                else:
        #                    notdone = True
        #    if count != 1:
        #        print("K", count)
        return fixed

def powell_minimize(solver_step, xs0, tol=1e-3, max_iter=10):
    """
    Derivative-free Powell-style minimization to reduce ||xs - solver_step(xs)||^2.
    xs0: dict of initial variable values
    solver_step: function(xs: dict) -> dict
    """
    xs = xs0.copy()
    # initial directions: one per variable
    directions = [{k: 1.0 if k == var else 0.0 for k in xs} for var in xs]

    def obj(xs_dict):
        # squared norm of difference
        new = solver_step(xs_dict)
        return sum((new[k] - xs_dict[k])**2 for k in xs_dict)

    for it in range(max_iter):
        print(it)
        xs_start = xs.copy()
        f_start = obj(xs)
        max_improve = 0.0
        new_direction = None

        for ui in directions:
            # line search along ui
            #def line_obj(alpha):
            #    trial = {k: xs[k] + alpha*ui[k] for k in xs}
            #    return obj(trial)

            best_val, best_alpha = adaptive_line_search(xs, ui, solver_step, 2)
            # simple 1D search: evaluate at -1, 0, +1 step sizes
            #alphas = [-1.0, 0.0, 1.0]
            #best_alpha = 0.0
            #best_val = line_obj(0.0)
            #for a in alphas:
            #    val = line_obj(a)
            #    if val < best_val:
            #        best_val = val
            #        best_alpha = a
            # update xs along ui
            xs = {k: xs[k] + best_alpha*ui[k] for k in xs}

            improve = f_start - best_val
            if improve > max_improve:
                max_improve = improve
                new_direction = {k: xs[k] - xs_start[k] for k in xs}

        # replace the direction of largest improvement
        if new_direction is not None:
            directions[-1] = new_direction

        # check convergence
        if max(abs(xs[k] - xs_start[k]) for k in xs) < tol:
            break

    return xs

def adaptive_line_search(xs, direction, solver_step, max_steps=20, tol=1e-3):
    alpha = 0.0
    step = 1.0
    best_alpha = 0.0
    best_val = sum((solver_step(xs)[k] - xs[k])**2 for k in xs)
    
    for _ in range(max_steps):
        trial = {k: xs[k] + alpha*direction[k] for k in xs}
        val = sum((solver_step(trial)[k] - trial[k])**2 for k in xs)
        if val < best_val - tol:
            best_val = val
            best_alpha = alpha
            alpha += step  # keep going in this direction
            step *= 1.5   # accelerate if successful
        else:
            step *= -0.5  # reverse and shrink if overshot
            alpha += step
        if abs(step) < tol:
            break
    return best_val, best_alpha

import numpy as np

def cma_es_minimize(solver_step, xs0, sigma=100.0, popsize=100, max_iter=50, tol=1e-3):
    """
    CMA-ES inspired global search for black-box function solver_step.
    xs0: dict of initial variables
    sigma: initial step size
    popsize: number of candidates per generation
    """
    keys = list(xs0.keys())
    n = len(keys)
    
    # initial mean vector
    mu = np.array([xs0[k] for k in keys], dtype=float)
    # covariance matrix (identity initially)
    C = np.eye(n) * sigma**2

    def obj(vec):
        xs_dict = {k: v for k,v in zip(keys, vec)}
        new = solver_step(xs_dict)
        return sum((new[k] - xs_dict[k])**2 for k in keys)

    for iteration in range(max_iter):
        # sample candidates
        candidates = np.random.multivariate_normal(mu, C, popsize)
        # evaluate objective
        fitness = np.array([obj(c) for c in candidates])
        # select best half
        indices = fitness.argsort()[:popsize//2]
        best = candidates[indices]
        # update mean
        mu_new = best.mean(axis=0)
        # update covariance roughly
        diffs = best - mu_new
        C_new = np.cov(diffs.T) + 1e-8*np.eye(n)  # small regularizer
        mu, C = mu_new, C_new

        if max(np.abs(diffs).max(), np.linalg.norm(mu - mu_new)) < tol:
            break

    # return final best layout
    return {k: v for k,v in zip(keys, mu)}


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

