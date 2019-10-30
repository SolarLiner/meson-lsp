import argparse
import logging
import sys
from logging import Formatter

from mlsp.log_handler import LanguageServerLoggingHandler
from mlsp.server import new_with_stdio


def setup_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true', default=False, help='Increase verbosity')
    parser.add_argument('--tcp', default=0, help='Specify TCP port to use (default: use stdio)', type=int)
    return parser


def main():
    parser = setup_arguments()
    namespace = parser.parse_args()

    # Not supporting options for now
    logger = logging.getLogger()
    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(0)
    logger.addHandler(sh)
    if namespace.debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.WARNING)
    server = new_with_stdio(namespace)
    lsp_handler = LanguageServerLoggingHandler(server.endpoint)
    lsp_handler.setFormatter(Formatter(fmt="[%(module)s - %(asctime)-8s] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(lsp_handler)

    try:
        server.start()
    except Exception as ex:
        logger.exception("Server exception")
