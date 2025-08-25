import pygame
from xylem.cpsat import System
from xylem.nodes import *
from xylem.stylesheet import parse
from xylem.constraints import Flex, Slack, Constant

from random import randint

width = Slack()
height = Slack()
H = Flex()
root = Node(
    children=[
        Node(width = Constant(4*10), height = Constant(4*10)),
        Node(width = Constant(4*20), height = Constant(4*15)),
        Node(width = Constant(4*7),  height = Constant(4*25)),
        Node(
            children=[
                Node(width = Constant(4*10), height = Constant(4*10)),
                Node(width = Constant(4*20), height = Constant(4*15)),
                Node(width = Constant(4*7),  height = Constant(4*25)),
            ],
            tag = 'column',
        ),
        Node(
            children=[
                Node(width = Constant(randint(10,80)),
                     height = Constant(randint(10,32)))
                for _ in range(20)
            ],
            height = H,
            tag = 'paragraph'
        ),
    ], 
    left = Constant(0),
    top = Constant(0),
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

@ ().height <= 200

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
  @1 *.left = 0
  @1 *.top  = 0
  @1 ().width = 100
  @ ().width = ().height
  layout("wrap")
}

""")

ruleset.resolve(system, (), root)

results = system.results()

def disp(node, results, x, y, depth):
    x += node.left.eval(results)
    y += node.top.eval(results)
    w = node.width.eval(results)
    h = node.height.eval(results)
    print(" "*depth + f"{node.tag} {node.name} {x} {y} {w} {h}")
    for child in node.children:
        disp(child, results, x, y, depth+2)

disp(root, results, 0, 0, 0)

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
