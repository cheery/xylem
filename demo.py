import pygame
from xylem.solver import *
from xylem.nodes import *

width = flex()
height = flex()
root = Node(
    children=[
        Node(w = promote(4*10), h = promote(4*10)),
        Node(w = promote(4*20), h = promote(4*15)),
        Node(w = promote(4*7),  h = promote(4*25)),
        Node(
            children=[
                Node(w = promote(4*10), h = promote(4*10)),
                Node(w = promote(4*20), h = promote(4*15)),
                Node(w = promote(4*7),  h = promote(4*25)),
            ],
            computed_layout='column'
        ),
    ], 
    x = promote(0),
    y = promote(0),
    w = width,
    h = height,
    computed_layout='row')

system = System({})

def layout(system, node):
    if node.computed_layout == 'row':
        x = promote(0)
        top = promote(0)
        bot = node.h

        for child in node.children:
            a = slack()
            system.add(eq(x - child.x))
            system.add(eq(top - child.y + a))
            system.add(eq(bot - (child.y+child.h+a)))
            #system.add(eq(bot - child.y - child.h - a))
            #system.add(eq(top - child.y))
            #system.add(les(child.y + child.h - bot, 0))
            x = child.x + child.w
        system.add(eq(x - node.w))
    if node.computed_layout == 'column':
        left  = promote(0)
        right = node.w
        y     = promote(0)
        for child in node.children:
            a = slack()
            system.add(eq(y - child.y))
            system.add(eq(left - child.x + a))
            system.add(eq(right - (child.x+child.w+a)))
            y = child.y + child.h
        system.add(eq(y - node.h))
            
    for child in node.children:
        layout(system, child)

layout(system, root)

def draw(screen, node, results, x, y):
    x += node.x.eval(results)
    y += node.y.eval(results)
    w = node.w.eval(results)
    h = node.h.eval(results)
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
