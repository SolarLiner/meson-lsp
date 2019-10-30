from typing import List

from mesonbuild import mparser
from mesonbuild.ast import AstVisitor


class VariablesVisitor(AstVisitor):
    variables: List[mparser.AssignmentNode]

    def __init__(self):
        super().__init__()
        self.variables = []

    def visit_AssignmentNode(self, node: mparser.AssignmentNode):
        self.variables.append(node)
