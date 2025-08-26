import pygame
from xylem.cascade import System
from xylem.nodes import *
from xylem.stylesheet import parse

from random import randint

class Resizer:
    def __init__(self, width, height):
        self.width = width
        self.height = height

    def __call__(self, node):
        return ResizeSolver(self, node)

class ResizeSolver:
    def __init__(self, rez, node):
        self.rez = rez
        self.node = node

    def details(self):
        return set(), {self.node.width.var, self.node.height.var}

    def solve(self, fixed):
        return {
            self.node.width.var: self.rez.width,
            self.node.height.var: self.rez.height,
        }

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 640

width = slack()
height = slack()
H = flex()
root = Node(
    nudgeteer = Resizer(SCREEN_WIDTH, SCREEN_HEIGHT),
    children = [
        Node(
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
            tag = 'row')
    ],
    left = promote(0),
    top = promote(0),
    width = width,
    height = height,
)

system = System()
system.add_node(root)

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

x=* { Dim !a: H: Edge-a-(*)-a-Edge @0 a >= 0 }
x=* { Dim !a: V: Edge-a-(*)-a-Edge @0 a >= 0 }

& row {
  x;y=* { H: (x)(y) }
  x=*:first { H: Edge(x) }
  x=*:last  { H: (x)Edge }
  x=* { Dim a: V: Edge-a-(x)-a-Edge @0 a = 0 }
}

& column {
  x;y=* { V: (x)(y) }
  x=*:first { V: Edge(x) }
  x=*:last  { V: (x)Edge }
  x=* { Dim a: H: Edge-a-(x)-a-Edge @0 a = 0 }
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

screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)

clock = pygame.time.Clock()


while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            raise SystemExit
        if event.type == pygame.VIDEORESIZE:
            SCREEN_WIDTH, SCREEN_HEIGHT = event.size
            root.nudgeteer.width = SCREEN_WIDTH
            root.nudgeteer.height = SCREEN_HEIGHT
            results = system.results()

    screen.fill((30,30,30))
    draw(screen, root, results, 0, 0)

    pygame.display.flip()
    clock.tick(60)
