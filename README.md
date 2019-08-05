# snakeql

Query collections of Python objects with a duck-typed SQL-inspired API.

## Example

```python
from random import randint
from snakeql import query, selectabletuple, SELECT

Point = selectabletuple("Point", "x y")
x, y = Point.fields

points = [Point(randint(0, 20), randint(0, 20)) for _ in range(10000)]

# Find diagonal points
# Using Python syntax
f = SELECT(x).WHERE(x == y)
diagonals = f(points)
# Using query
f = query("SELECT o.x WHERE o.x = o.y")
diagonals = f(points)

# Get unique points
f = query("SELECT DISTINCT o")
uniques = f(points)
```