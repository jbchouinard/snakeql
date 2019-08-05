"""
>>> from collections import namedtuple
>>> from snakeql.core import SELECT, selectable
>>> Product = selectable(namedtuple('Product', ['name', 'qty', 'price']))
>>> name, qty, price = Product.fields
>>> products = [
...     Product('apple', 10, 1.00),
...     Product('banana', 20, 0.75),
...     Product('orange', 10, 3.00),
...     Product('apple', 100, 1.00),
... ]
>>> s = SELECT([f.count(name).AS('count')]).GROUP_BY().RETURNING(dict)
>>> list(s(products))
[{'count': 4}]

>>> s = SELECT(f.upper(name)).GROUP_BY(f.upper(name))
>>> list(s(products))
['APPLE', 'BANANA', 'ORANGE']

>>> s = SELECT(
...     name.AS('product'), f.sum(f.mul(price, qty)).AS('subtotal'),
... ).GROUP_BY(name).RETURNING(dict)
>>> list(s(products))
[{'product': 'apple', 'subtotal': 110.0}, {'product': 'banana', 'subtotal': 15.0}, {'product': 'orange', 'subtotal': 30.0}]

>>> s = SELECT([f.round(f.weighted_average(price, qty), 2)]).GROUP_BY()
>>> avg_item_px = s(products)
>>> list(avg_item_px)
[(1.11,)]

>>> from collections import namedtuple
>>> Point = selectable(namedtuple('Point', ['x', 'y']))
>>> x, y = Point.fields
>>> points = [Point(2, 5), Point(5, 5), Point(7, 0)]
>>> @f.field_function
... def area(x, y):
...     return x * y
...
>>> s = SELECT([area(x, y)])
>>> list(s(points))
[(10,), (25,), (0,)]
>>> s = SELECT([f.sum(f.area(x, y))]).GROUP_BY()
>>> list(s(points))
[(35,)]
"""
import functools
import operator
import random

from .core import AggregateFunctionField, FunctionField, to_fields


class FunctionsRegistry:
    def __init__(self):
        self._funcs = {}

    def _add(self, name, func):
        setattr(self, name, func)
        self._funcs[name] = func

    def field_function(self, func, name=None):
        if name is None:
            name = func.__name__

        @functools.wraps(func)
        def wrapped(*fields):
            return FunctionField(func, to_fields(fields), name)

        self._add(name, wrapped)
        return wrapped

    def aggregate_function(self, func, name=None):
        if name is None:
            name = func.__name__

        @functools.wraps(func)
        def wrapped(*fields):
            return AggregateFunctionField(func, to_fields(fields), name)

        self._add(name, wrapped)
        return wrapped


f = FunctionsRegistry()

f.field_function(operator.add)
f.field_function(operator.sub)
f.field_function(operator.mul)
f.field_function(operator.truediv, "div")
f.field_function(operator.mod)
f.field_function(operator.pow)
f.field_function(operator.abs)
f.field_function(round)
f.field_function(operator.concat)
f.field_function(str)
f.field_function(str.upper)
f.field_function(str.lower)
f.field_function(str.replace)
f.field_function(len)
f.field_function(random.randint)
f.field_function(random.random)

f.aggregate_function(len, "count")
f.aggregate_function(sum)
f.aggregate_function(max)
f.aggregate_function(min)
f.aggregate_function(list)
f.aggregate_function(tuple)
f.aggregate_function(set)


@f.aggregate_function
def product(xs):
    s = 1
    for x in xs:
        s *= x
    return s


@f.aggregate_function
def join(ns):
    return "".join(ns)


@f.aggregate_function
def first(ns):
    return next(iter(ns))


@f.aggregate_function
def average(ns):
    return sum(ns) / len(ns)


@f.aggregate_function
def weighted_average(xs, weights):
    total_weight = sum(weights)
    total = sum(x * wt for x, wt in zip(xs, weights))
    return total / total_weight


if __name__ == "__main__":
    import doctest

    doctest.testmod()
