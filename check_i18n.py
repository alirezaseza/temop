#!/usr/bin/env python3
"""Fail when values/strings.xml and values-fa/strings.xml differ in keys or format placeholders."""
import re
import sys
from collections import Counter

EN = "app/src/main/res/values/strings.xml"
FA = "app/src/main/res/values-fa/strings.xml"
ENTRY = re.compile(r'<string\s+name="([^"]+)"([^>]*)>(.*?)</string>', re.S)
PLACEHOLDER = re.compile(r"%(?:\d+\$)?[-#+ 0,(]*\d*(?:\.\d+)?[sdfxXeEgGc]")


def load(path):
    text = open(path, encoding="utf-8").read()
    return {m.group(1): (m.group(2), m.group(3)) for m in ENTRY.finditer(text)}


def conversions(value):
    # Positional indexes may legitimately be reordered in translations; the set of conversions may not.
    return Counter(re.sub(r"^%\d+\$", "%", p) for p in PLACEHOLDER.findall(value))


def main():
    en, fa = load(EN), load(FA)
    problems = []
    problems += [f"missing in fa: {k}" for k in sorted(en.keys() - fa.keys())]
    problems += [f"missing in en: {k}" for k in sorted(fa.keys() - en.keys())]
    for key in sorted(en.keys() & fa.keys()):
        if 'translatable="false"' in en[key][0]:
            continue
        if conversions(en[key][1]) != conversions(fa[key][1]):
            problems.append(f"placeholder mismatch in '{key}': en={dict(conversions(en[key][1]))} fa={dict(conversions(fa[key][1]))}")
        if not fa[key][1].strip():
            problems.append(f"empty fa string: {key}")
    for p in problems:
        print(p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
