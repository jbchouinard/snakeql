"""
>>> import re
>>> def p(s):
...     q = parser.parse(s)
...     return re.sub(r'[\\s\\n]+', ' ', str(q))
...
>>> p("SELECT o.x")
'SELECT o.x'
>>> p("SELECT o.x,")
'SELECT o.x,'
>>> p("SELECT DISTINCT o,")
'SELECT DISTINCT o,'
>>> p("SELECT o['x'], 'foo' AS bar")
"SELECT o['x'], 'foo' AS bar"
>>> p("SELECT add(o.x, mul(o.y, o.z))")
'SELECT add(o.x, mul(o.y, o.z))'
>>> p("SELECT str()")
'SELECT str()'
>>> p("SELECT o.x, sum(o.y)\\nGROUP BY o.x")
'SELECT o.x, sum(o.y) GROUP BY o.x,'
>>> p("SELECT o.x WHERE o.x > 3")
'SELECT o.x WHERE (o.x > 3)'
>>> p("SELECT o.x WHERE o.x IN o.y, o.z")
'SELECT o.x WHERE (o.x IN o.y, o.z)'
>>> p("SELECT o.x WHERE NOT o.x IN o.y, o.z")
'SELECT o.x WHERE NOT (o.x IN o.y, o.z)'
>>> p("SELECT o.x WHERE NOT o.x == 0 AND o.y == 0")
'SELECT o.x WHERE (NOT (o.x == 0) AND (o.y == 0))'
>>> p("SELECT o.x WHERE NOT (o.x == 0 AND o.y == 0)")
'SELECT o.x WHERE NOT ((o.x == 0) AND (o.y == 0))'
>>> p("select o.x where o.x == 0 and o.y == 0 or o.a == 0 and o.b == 0")
'SELECT o.x WHERE (((o.x == 0) AND (o.y == 0)) OR ((o.a == 0) AND (o.b == 0)))'
>>> p("select o['x'] as foo returning dict")
"SELECT o['x'] AS foo, RETURNING dict"
>>> p("select o.x * o.y ** o.z where (o.x * o.y) > 5")
'SELECT (o.x * (o.y ** o.z)) WHERE ((o.x * o.y) > 5)'
"""
import ply.yacc as yacc

from .core import (
    _return_types,
    AliasField,
    AttrField,
    ConstantField,
    IdentityField,
    KeyField,
    SELECT,
)
from .functions import f
from .lexer import tokens, SyntaxError

assert tokens


def p_statement(p):
    "statement : select distinct fexprplus where groupby returning"
    _, _, distinct, fexprplus, where, groupby, returning = p
    s = SELECT(fexprplus)
    if distinct is not None:
        s = s.DISTINCT()
    if where is not None:
        s = s.WHERE(where)
    if groupby is not None:
        s = s.GROUP_BY(*groupby)
    if returning is not None:
        s = s.RETURNING(returning)
    p[0] = s


def p_select(p):
    """
    select : SELECT
           | empty
    """
    pass


def p_where_1(p):
    "where : WHERE fexpr"
    p[0] = p[2]


def p_where_2(p):
    "where : empty"
    pass


def p_distinct_1(p):
    "distinct : DISTINCT"
    p[0] = p[1]


def p_distinct_2(p):
    "distinct : empty"
    pass


def p_groupby_1(p):
    "groupby : GROUP BY fexprplus"
    p[0] = p[3]
    if not isinstance(p[0], list):
        p[0] = [p[0]]


def p_groupby_2(p):
    "groupby : empty"
    pass


def p_returning_1(p):
    "returning : RETURNING ID"
    try:
        p[0] = _return_types[p[2]]
    except KeyError:
        raise NameError("undefined return type {}".format(p[2]))


def p_returning_2(p):
    "returning : empty"
    pass


def p_fexprplus_1(p):
    "fexprplus : fexprs"
    p[0] = p[1]


def p_fexprplus_2(p):
    "fexprplus : fexpr"
    p[0] = p[1]


def p_fexprstar_1(p):
    "fexprstar : fexprs"
    p[0] = p[1]


def p_fexprstar_2(p):
    "fexprstar : fexpr"
    p[0] = [p[1]]


def p_fexprstar_3(p):
    "fexprstar : empty"
    p[0] = []


def p_fexprs_1(p):
    "fexprs : fexpr ','"
    p[0] = [p[1]]


def p_fexprs_2(p):
    "fexprs : fexprs2plus"
    p[0] = p[1]


