"""Topology builder placeholder."""

class Topology:
    def __init__(self, nodes=None):
        self.nodes = nodes or []

    def add_node(self, node):
        self.nodes.append(node)
