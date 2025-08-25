import pygame
from xylem.fixpoint import *
from xylem.nodes import *
from xylem.stylesheet import parse

from random import randint

width = slack()
height = slack()
H = flex()
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
        Node(
            children=[
                Node(width = promote(randint(10,80)),
                     height = promote(randint(10,32)))
                for _ in range(20)
            ],
            height = H,
            tag = 'paragraph'
        ),
    ], 
    left = promote(0),
    top = promote(0),
    width = width,
    height = height,
    tag = 'row')

system = System()

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


ruleset = parse("""

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

& paragraph {
  @ ().width = 200
  layout("knuth-plass")
}

""")

ruleset.resolve(system, (), root)

results = system.results()

def draw(screen, node, results, x, y):
    x += node.left.eval(results)
    y += node.top.eval(results)
    w = node.width.eval(results)
    h = node.height.eval(results)
    if node.tag == "paragraph":
        pygame.draw.rect(screen, (255,100,100), (x,y,w,h), 1)
    else:
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

    screen.fill((30,30,30))
    draw(screen, root, results, 100, 100)

    pygame.display.flip()
    clock.tick(60)
