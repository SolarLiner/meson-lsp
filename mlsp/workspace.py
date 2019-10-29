import logging
import pkgutil
from pathlib import Path
from typing import Dict, List

from mesonbuild.mparser import ParseException, Lexer
from pyls_jsonrpc.endpoint import Endpoint

from mlsp import consts
from mlsp.ast import LSPInterpreter
from mlsp.document import Document

logger = logging.getLogger(__name__)

KEYWORDS_BLOCK = ["if", "foreach"]
KEYWORDS_BLOCK_END = [f"end{v}" for v in KEYWORDS_BLOCK]
KEYWORDS_LOGIC = ["and", "or", "not"]
KEYWORDS_OTHER = ["else", "elif"]
KEYWORDS_ALL = KEYWORDS_BLOCK + KEYWORDS_BLOCK_END + KEYWORDS_LOGIC + KEYWORDS_OTHER

MODULES = [
    dict(
        name=m.name.replace('unstable_', ''),
        deprecated=('unstable' in m.name)
    ) for m in pkgutil.iter_modules([
        (Path(__file__) / '../../modules').resolve()
    ])
]


class Workspace:
    documents: Dict[str, Document]
    errors: List[ParseException]

    def __init__(self, root_uri: str, endpoint: Endpoint):
        self.interpreter = LSPInterpreter(self, '')
        logger.debug('Workspace(%s, %s)', root_uri, endpoint)
        self.root_uri = root_uri
        self.endpoint = endpoint
        self.documents = dict()
        self.errors = list()
        self.build_ast()

    def build_ast(self):
        logger.info('Rebuilding AST')
        self.errors = list()
        try:
            self.interpreter.load_root_meson_file()
            self.interpreter.parse_project()
            self.interpreter.run()
        except ParseException as pe:
            self.errors.append(pe)
        except:
            logger.exception('AST parsing failed')
            raise
        self.endpoint.notify('textDocument/publishDiagnostics',
                             params={
                                 'uri': str((Path(self.root_uri) / 'meson.build').absolute()),
                                 'diagnostics': [{
                                     'source': 'meson',
                                     'range': {
                                         'start': {
                                             'line': e.lineno,
                                             'character': e.colno
                                         },
                                         'end': {
                                             'line': e.lineno,
                                             'character': e.colno
                                         }
                                     },
                                     'message': str(e),
                                     'severity': consts.DiagnosticSeverity.Error,
                                     'code': '-1'
                                 } for e in self.errors]
                             })

    def update(self, document: dict, changes=None):
        if document.get('uri') in self.documents:
            self.documents.get(document.get('uri')).update(changes)
        else:
            self.documents[document.get('uri')] = Document(
                document.get('uri'),
                document.get('text')
            )

    def get_document(self, uri: str):
        return self.documents.get(uri)

    def pop_document(self, document: Document):
        return self.documents.pop(document.get_position_character_count('uri'))

    def get_symbols(self):
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
                label=k,
                kind=consts.CompletionItemKind.Variable,
                documentation="TODO (variables)",
                detail=str(type(v)))
            for k, v in self.interpreter.variables.items()
        ]
        assignments = [
            dict(
                label=k,
                kind=consts.CompletionItemKind.Variable,
                documentation=f"TODO (assignments) - evaluates to {str(v)}",
                detail=str(type(v)))
            for k, v in self.interpreter.assign_vals.items()
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
        return keywords + modules + variables + assignments + functions + subdirs
