"""
Query collections of Python objects with a duck-typed SQL-inspired API.


Query dataclasses:

>>> from dataclasses import dataclass
>>> @selectable
... @dataclass
... class Person:
...     name: str
...     age: int
...     height: float
...
>>> name, age, height = Person.fields
>>> people = [Person('Joe', 25, 180), Person('Bill', 50, 160), Person('Jack', 75, 190)]

Basic SELECT statement
>>> s = SELECT(name, age).WHERE(age < 40)
>>> list(s(people))  # execute the "statement" by calling it on a collection of objects
[('Joe', 25)]

Get dicts instead of tuples:
>>> list(s.RETURNING(dict)(people))
[{'name': 'Joe', 'age': 25}]

Select all fields defined on Person:
>>> s = Person.fields.SELECT().WHERE(age < 40)
>>> list(s(people))
[('Joe', 25, 180)]

Give no argument to SELECT to get the original objects instead of tuples or dicts:
>>> s = SELECT().WHERE(age < 40)
>>> list(s(people))
[Person(name='Joe', age=25, height=180)]

>>> s = SELECT([name]).WHERE(age >= 40)
>>> list(s(people))
[('Bill',), ('Jack',)]

>>> s = SELECT([name.AS('FirstName')]).RETURNING(dict)
>>> list(s(people))
[{'FirstName': 'Joe'}, {'FirstName': 'Bill'}, {'FirstName': 'Jack'}]


Query namedtuples:

>>> from collections import namedtuple
>>> Point = selectable(namedtuple('Point', ['x', 'y']))
>>> x, y = Point.fields
>>> points = [Point(2, 5), Point(5, 5), Point(7, 0)]
>>> list(SELECT(x, y).WHERE(x >= y)(points))
[(5, 5), (7, 0)]
"""
import abc
import fnmatch
import itertools
import operator
import re
from collections import namedtuple
from typing import Any, Callable, Iterable, Sequence, Tuple, Union


def and_(x, y):
    return x and y


def or_(x, y):
    return o or y


def not_(x):
    return not x


def in_(x, y):
    return x in y


def matches(x, y):
    return re.match(y, x)


def field_op(operator, op_str):
    def method(self, other):
        return OperatorField(operator, (self, to_field(other)), op_str)

    return method


class Field(abc.ABC):
    @abc.abstractmethod
    def _name(self):
        pass

    @abc.abstractmethod
    def __call__(self, obj):
        pass

    @abc.abstractmethod
    def _is_mapper(self):
        "f(x) -> y"
        pass

    @abc.abstractmethod
    def _is_aggregator(self):
        "f([x1, x2, ... xn]) -> y"
        pass

    @abc.abstractmethod
    def _equals(self, other):
        pass

    def AS(self, name):
        return AliasField(self, name)

    def IN(self, others):
        return OperatorField(in_, (self, ListField(others)), "IN")

    def __invert__(self):
        return OperatorField(not_, (self,), "NOT")

    __and__ = field_op(and_, "AND")
    __or__ = field_op(or_, "OR")
    __eq__ = field_op(operator.eq, "==")
    __ne__ = field_op(operator.ne, "!=")
    __lt__ = field_op(operator.lt, "<")
    __le__ = field_op(operator.le, "<=")
    __gt__ = field_op(operator.gt, ">")
    __ge__ = field_op(operator.ge, ">=")
    __add__ = field_op(operator.add, "+")
    __sub__ = field_op(operator.sub, "-")
    __mul__ = field_op(operator.mul, "*")
    __truediv__ = field_op(operator.truediv, "/")
    __mod__ = field_op(operator.mod, "%")
    __pow__ = field_op(operator.pow, "**")
    IS = field_op(operator.is_, "IS")
    CONTAINS = field_op(operator.contains, "CONTAINS")
    LIKE = field_op(fnmatch.fnmatch, "LIKE")
    MATCHES = field_op(matches, "MATCHES")
    AND = __and__
    OR = __or__


def NOT(field):
    return ~field


class ListField(Field):
    def __init__(self, fields):
        self.fields = to_fields(fields)

    def __repr__(self):
        return f"ListField({self.fields!r})"

    def __str__(self):
        return ", ".join(str(f) for f in self.fields)

    def _name(self):
        return ",".join(f._name() for f in self.fields)

    def __call__(self, obj):
        return [f(obj) for f in self.fields]

    def _is_mapper(self):
        return all(f._is_mapper() for f in self.fields)

    def _is_aggregator(self):
        return all(f._is_aggregator() for f in self.fields)

    def _equals(self, other):
        if isinstance(other, AliasField):
            return other._equals(self)
        if type(self) is not type(other):
            return False
        if len(self.fields) != len(other.fields):
            return False
        for sf, of in zip(self.fields, other.fields):
            if not sf._equals(of):
                return False
        return True


