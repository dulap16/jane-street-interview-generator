"""Read-only narration metadata; never rewrite candidate source."""

from __future__ import annotations

import io
import re
import tokenize


def comments(source: str, language: str) -> list[dict]:
    if language == "python":
        found = []
        try:
            for token in tokenize.generate_tokens(io.StringIO(source).readline):
                if token.type == tokenize.COMMENT and token.string.startswith("# THINK:"):
                    line, col = token.start
                    if not source.splitlines()[line - 1][:col].strip():
                        found.append({"line": line, "text": token.string[8:].strip(),
                                      "original": token.string})
        except (tokenize.TokenError, IndentationError, SyntaxError):
            # Partial editor buffers are normal; no uncertain lines are removed.
            return []
        return found
    # Conservative C++ lexer, including raw strings and escaped-newline comments.
    found = []
    i, line, line_start = 0, 1, 0
    while i < len(source):
        if source[i] == "\n":
            line += 1
            line_start = i + 1
            i += 1
        elif source.startswith("/*", i):
            end = source.find("*/", i + 2)
            end = len(source) if end < 0 else end + 2
            chunk = source[i:end]
            line += chunk.count("\n")
            if "\n" in chunk:
                line_start = i + chunk.rfind("\n") + 1
            i = end
        elif source.startswith("//", i):
            end = source.find("\n", i)
            end = len(source) if end < 0 else end
            # A continued comment is not a standalone narration-only line.
            text = source[i:end]
            if (text.startswith("// THINK:") and not source[line_start:i].strip()
                    and not text.rstrip("\r").endswith("\\")):
                found.append({"line": line, "text": text[9:].strip(), "original": text})
            while end < len(source) and source[:end].rstrip("\r").endswith("\\"):
                end = source.find("\n", end + 1)
                if end < 0:
                    end = len(source)
            chunk = source[i:end]
            line += chunk.count("\n")
            if "\n" in chunk:
                line_start = i + chunk.rfind("\n") + 1
            i = end
        elif source.startswith('R"', i):
            match = re.match(r'R"([^ ()\\\t\r\n]{0,16})\(', source[i:])
            if match:
                marker = ")" + match.group(1) + '"'
                end = source.find(marker, i + len(match.group(0)))
                end = len(source) if end < 0 else end + len(marker)
                chunk = source[i:end]
                line += chunk.count("\n")
                if "\n" in chunk:
                    line_start = i + chunk.rfind("\n") + 1
                i = end
            else:
                i += 1
        elif source[i] in "\"'":
            quote = source[i]
            i += 1
            while i < len(source):
                if source[i] == "\n":
                    line += 1
                    line_start = i + 1
                if source[i] == "\\":
                    if i + 1 < len(source) and source[i + 1] == "\n":
                        line += 1
                        line_start = i + 2
                    i += 2
                elif source[i] == quote:
                    i += 1
                    break
                else:
                    i += 1
        else:
            i += 1
    return found
