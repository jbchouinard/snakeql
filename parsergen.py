import argparse
import sys


def read_grammar(lines):
    last_p = None
    n = 1
    for line in lines:
        if ":" in line:
            last_p, rule = line.split(":")
            last_p = last_p.strip()
            n = 1
            rule = rule.strip()
        elif "|" in line:
            _, rule = line.split("|")
            rule = rule.strip()
            n += 1
        else:
            continue
        yield (last_p, n, rule)


def p_function(rule):
    p, n, rule = rule
    return """
def p_{p}_{n}(p):
    "{p} : {rule}"
    pass""".format(
        p=p, rule=rule, n=n
    )


def generate_parser(rules):
    for rule in rules:
        yield p_function(rule)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", default=None)
    parser.add_argument("-o", "--output", default=None)
    args = parser.parse_args()

    if args.input is None:
        fin = sys.stdin
    else:
        fin = open(args.input, "r")

    if args.output is None:
        fout = sys.stdout
    else:
        fout = open(args.output, "w")

    for line in generate_parser(read_grammar(fin)):
        fout.write(line)
        fout.write("\n")

    if fin is not sys.stdin:
        fin.close()
    if fout is not sys.stdout:
        fout.close()


if __name__ == "__main__":
    main()