class KeyField(Field):
    def __init__(self, key):
        self.key = key

    def __repr__(self):
        return f"KeyField({self.key!r})"

    def __str__(self):
        return f"o[{self.key!r}]"

    def _name(self):
        return self.key

    def __call__(self, obj):
        return obj[self.key]

    def _is_mapper(self):
        return True

    def _is_aggregator(self):
        return False

    def _equals(self, other):
        if isinstance(other, AliasField):
            return other._equals(self)
        return (type(self) is type(other)) and (self.key == other.key)


class AttrField(Field):
    def __init__(self, attr):
        self.attr = attr

    def __repr__(self):
        return f"AttrField({self.attr!r})"

    def __str__(self):
        return f"o.{self.attr!s}"

    def _name(self):
        return self.attr

    def __call__(self, obj):
        return getattr(obj, self.attr)

    def _is_mapper(self):
        return True

    def _is_aggregator(self):
        return False

    def _equals(self, other):
        """
        >>> AttrField('x')._equals(AttrField('x'))
        True
        >>> AttrField('x')._equals(AttrField('y'))
        False
        """
        if isinstance(other, AliasField):
            return other._equals(self)
        return (type(self) is type(other)) and (self.attr == other.attr)


class IdentityField(Field):
    """
    >>> o = IdentityField()
    >>> people = [('Alex', 30), ('Bill', 70)]
    >>> list(SELECT()(people))
    [('Alex', 30), ('Bill', 70)]
    >>> to_dicts = SELECT(o[0].AS('name'), o[1].AS('age')).RETURNING(dict)
    >>> list(to_dicts(people))
    [{'name': 'Alex', 'age': 30}, {'name': 'Bill', 'age': 70}]
    """

    def __call__(self, obj):
        return obj

    def _name(self):
        return "o"

    def __repr__(self):
        return "IdentityField()"

    def __str__(self):
        return "o"

    def __getitem__(self, key):
        return KeyField(key)

    def __getattr__(self, attr):
        return AttrField(attr)

    def _is_mapper(self):
        return True

    def _is_aggregator(self):
        return False

    def _equals(self, other):
        if isinstance(other, AliasField):
            return other._equals(self)
        return type(self) is type(other)


o = IdentityField()


class AliasField(Field):
    def __init__(self, field: Any, name: str):
        assert re.match(r"[a-zA-Z_][a-zA-Z_0-9]*", name), "Alias must be a valid Python identifier"
        self.field = to_field(field)
        self.name = name

    def __str__(self):
        return f"{self.field!s} AS {self.name!s}"

    def __repr__(self):
        return f"{self.field!r}.AS({self.name!r})"

    def _name(self):
        return self.name

    def __call__(self, obj):
        """
        >>> x = KeyField('x')
        >>> x_as_y = x.AS('y')
        >>> x_as_y({'x': 12})
        12
        """
        return self.field(obj)

    def _is_mapper(self):
        return self.field._is_mapper()

    def _is_aggregator(self):
        return self.field._is_aggregator()

    def _equals(self, other):
        return self.field._equals(other)


class ConstantField(Field):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"ConstantField({self.value!r})"

    def __str__(self):
        return repr(self.value)

    def _name(self):
        return str(self.value)

    def __call__(self, obj):
        return self.value

    def _is_mapper(self):
        return True

    def _is_aggregator(self):
        return True

    def _equals(self, other):
        if isinstance(other, AliasField):
            return other._equals(self)
        return type(self) is type(other) and self.value == other.value


class FunctionField(Field):
    def __init__(self, func: Callable, args: Iterable, name=None):
        self.func = func
        self.args = tuple(args)
        self.name = name or func.__name__

    def __repr__(self):
        return f"FunctionField({self.func!r}, {self.args!r}, {self.name!r})"

    def __str__(self):
        args = ", ".join(str(arg) for arg in self.args)
        return f"{self.name!s}({args})"

    def _name(self):
        return str(self)

    def __call__(self, obj):
        return self.func(*(arg(obj) for arg in self.args))

    def _is_mapper(self):
        return all(arg._is_mapper() for arg in self.args)

    def _is_aggregator(self):
        return all(arg._is_aggregator() for arg in self.args)

    def _equals(self, other):
        if isinstance(other, AliasField):
            return other._equals(self)
        if not type(self) is type(other):
            return False
        if self.func is not other.func:
            return False
        if len(self.args) != len(other.args):
            return False
        for sarg, oarg in zip(self.args, other.args):
            if not sarg._equals(oarg):
                return False
        return True


