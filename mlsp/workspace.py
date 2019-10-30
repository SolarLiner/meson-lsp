import logging
import pkgutil
from importlib import import_module
from pathlib import Path
from typing import Dict, List, Optional

from mesonbuild.ast import AstVisitor
from mesonbuild.mparser import ParseException, Lexer
from pyls_jsonrpc.endpoint import Endpoint

from mlsp import consts
from mlsp.ast import LSPInterpreter
from mlsp.document import Document
from mlsp.visitors import VariablesVisitor

logger = logging.getLogger(__name__)

KEYWORDS_BLOCK = ["if", "foreach"]
KEYWORDS_BLOCK_END = [f"end{v}" for v in KEYWORDS_BLOCK]
KEYWORDS_LOGIC = ["and", "or", "not"]
KEYWORDS_OTHER = ["else", "elif"]
KEYWORDS_ALL = KEYWORDS_BLOCK + KEYWORDS_BLOCK_END + KEYWORDS_LOGIC + KEYWORDS_OTHER

MODULES = [
    dict(
        name=m.name.replace('unstable_', ''),
        deprecated=m.name.startswith('unstable')
    ) for m in pkgutil.iter_modules(
        import_module('mesonbuild.modules').__path__
    )
]


class Workspace:
    documents: Dict[str, Document]
    LSPInterpreter: Optional[LSPInterpreter]
    symbols: List[dict]
    visitors: Dict[str, AstVisitor]

    def __init__(self, root_uri: str, endpoint: Endpoint):
        logger.debug('Workspace(%s, %s)', root_uri, endpoint)
        self.root_uri = root_uri
        self.endpoint = endpoint
        self.documents = dict()
        self.interpreter = None
        self.symbols = list()
        self.last_update_version = 0
        self.visitors = dict(variables=VariablesVisitor())
        self.build_ast()

    @property
    def version(self):
        v = 0
        for i, doc in enumerate(self.documents.values()):
            v += doc.version * 10 ** i
        return v

    def build_ast(self):
        logger.debug('Rebuilding AST')
        diagnostics = list()
        try:
            self.interpreter = LSPInterpreter(self, '', visitors=list(self.visitors.values()))
            self.interpreter.load_root_meson_file()
            self.interpreter.parse_project()
            self.interpreter.run()
        except ParseException as pe:
            diagnostics.append({
                'source': 'meson',
                'range': {
                    'start': {
                        'line': pe.lineno,
                        'character': 1
                    },
                    'end': {
                        'line': pe.lineno,
                        'character': pe.colno
                    }
                },
                'message': str(pe).split('\n')[0],
                'severity': consts.DiagnosticSeverity.Error,
                'code': '-1'
            })
        except:
            logger.exception('AST parsing failed')
        self.symbols = self._get_symbols()

        # TODO: Other error reporting

        self.endpoint.notify('textDocument/publishDiagnostics',
                             params={
                                 'uri': str((Path(self.root_uri) / 'meson.build').absolute()),
                                 'diagnostics': diagnostics
                             })

    def update(self, document: dict, changes=None):
        if document.get('uri') in self.documents:
            self.documents.get(document.get('uri')).update(changes)
        else:
            self.documents[document.get('uri')] = Document(
                document.get('uri'),
                document.get('text')
            )
        # Optimization to only update symbols on document update
        if self.version > self.last_update_version:
            self.build_ast()
            self.last_update_version = self.version

    def get_document(self, uri: str):
        return self.documents.get(uri)

    def pop_document(self, document: Document):
        return self.documents.pop(document.get_position_character_count('uri'))

    def _get_symbols(self):
        visitor = VariablesVisitor()
        self.interpreter.visit([visitor])

        keywords = [
                       dict(label=k, kind=consts.CompletionItemKind.Keyword)
                       for k in Lexer("").keywords
                   ] + [
                       dict(
                           label=k,
                           kind=consts.CompletionItemKind.Keyword,
                           deprecated=True) for k in Lexer("").future_keywords
                   ]
        modules = [
            dict(
                label=k['name'],
                detail=f"{k['name']} module (unstable)"
                if k['deprecated'] else f"{k['name']} module",
                deprecated=k['deprecated'],
                insertText=f"import('{k['name']}')",
                kind=consts.CompletionItemKind.Module) for k in MODULES
        ]
        variables = [
            dict(
                label=v.var_name,
                detail=str(type(v.value)),
                kind=consts.CompletionItemKind.Variable
            ) for v in visitor.variables
        ]
        functions = [
            dict(
                label=k,
                kind=consts.CompletionItemKind.Function,
                documentation="TODO",
                detail='Function') for k in self.interpreter.funcs.keys()
        ]
        subdirs = [
            dict(
                label=f"{k} (subproject)",
                kind=consts.CompletionItemKind.Reference,
                detail=f"subproject('{k}')",
                insertText=f"subproject('{k}')")
            for k in self.interpreter.visited_subdirs.keys()
        ]
        return keywords + modules + variables + functions + subdirs
