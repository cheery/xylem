import pygame
from xylem.solver import *
from xylem.nodes import *
from xylem.stylesheet import parse_declarations

width = slack()
height = slack()
root = Node(
    children=[
        Node(width = promote(4*10), height = promote(4*10)),
        Node(width = promote(4*20), height = promote(4*15)),
        Node(width = promote(4*7),  height = promote(4*25)),
        Node(
            children=[
                Node(width = promote(4*10), height = promote(4*10)),
                Node(width = promote(4*20), height = promote(4*15)),
                Node(width = promote(4*7),  height = promote(4*25)),
            ],
            tag = 'column',
        ),
    ], 
    left = promote(0),
    top = promote(0),
    width = width,
    height = height,
    tag = 'row')

system = System({})

# thing 
# %thing
# & thing
# thing thang
# thing - thang
# thing | thang
# *
# thing :first
# thing :last

# expr.parameter
# -expr
# +expr
# x-y
# x+y
# x*y
# x/y

# Edge
# -a-
# (a)

# H: pattern
# V: pattern

# Dim x, !y: pattern
# @n x = y
# @n x <= y
# @n x >= y
# @n x >| y
# @n x <| y
# x;y=foo { }
# x=foo, y=bar { }
# x { }
# x :empty { }


ruleset = parse_declarations("""

& row {
  x;y=* { H: (x)(y) }
  x=*:first { H: Edge(x) }
  x=*:last  { H: (x)Edge }
  V: Edge-a-(*)-a-Edge
}

& column {
  x;y=* { V: (x)(y) }
  x=*:first { V: Edge(x) }
  x=*:last  { V: (x)Edge }
  H: Edge-a-(*)-a-Edge
}

""")

ruleset.resolve(system, (), root)

print(system.format(Names({})))

def draw(screen, node, results, x, y):
    x += node.left.eval(results)
    y += node.top.eval(results)
    w = node.width.eval(results)
    h = node.height.eval(results)
    pygame.draw.rect(screen, (200,200,200), (x,y,w,h), 1)
    for child in node.children:
        draw(screen, child, results, x, y)

pygame.init()

screen = pygame.display.set_mode((1280,640))

clock = pygame.time.Clock()

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            raise SystemExit

    results = system.results()
    screen.fill((30,30,30))
    draw(screen, root, results, 0, 0)

    pygame.display.flip()
    clock.tick(60)
