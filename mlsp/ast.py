import logging
import os
import sys
from pathlib import Path
from typing import Optional, List
from urllib import parse

from mesonbuild import mparser, environment, mesonlib
from mesonbuild.ast import AstInterpreter, AstVisitor

# from .workspace import Workspace

logger = logging.getLogger(__name__)


class LSPInterpreter(AstInterpreter):
    def __init__(self, workspace: 'mlsp.workspace.Workspace', subdir: str, visitors: Optional[List[AstVisitor]]):
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
            if self.visitors:
                for visitor in self.visitors:
                    self.ast.accept(visitor)
        else:
            super().load_root_meson_file()

    def func_subdir(self, node, args, kwargs):
        args = self.flatten_args(args)
        if len(args) != 1 or not isinstance(args[0], str):
            sys.stderr.write(
                'Unable to evaluate subdir({}) in AstInterpreter -> skipping\n'.format(args)
            )
            return
        prev_subdir = self.subdir
        subdir = os.path.join(prev_subdir, args[0])
        absdir = os.path.join(self.source_root, subdir)
        build_filename = os.path.join(subdir, environment.build_filename)
        absname = os.path.join(self.source_root, build_filename)
        symlinkless_dir = os.path.join(self.source_root, build_filename)
        if symlinkless_dir in self.visited_subdirs:
            sys.stderr.write(
                'Trying to enter {} which has already been visited --> skipping\n'.format(args[0])
            )
            return
        self.visited_subdirs[symlinkless_dir] = True
        abs_uri = Path(absname).as_uri()
        if abs_uri not in self.workspace.documents:
            if not os.path.isfile(absname):
                sys.stderr.write(
                    'Unable to find build file {} --> skipping\n'.format(build_filename)
                )
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
