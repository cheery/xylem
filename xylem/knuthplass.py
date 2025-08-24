def details(node):
    consumes = set()
    produces = set()
    produces.add(node.height.var)
    consumes.update(node.width.coeffs)
    for child in node.children:
        produces.add(child.left.var)
        produces.add(child.top.var)
        consumes.update(child.width.coeffs)
        consumes.update(child.height.coeffs)
    return consumes, produces

def solve(node, results):
    values = {}
    y = 0
    for line in knuth_plass(node, results):
        x = 0
        for child in line:
            values[child.left.var] = x
            values[child.top.var] = y
            x += child.width.eval(results)
        tallest = max((c.height.eval(results) for c in line), default=0)
        y += tallest
    values[node.height.var] = y
    return values

def knuth_plass(node, results):
    line_width = node.width.eval(results)
    children = node.children
    n = len(children)
    INF = float("inf")

    # Quick pre-check: if any child > line_width, force it into its own line
    forced_lines = []
    buffer = []
    for child in children:
        if child.width.eval(results) > line_width:
            if buffer:
                forced_lines.append(buffer)
                buffer = []
            forced_lines.append([child])
        else:
            buffer.append(child)
    if buffer:
        forced_lines.append(buffer)

    # If any forced lines were needed, just return them
    if len(forced_lines) != 1 or (forced_lines and forced_lines[0] != children):
        return forced_lines

    # Otherwise, do proper DP on the whole sequence
    cost = [INF] * (n + 1)
    breaks = [-1] * (n + 1)
    cost[0] = 0

    cumw = [0]
    for child in children:
        cumw.append(cumw[-1] + child.width.eval(results))

    def line_badness(i, j):
        width = cumw[j] - cumw[i]
        if width > line_width:
            return INF
        slack = line_width - width
        return slack ** 3

    for j in range(1, n + 1):
        for i in range(0, j):
            b = line_badness(i, j)
            if b < INF and cost[i] + b < cost[j]:
                cost[j] = cost[i] + b
                breaks[j] = i

    lines = []
    j = n
    while j > 0:
        i = breaks[j]
        if i == -1:
            # fallback: force one child per line
            lines.append([children[j - 1]])
            j -= 1
        else:
            lines.append(children[i:j])
            j = i
    lines.reverse()
    return lines

