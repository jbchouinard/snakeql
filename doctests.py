import doctest
import sys
import warnings

import snakeql.lexer
import snakeql.parser


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    for mod in (snakeql.lexer, snakeql.parser, snakeql.core, snakeql.functions):
        fail_count, test_count = doctest.testmod(mod)
        if fail_count:
            sys.exit(1)
