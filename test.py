#! /usr/bin/env python
# -*- coding: utf-8 -*-

import docker_reg
from pprint import pprint

images = {}
u1 = "docker1:5000"
u2 = "docker2:5000"

dreg1 = docker_reg.DockerRegAPI(url=u1)
dreg1.populate_image_details()

dreg2 = docker_reg.DockerRegAPI(url=u2)
dreg2.populate_image_details()

win, lose = dreg1.diff_image_list(dreg2.get_image_details())
print "Docker1 won those:"
for name, tags in win:
    for tag in tags:
        print "docker pull %s/%s:%s"
print "Docker2 won those:"
pprint(lose)