class OperatorField(FunctionField):
    def __init__(self, func: Callable, args: Iterable, name=None):
        assert len(args) in (1, 2)
        super().__init__(func, args, name)

    def __repr__(self):
        return f"OperatorField({self.func!r}, {self.args!r}, {self.name!r})"

    def __str__(self):
        if len(self.args) == 2:
            return f"({fields_to_str(self.args[0])} {self.name} {fields_to_str(self.args[1])})"
        else:
            return f"{self.name} {fields_to_str(self.args[0])}"


class AggregateFunctionField(FunctionField):
    def __init__(self, func: Callable, args: Iterable, name=None):
        super().__init__(func, args, name)
        assert all(arg._is_mapper() for arg in args)

    def __repr__(self):
        return f"AggregrateFunctionField({self.func!r}, {self.args!r}, {self.name!r})"

    def __call__(self, objs):
        args = []
        for arg in self.args:
            args.append(tuple(arg(obj) for obj in objs))
        return self.func(*args)

    def _is_mapper(self):
        return False

    def _is_aggregator(self):
        return True


class AttrFieldsDescriptor:
    def __init__(self):
        self._fields = []

    def __iter__(self):
        return iter(self._fields)

    def add(self, attr):
        field = AttrField(attr)
        self._fields.append(field)
        setattr(self, attr, field)

    def SELECT(self):
        return SELECT(*self._fields)


def selectable(cls_or_fields=None):
    def wrapper(cls):
        querycls = type(cls.__name__, (cls,), {"fields": AttrFieldsDescriptor()})
        if cfields is None:
            if hasattr(cls, "__dataclass_fields__"):
                fields = cls.__dataclass_fields__
            elif hasattr(cls, "_fields"):
                fields = cls._fields
            else:
                fields = []
        else:
            fields = cfields

        for f in fields:
            querycls.fields.add(f)
        add_return_type(querycls)
        return querycls

    if isinstance(cls_or_fields, type):
        cfields = None
        return wrapper(cls_or_fields)
    else:
        cfields = cls_or_fields
        return wrapper


def selectabletuple(clsname, fields):
    return selectable(namedtuple(clsname, fields))


def SELECT(*fields):
    if not fields:
        select_fields = (IdentityField(),)
        flatten = True
    elif len(fields) == 1:
        field = fields[0]
        if isinstance(field, (list, tuple)):
            select_fields = to_fields(field)
            flatten = False
        else:
            select_fields = (to_field(field),)
            flatten = True
    else:
        select_fields = to_fields(fields)
        flatten = False
    return SelectQuery(select_fields, flatten)


