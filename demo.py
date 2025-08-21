import pygame
from xylem.solver import *
from xylem.nodes import *

width = flex()
height = flex()
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
            computed_layout='column'
        ),
    ], 
    left = promote(0),
    top = promote(0),
    width = width,
    height = height,
    computed_layout='row')

system = System({})

def layout(system, node):
    if node.computed_layout == 'row':
        x = promote(0)
        top = promote(0)
        bot = node.height

        for child in node.children:
            a = slack()
            system.add(eq(x - child.left))
            system.add(eq(top - child.top + a))
            system.add(eq(bot - (child.bottom+a)))
            x = child.right
        system.add(eq(x - node.width))
    if node.computed_layout == 'column':
        left  = promote(0)
        right = node.width
        y     = promote(0)
        for child in node.children:
            a = slack()
            system.add(eq(y - child.top))
            system.add(eq(left - child.left + a))
            system.add(eq(right - (child.right+a)))
            y = child.bottom
        system.add(eq(y - node.height))
            
    for child in node.children:
        layout(system, child)

layout(system, root)

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