def p_fexprs_3(p):
    "fexprs : fexprs2plus ','"
    p[0] = p[1]


def p_fexprs2plus_1(p):
    "fexprs2plus : fexprs2plus ',' fexpr"
    p[0] = p[1]
    p[0].append(p[3])


def p_fexprs2plus_2(p):
    "fexprs2plus : fexpr ',' fexpr"
    p[0] = [p[1], p[3]]


def p_fexpr_1(p):
    "fexpr : fexpr OR predterm"
    p[0] = p[1] | p[3]


def p_fexpr_2(p):
    "fexpr : predterm"
    p[0] = p[1]


def p_predterm_1(p):
    "predterm : predterm AND prednfactor"
    p[0] = p[1] & p[3]


def p_predterm_2(p):
    "predterm : prednfactor"
    p[0] = p[1]


def p_prednfactor_1(p):
    "prednfactor : NOT prednfactor"
    p[0] = ~p[2]


def p_prednfactor_2(p):
    "prednfactor : predfactor"
    p[0] = p[1]


def p_predfactor_1(p):
    "predfactor : predfactor IN fexprs"
    p[0] = p[1].IN(p[3])


def p_predfactor_2(p):
    "predfactor : predfactor COMPARE arithexpr"
    left, op, right = p[1], p[2], p[3]
    if op == "==":
        p[0] = left == right
    elif op == "!=":
        p[0] = left != right
    elif op == ">":
        p[0] = left > right
    elif op == ">=":
        p[0] = left >= right
    elif op == "<":
        p[0] = left < right
    elif op == "<=":
        p[0] = left <= right
    elif op == "IS":
        p[0] = left.IS(right)
    elif op == "CONTAINS":
        p[0] = left.CONTAINS(right)
    elif op == "LIKE":
        p[0] = left.LIKE(right)
    elif op == "MATCHES":
        p[0] == left.MATCHES(right)


def p_predfactor_3(p):
    "predfactor : arithexpr"
    p[0] = p[1]


def p_arithexpr_1(p):
    "arithexpr : arithexpr '+' term"
    p[0] = p[1] + p[3]


def p_arithexpr_2(p):
    "arithexpr : arithexpr '-' term"
    p[0] = p[1] - p[3]


def p_arithexpr_3(p):
    "arithexpr : term"
    p[0] = p[1]


def p_term_1(p):
    "term : term '*' expnt"
    p[0] = p[1] * p[3]


def p_term_2(p):
    "term : term '/' expnt"
    p[0] = p[1] / p[3]


def p_term_3(p):
    "term : term '%' expnt"
    p[0] = p[1] % p[3]


def p_term_4(p):
    "term : expnt"
    p[0] = p[1]


def p_expnt_1(p):
    "expnt : field POW expnt"
    p[0] = p[1] ** p[3]


def p_expnt_2(p):
    "expnt : field"
    p[0] = p[1]


def p_field_1(p):
    "field : literal"
    p[0] = ConstantField(p[1])


def p_field_2(p):
    "field : O"
    p[0] = IdentityField()


def p_field_3(p):
    "field : O '.' ID"
    p[0] = AttrField(p[3])


def p_field_4(p):
    "field : O '[' literal ']'"
    p[0] = KeyField(p[3])


def p_field_5(p):
    "field : ID '(' fexprstar ')'"
    try:
        p[0] = f._funcs[p[1]](*p[3])
    except KeyError:
        raise NameError("undefined field function {}".format(p[1]))


def p_field_6(p):
    "field : '(' fexpr ')'"
    p[0] = p[2]


def p_field_7(p):
    "field : field AS ID"
    p[0] = AliasField(p[1], p[3])


def p_literal_1(p):
    "literal : STR"
    p[0] = p[1]


def p_literal_2(p):
    "literal : FLOAT"
    p[0] = p[1]


def p_literal_3(p):
    "literal : INT"
    p[0] = p[1]


def p_literal_4(p):
    "literal : TRUE"
    p[0] = True


def p_literal_5(p):
    "literal : FALSE"
    p[0] = False


def p_literal_6(p):
    "literal : NONE"
    p[0] = None


def p_empty_1(p):
    "empty : "
    pass


def p_error(p):
    raise SyntaxError(f"Unexpected token {p.type} ({p.value}) on line {p.lineno}")


parser = yacc.yacc()


if __name__ == "__main__":
    import doctest

    doctest.testmod()
