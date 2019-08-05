from collections import namedtuple
from snakeql import SELECT, selectable, query as p

length = p("select sum(1) group by true")
assert length([1, 2, 3, 4]).one() == 4

unique = p("select distinct o")
assert unique([1, 2, 3, 4, 1, 2, 2]).list() == [1, 2, 3, 4]

filter_x = p("select o['x'], returning dict")
assert filter_x([{"x": 12, "y": 15}, {"x": 0, "y": 0}]).list() == [{"x": 12}, {"x": 0}]

Point = selectable(namedtuple("Point", ["x", "y"]))
points = [Point(0, 0), Point(1, 5), Point(10, 5), Point(7, 7)]

# Query as text
diagonal = p("select o where o.x == o.y")
assert diagonal(points).list() == [Point(0, 0), Point(7, 7)]

# Query as code
x, y = Point.fields
diagonal = SELECT().WHERE(x == y)
assert diagonal(points).list() == [Point(0, 0), Point(7, 7)]


points = [Point(0, 0), Point(0, 10), Point(5, 5)]
groupby_x = p("select list(o) group by o.x")
assert groupby_x(points).list() == [[Point(0, 0), Point(0, 10)], [Point(5, 5)]]