class SelectQuery:
    def __init__(
        self,
        fields: Tuple[Field, ...],
        flatten: bool,
        distinct: bool = False,
        where: Field = None,
        group_by: Tuple[Field] = None,
        return_type: type = None,
    ):
        self.fields = fields
        self.flatten = flatten
        self.distinct = distinct
        self.where = where
        self.group_by = group_by
        self.return_type = return_type

    def _replace(self, flatten=None, distinct=None, where=None, group_by=None, return_type=None):
        return SelectQuery(
            fields=self.fields,
            flatten=self.flatten if flatten is None else flatten,
            distinct=self.distinct if distinct is None else distinct,
            where=self.where if where is None else where,
            group_by=self.group_by if group_by is None else group_by,
            return_type=self.return_type if return_type is None else return_type,
        )

    def __str__(self):
        lines = []
        select = "SELECT DISTINCT" if self.distinct else "SELECT"
        fields = self.fields[0] if self.flatten else self.fields
        lines.append(select + " " + fields_to_str(fields))
        if self.where is not None:
            lines.append(f"WHERE {block(str(self.where))}")
        if self.group_by is not None:
            lines.append("GROUP BY " + fields_to_str(self.group_by))
        if self.return_type:
            lines.append(f"RETURNING {self.return_type.__name__!s}")
        return "\n".join(lines)

    def __repr__(self):
        statement = '"""\n' + str(self) + '\n"""'
        return f"snakeql.query(\n{indent(statement)}\n)"

    def DISTINCT(self):
        return self._replace(distinct=True)

    def _distinct(self, res):
        if self.distinct:
            seen = set()
            for r in res:
                if r not in seen:
                    seen.add(r)
                    yield r
        else:
            yield from res

    def WHERE(self, where):
        assert where._is_mapper(), "cannot use an aggregate function in WHERE"
        return self._replace(where=to_field(where))

    def _where(self, res):
        if self.where is not None:
            return filter(self.where, res)
        else:
            return res

    def GROUP_BY(self, *fields):
        fields = to_fields(fields)
        assert all(f._is_mapper() for f in fields), "cannot use an aggregate function in GROUP BY"
        for select_field in self.fields:
            if field_index(select_field, fields) is None:
                if not select_field._is_aggregator():
                    raise ValueError(
                        f"{select_field!s} is neither in GROUP BY or an aggregate function"
                    )
        return self._replace(group_by=fields)

    def RETURNING(self, return_type: Callable):
        return self._replace(flatten=False, return_type=return_type)

    def _returning(self, res):
        if self.return_type is not None:
            names = [f._name() for f in self.fields]
            for r in res:
                yield self.return_type(**dict(zip(names, r)))
        else:
            yield from res

    def _select(self, fields, res):
        for r in res:
            yield tuple(f(r) for f in fields)

    def _flatten(self, res):
        if self.flatten:
            return (r[0] for r in res)
        else:
            return res

    def _make_group_by_field(self, select_field):
        idx = field_index(select_field, self.group_by)
        # If the select field is part of the group by, get value from group key
        if idx is not None:
            return lambda pair: pair.key()[idx]
        # Else the select field must be an aggregate function
        else:
            return lambda pair: select_field(pair.value())

    def _group(self, res):
        res = list(res)
        keys = self._select(self.group_by, res)
        pairs = (KeyValuePair(k, v) for k, v in zip(keys, res))
        pairs = sorted(pairs, key=KeyValuePair.key)
        for k, group_pairs in itertools.groupby(pairs, key=KeyValuePair.key):
            yield KeyValuePair(k, [p.value() for p in group_pairs])

    def __call__(self, objects):
        res = self._where(objects)

        if self.group_by is None:
            for f in self.fields:
                if not f._is_mapper():
                    raise ValueError(f"cannot use aggregate function {f!s} without GROUP BY")
            assert all(f._is_mapper() for f in self.fields)
            res = self._select(self.fields, res)
        else:
            group_by_fields = tuple(self._make_group_by_field(f) for f in self.fields)
            res = self._select(group_by_fields, self._group(res))

        res = self._flatten(res)
        res = self._distinct(res)
        res = self._returning(res)
        return SelectResult(res, self)


class KeyValuePair:
    def __init__(self, key, value):
        self._key = key
        self._value = value

    def key(self):
        return self._key

    def value(self):
        return self._value


class SelectResult:
    def __init__(self, res, query):
        self._res = res
        self.query = query

    def __iter__(self):
        return self._res

    def list(self):
        return list(self)

    def one(self):
        try:
            first = next(self._res)
        except StopIteration:
            raise ValueError("no items in in result")
        try:
            next(self._res)
        except StopIteration:
            pass
        else:
            raise ValueError("more than one item in result")
        return first


_return_types = {"dict": dict}


def add_return_type(type_, name=None):
    if name is None:
        name = type_.__name__
    _return_types[name] = type_


def to_field(field_or_value: Any) -> Field:
    if isinstance(field_or_value, Field):
        return field_or_value
    else:
        return ConstantField(field_or_value)


def to_fields(fields_or_values: Iterable) -> Tuple[Field, ...]:
    return tuple(to_field(fv) for fv in fields_or_values)


def fields_to_str(fields: Union[Field, Sequence[Field]]):
    if isinstance(fields, Field):
        return str(fields)
    elif len(fields) == 0:
        return "()"
    elif len(fields) == 1:
        return str(fields[0]) + ","
    else:
        return ", ".join(str(f) for f in fields)


def field_index(needle_field: Field, haystack_fields: Iterable[Field]):
    for i, candidate_field in enumerate(haystack_fields):
        if needle_field._equals(candidate_field):
            return i
    return None


def indent(text, tab="    "):
    return "\n".join(tab + line for line in text.splitlines())


def block(text, tab="    "):
    if len(text.splitlines()) == 1:
        return text
    else:
        return f"(\n{indent(text, tab=tab)}\n)"


if __name__ == "__main__":
    import doctest

    doctest.testmod()
