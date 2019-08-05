"""
>>> def tokens(lexer):
...     toks = []
...     tok = lexer.token()
...     while tok:
...         toks.append(tok.type)
...         tok = lexer.token()
...     return toks
...
>>> lexer.input('SELECT DISTINCT o.x, sum(o.y)')
>>> tokens(lexer)
['SELECT', 'DISTINCT', 'O', '.', 'ID', ',', 'ID', '(', 'O', '.', 'ID', ')']
>>> lexer.input('WHERE o.x == o.y')
>>> tokens(lexer)
['WHERE', 'O', '.', 'ID', 'COMPARE', 'O', '.', 'ID']
>>> lexer.input('GROUP BY o.x')
>>> tokens(lexer)
['GROUP', 'BY', 'O', '.', 'ID']

>>> lexer.input("SELECT o['x'], o['y']")
>>> tokens(lexer)
['SELECT', 'O', '[', 'STR', ']', ',', 'O', '[', 'STR', ']']
>>> lexer.input("WHERE o['x'] IS TRUE")
>>> tokens(lexer)
['WHERE', 'O', '[', 'STR', ']', 'COMPARE', 'TRUE']

>>> lexer.input(".12 12.0 0. 12e12 -12E-12 +0.00")
>>> tokens(lexer)
['FLOAT', 'FLOAT', 'FLOAT', 'FLOAT', 'FLOAT', 'FLOAT']

>>> lexer.input("12 0 44 -1 +13 0xa12 0b0110 0o732 -0X12")
>>> tokens(lexer)
['INT', 'INT', 'INT', 'INT', 'INT', 'INT', 'INT', 'INT', 'INT']

>>> lexer.input("'foo' 'SELECT' '12.0' 'sum(x.y)' ''")
>>> tokens(lexer)
['STR', 'STR', 'STR', 'STR', 'STR']
"""
import ply.lex as lex


literals = "()[],.+-/*%"

tokens = ["COMPARE", "ID", "STR", "INT", "FLOAT", "POW"]

keywords = {
    "SELECT",
    "DISTINCT",
    "WHERE",
    "GROUP",
    "BY",
    "AS",
    "RETURNING",
    "AND",
    "OR",
    "NOT",
    "TRUE",
    "FALSE",
    "NONE",
    "O",
    "IN",
}
tokens.extend(keywords)

compare_ids = {"IS", "IN", "CONTAINS", "MATCHES", "LIKE"}

t_COMPARE = r">=?|<=?|==|!="

t_POW = r"\*\*"


def t_ID(t):
    r"[a-zA-Z_][a-zA-Z_0-9]*"
    if t.value.upper() in keywords:
        t.value = t.value.upper()
        t.type = t.value
    elif t.value.upper() in compare_ids:
        t.value = t.value.upper()
        t.type = "COMPARE"
    return t


def t_STR(t):
    r"'(\\\\|\\'|[^'\\])*'"
    t.value = t.value[1:-1]
    return t


pointfloat = r"(\d+)?\.\d+|\d+\."
exponent = r"[eE][+-]?\d+"
exponentfloat = f"(\\d+|{pointfloat}){exponent}"
floatnumber = f"[+-]?({exponentfloat}|{pointfloat})"


@lex.TOKEN(floatnumber)
def t_FLOAT(t):
    t.value = float(t.value)
    return t


decint = r"[1-9][0-9]*"
binint = r"0[bB][01]+"
octint = r"0[oO][0-7]+"
hexint = r"0[xX][0-9a-fA-F]+"
intnumber = f"[+-]?({decint}|{binint}|{octint}|{hexint}|0)"


@lex.TOKEN(intnumber)
def t_INT(t):
    if t.value.startswith("-"):
        sign, n = -1, t.value[1:]
    elif t.value.startswith("+"):
        sign, n = 1, t.value[1:]
    else:
        sign, n = 1, t.value

    bases = {"0b": 2, "0o": 8, "0x": 16}
    prefix = n.lower()[:2]
    if prefix in bases:
        t.value = sign * int(n[2:], bases[prefix])
    else:
        t.value = sign * int(n)
    return t


def t_newline(t):
    r"\n+"
    t.lexer.lineno += len(t.value)


t_ignore = " \t"


class SyntaxError(Exception):
    pass


def t_error(t):
    raise SyntaxError("Unexpected character(s) %r at line %i" % (t.value, t.lineno))


lexer = lex.lex()


if __name__ == "__main__":
    import doctest

    doctest.testmod()
