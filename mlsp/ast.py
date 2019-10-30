import logging
import os
from pathlib import Path
from typing import Optional, List
from urllib import parse

from mesonbuild import mparser, environment, mesonlib
from mesonbuild.ast import AstInterpreter, AstVisitor
# from .workspace import Workspace
from mesonbuild.mparser import ParseException

logger = logging.getLogger(__name__)


class LSPInterpreter(AstInterpreter):
    def __init__(self, workspace: 'mlsp.workspace.Workspace', subdir: str, visitors: Optional[List[AstVisitor]] = None):
        self.workspace = workspace
        self.ast = None
        source_root = parse.unquote(parse.urlparse(workspace.root_uri).path)
        super().__init__(source_root, subdir, visitors)

    def load_root_meson_file(self):
        meson_uri = os.path.join(self.workspace.root_uri, "meson.build")
        logger.debug('%s - %s', self.workspace.documents, meson_uri)

        if meson_uri in self.workspace.documents:
            document = self.workspace.get_document(meson_uri)
            self.ast = mparser.Parser(document.contents, '').parse()
            self.visit()
        else:
            super().load_root_meson_file()

    def visit(self, extra_visitors: Optional[List[AstVisitor]] = None):
        all_visitors = (self.visitors or []) + (extra_visitors or [])
        if self.ast:
            for visitor in all_visitors:
                self.ast.accept(visitor)
        else:
            logger.warning("AST Not built!")

    def func_subdir(self, node, args, kwargs):
        args = self.flatten_args(args)
        if len(args) > 1:
            raise ParseException("`subdir` only accepts 1 argument; found %d instead" % len(args), "",
                                 node.lineno,
                                 node.colno)
        if not isinstance(args[0], str):
            raise ParseException("`subdir` expects a string argument; found %s instead" % str(type(args[0])), "",
                                 node.lineno, node.colno)
        prev_subdir = self.subdir
        subdir = os.path.join(prev_subdir, args[0])
        build_filename = os.path.join(subdir, environment.build_filename)
        absname = os.path.join(self.source_root, build_filename)
        symlinkless_dir = os.path.join(self.source_root, build_filename)
        if symlinkless_dir in self.visited_subdirs:
            logger.info('Trying to enter %s which has already been visited --> skipping', args[0])
            return
        self.visited_subdirs[symlinkless_dir] = True
        abs_uri = Path(absname).as_uri()
        if abs_uri not in self.workspace.documents:
            if not os.path.isfile(absname):
                logger.info('Unable to find build file %s --> skipping', build_filename)
                return
            with open(absname, encoding='utf8') as f:
                code = f.read()
            assert (isinstance(code, str))
            try:
                codeblock = mparser.Parser(code, subdir).parse()
            except mesonlib.MesonException as me:
                me.file = build_filename
                raise me
        else:
            try:
                document = self.workspace.get_document(abs_uri)
                codeblock = mparser.Parser(document.contents).parse()
            except mesonlib.MesonException as me:
                me.file = build_filename
                raise me
        self.subdir = subdir
        for visitor in self.visitors:
            codeblock.accept(visitor)
        self.evaluate_codeblock(codeblock)
        self.subdir = prev_subdir
