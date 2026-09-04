#!/usr/bin/env python3
"""
THIS SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, 
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF 
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. 
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY 
CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, 
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THIS 
SOFTWARE OR THE USE OR OTHER DEALINGS IN THIS SOFTWARE.

Structural validator for Ilograph architecture-diagram YAML files.

Checks the mechanical rules from the ilograph skill's review checklist that
don't require semantic judgment: broken references, name/id hygiene,
sequence-perspective closure (control returns at least once to `start` and
to every `restartAt` target), call/return parity of synchronous `to:` steps
(returns that "jump over" a resource, and calls left unreturned),
subSequence completeness, relations that connect a resource to its own
parent/child, that every `description:`/`notes:` uses YAML block literal
style, and two YAML-formatting heuristics.
Unreferenced resources, sequence-closure gaps and call/return parity are
flagged as WARNINGs rather than ERRORs, since each can be a legitimate
authoring choice (a resource kept around for an upcoming perspective; a
flow that deliberately ends on a second actor; a genuine callback into a
resource further up the call stack).

This script does NOT check content quality (whether the right resources or
flows were chosen, whether prose is accurate, or whether code references are
backticked). That's left to human/model review.

Usage:
    python3 validate_ilograph.py [path/to/ilograph.yaml] [--strict]

Exits 1 if any ERROR-level finding is present (or any WARNING when --strict
is passed), else exits 0.
"""

import argparse
import re
import sys
from collections import Counter

try:
    import yaml
except ImportError:
    sys.exit("This script requires PyYAML. Install it with: pip install pyyaml")

RESTRICTED_CHARS = re.compile(r"[/^*\[\],]")
TO_KEYS = ("to", "toAsync", "toAndBack", "restartAt")

BARE_KEY_RE = re.compile(r"^(\s*)([A-Za-z][A-Za-z0-9_]*):\s*$")
BLOCK_SCALAR_KEY_RE = re.compile(r"^(\s*)([A-Za-z][A-Za-z0-9_]*):\s*[|>][+-]?\s*$")
DASH_RE = re.compile(r"^(\s*)-\s")

DESC_NOTES_KEY_RE = re.compile(r"^(\s*)(description|notes):(.*)$")
BLOCK_LITERAL_VALUE_RE = re.compile(r"^\|[+-]?\d*\s*(#.*)?$")


class Finding:
    def __init__(self, level, check, message, location=None):
        self.level = level  # "ERROR" or "WARNING"
        self.check = check
        self.message = message
        self.location = location

    def __str__(self):
        loc = f" ({self.location})" if self.location else ""
        return f"[{self.level}] {self.check}: {self.message}{loc}"


# ---------------------------------------------------------------------------
# Resource tree helpers
# ---------------------------------------------------------------------------

def effective_id(resource):
    return resource.get("id", resource.get("name"))


def walk_resources(resources, parent_id=None):
    """Yield (id, resource_dict, parent_id) for every resource in the tree."""
    for r in resources or []:
        rid = effective_id(r)
        yield rid, r, parent_id
        for child in r.get("children", []) or []:
            yield from walk_resources([child], rid)


def build_resource_index(data):
    resources = data.get("resources", []) or []
    by_id, parent_of, id_list, name_list = {}, {}, [], []
    for rid, r, parent_id in walk_resources(resources):
        id_list.append(rid)
        name_list.append(r.get("name", ""))
        by_id[rid] = r
        parent_of[rid] = parent_id
    return by_id, parent_of, id_list, name_list


def has_referenced_descendant(resource, referenced_ids):
    if effective_id(resource) in referenced_ids:
        return True
    return any(
        has_referenced_descendant(c, referenced_ids)
        for c in resource.get("children", []) or []
    )


# ---------------------------------------------------------------------------
# Perspective / step walkers
# ---------------------------------------------------------------------------

def flatten_steps(steps):
    """Flatten subSequence nesting into a single ordered list of leaf steps."""
    flat = []
    for step in steps or []:
        if "subSequence" in step:
            flat.extend(flatten_steps(step["subSequence"].get("steps", [])))
        else:
            flat.append(step)
    return flat


def iter_all_steps(steps, ctx=""):
    """Yield (node, context_label, is_subsequence_header), recursively.

    Includes subSequence header dicts themselves (is_subsequence_header=True)
    so completeness checks can inspect their name/color/notes/steps fields.
    """
    for step in steps or []:
        if "subSequence" in step:
            ss = step["subSequence"]
            label = ss.get("name", "<unnamed subSequence>")
            new_ctx = f"{ctx} > subSequence:{label}"
            yield ss, new_ctx, True
            yield from iter_all_steps(ss.get("steps", []), new_ctx)
        else:
            label = step.get("label", "<unlabeled step>")
            yield step, f"{ctx} > step:{label}", False


def collect_step_targets(steps):
    targets = set()
    for step, _ctx, is_sub in iter_all_steps(steps):
        if is_sub:
            continue
        for key in TO_KEYS:
            if key in step:
                targets.add(step[key])
    return targets


def split_relation_targets(to_value):
    if isinstance(to_value, list):
        return [str(v).strip() for v in to_value]
    return [v.strip() for v in str(to_value).split(",")]


def _strip_block_scalar_bodies(lines):
    """Blank out block-scalar body lines so prose text can't be misread as
    YAML keys by the text-based checks (compact-style, block-literal-style)."""
    out = list(lines)
    in_block, key_indent = False, None
    for i, line in enumerate(lines):
        if in_block:
            if line.strip() == "":
                out[i] = ""
                continue
            indent = len(line) - len(line.lstrip(" "))
            if indent > key_indent:
                out[i] = ""
                continue
            in_block = False
        m = BLOCK_SCALAR_KEY_RE.match(line)
        if m:
            key_indent = len(m.group(1))
            in_block = True
    return out


# ---------------------------------------------------------------------------
# Deterministic (ERROR-level) checks
# ---------------------------------------------------------------------------

def check_undefined_references(data, by_id):
    findings = []
    referenced = set()
    for p in data.get("perspectives", []) or []:
        if "sequence" in p:
            seq = p["sequence"]
            if seq.get("start"):
                referenced.add(seq["start"])
            referenced |= collect_step_targets(seq.get("steps", []))
        if "relations" in p:
            for rel in p["relations"]:
                if rel.get("from"):
                    referenced.add(rel["from"])
                referenced |= set(split_relation_targets(rel.get("to", "")))
    for ref in sorted(x for x in referenced if x):
        if ref not in by_id:
            findings.append(Finding(
                "ERROR", "undefined-reference",
                f"Perspectives reference resource '{ref}', which is not defined in resources:",
            ))
    return findings, referenced


def check_unused_resources(data, referenced):
    findings = []

    def walk(rs):
        for r in rs or []:
            if not r.get("abstract") and not has_referenced_descendant(r, referenced):
                findings.append(Finding(
                    "WARNING", "unused-resource",
                    f"Resource '{r.get('name')}' is not referenced (directly or via a "
                    f"descendant) by any perspective; prune it or add it to a flow.",
                ))
            walk(r.get("children", []))

    walk(data.get("resources", []))
    return findings


def check_name_id_hygiene(by_id, id_list):
    """Restricted characters, and reference-key collisions.

    Note: resources are addressed by their *effective id* (explicit `id`, or
    `name` if no `id` is given). Two resources may share the same `name` and
    still be perfectly unambiguous, as long as at most one of them lacks an
    `id` -- that one is still uniquely addressable by its bare name. So this
    only needs to check for collisions on the effective id, not on raw name
    duplication.
    """
    findings = []

    for r in by_id.values():
        name = r.get("name", "")
        if RESTRICTED_CHARS.search(name) and "id" not in r:
            findings.append(Finding(
                "ERROR", "restricted-char-name",
                f"Resource named '{name}' contains a restricted character "
                f"(/ ^ * [ ] ,) but has no 'id' to reference it by.",
            ))

    for rid, count in Counter(id_list).items():
        if count > 1:
            findings.append(Finding(
                "ERROR", "duplicate-id",
                f"Id/name '{rid}' is used by {count} different resources; give "
                f"each a unique 'id' so perspectives can reference them "
                f"unambiguously.",
            ))

    return findings


def check_sequence_closure(data):
    """Control should return to the `start` actor at least once somewhere in
    the sequence -- not necessarily as the very last step, since a sequence
    may legitimately end on whichever actor most recently held control (e.g.
    after a `restartAt` hands control to a second actor for good). The same
    "returns at least once" expectation applies to every resource named in a
    `restartAt` step, since that's the actor/component the flow just jumped
    to.
    """
    findings = []
    for p in data.get("perspectives", []) or []:
        if "sequence" not in p:
            continue
        seq = p["sequence"]
        start = seq.get("start")
        flat = flatten_steps(seq.get("steps", []))
        if not flat:
            findings.append(Finding(
                "ERROR", "empty-sequence", "Sequence perspective has no steps.",
                location=p.get("name"),
            ))
            continue

        return_targets = {
            step[k] for step in flat for k in ("to", "toAsync", "toAndBack") if step.get(k)
        }
        restart_targets = {step["restartAt"] for step in flat if step.get("restartAt")}

        if start and start not in return_targets:
            findings.append(Finding(
                "WARNING", "no-return-to-start",
                f"No step ever returns control (via to/toAsync/toAndBack) to the "
                f"initiating actor '{start}'.",
                location=p.get("name"),
            ))

        for target in sorted(t for t in restart_targets if t not in return_targets):
            findings.append(Finding(
                "WARNING", "no-return-to-restart-target",
                f"'restartAt: {target}' is used, but no step ever returns control "
                f"back to '{target}'.",
                location=p.get("name"),
            ))
    return findings



def _fmt_names(names):
    return ", ".join(f"'{n}'" for n in names)


def check_call_return_parity(data):
    """Model each sequence as a call stack and warn when synchronous `to:`
    steps don't pair up with matching returns.

    `to: X` transfers control to X and leaves the caller waiting, so the
    caller is pushed onto a stack; a later `to:` back to the resource on top
    of that stack is its matching return, which pops it. `toAsync:` and
    `toAndBack:` don't move the control pointer at all, so neither needs a
    return step, and a self-referencing step (`to:` the resource that already
    holds control) is internal processing rather than a new frame.

    `color: gray` (the convention for a plain return-path hop) is used as a
    declaration that a step is a return: a gray step opens no frame, and one
    that lands on a resource nobody is waiting at is reported rather than
    silently read as a new call. Its absence is not read as proof of a call,
    since a return carrying real content keeps its own color and description.

    The authoring mistake this catches is a return that "jumps over" a
    resource: given A -> B -> C, a step straight back from C to A skips B's
    return, so B is left waiting forever in the rendered sequence. Returning
    to a resource deeper in the stack is the signature of that mistake. Also
    flagged: calls still awaiting a return when the sequence ends or when a
    `restartAt:` abandons the stack.

    WARNING-level because for steps that aren't marked gray the stack model
    can't tell a genuine callback (C legitimately calling back into A) from a
    skipped return; those findings say so.
    """
    findings = []
    for p in data.get("perspectives", []) or []:
        if "sequence" not in p:
            continue
        seq = p["sequence"]
        current = seq.get("start")
        stack = []  # resources awaiting a return, outermost caller first

        for step, ctx, is_sub in iter_all_steps(seq.get("steps", []), p.get("name", "")):
            if is_sub:
                continue

            if "restartAt" in step:
                if stack:
                    findings.append(Finding(
                        "WARNING", "unreturned-call",
                        f"'restartAt: {str(step['restartAt']).strip()}' abandons the "
                        f"call stack while {_fmt_names(reversed(stack))} is/are still "
                        f"awaiting a return. Walk control back up to the initiating "
                        f"actor first, unless this leg deliberately ends here "
                        f"(e.g. a background worker finishing its job).",
                        location=ctx,
                    ))
                stack = []
                current = str(step["restartAt"]).strip()
                continue

            # toAsync/toAndBack leave the control pointer where it is, so they
            # neither open nor close a frame.
            if "to" not in step:
                continue

            target = str(step["to"]).strip()
            if target == current:
                continue  # self-referencing step: internal work, returns implicitly

            # `color: gray` marks a step as a pure return-path hop. Match it
            # exactly: the documented base-dispatch step is `color: DimGray`
            # and is a forward call, not a return.
            is_return = str(step.get("color", "")).strip().lower() == "gray"

            if stack and stack[-1] == target:
                stack.pop()  # matching return to the caller on top of the stack
            elif target in stack:
                # A return, but to a frame further down: every frame above it
                # was called and never returned from. Match the nearest one,
                # since the same resource can legitimately recur in the stack.
                idx = len(stack) - 1 - stack[::-1].index(target)
                skipped = list(reversed(stack[idx + 1:]))
                chain = " -> ".join([current] + skipped + [target])
                hedge = "" if is_return else (
                    " (This step isn't marked 'color: gray', so it may be a "
                    "deliberate callback rather than a return — if it is a "
                    "return, color it gray.)"
                )
                findings.append(Finding(
                    "WARNING", "return-jumps-over-resource",
                    f"Control jumps from '{current}' back to '{target}', skipping "
                    f"the return path through {_fmt_names(skipped)} — each of those "
                    f"is still awaiting the return of a synchronous 'to:' call. "
                    f"Return one resource at a time instead: {chain}.{hedge}",
                    location=ctx,
                ))
                del stack[idx:]
            elif is_return:
                # A return-path hop to a resource that isn't awaiting one. A
                # gray step opens no frame either way; handing control back to
                # the initiating actor is how a `restartAt:` leg legitimately
                # closes out, but any other target means the return path lost
                # track of who the caller was.
                if target != seq.get("start"):
                    waiting = (f"'{current}' was called by '{stack[-1]}'" if stack
                               else f"nothing is awaiting a return from '{current}'")
                    findings.append(Finding(
                        "WARNING", "return-to-non-caller",
                        f"Step is marked 'color: gray' (a return-path hop) but hands "
                        f"control to '{target}', which never called '{current}' and "
                        f"isn't awaiting a return — {waiting}.",
                        location=ctx,
                    ))
            else:
                stack.append(current)  # a new call: the caller now waits
            current = target

        # Control ending back at the initiating actor is the closure the
        # sequence was after; any frames still on the stack there are an
        # artifact of a `restartAt:` leg re-entering mid-flow, not a call
        # someone forgot to return from.
        if stack and current != seq.get("start"):
            findings.append(Finding(
                "WARNING", "unreturned-call",
                f"Sequence ends with control at '{current}', but "
                f"{_fmt_names(reversed(stack))} never got control back after the "
                f"synchronous 'to:' call(s) made from there.",
                location=p.get("name"),
            ))
    return findings


def check_subsequence_completeness(data):
    findings = []
    required = ("name", "color", "notes", "steps")
    for p in data.get("perspectives", []) or []:
        if "sequence" not in p:
            continue
        for node, ctx, is_sub in iter_all_steps(p["sequence"].get("steps", []), p.get("name", "")):
            if not is_sub:
                continue
            missing = [k for k in required if not node.get(k)]
            if missing:
                findings.append(Finding(
                    "ERROR", "incomplete-subsequence",
                    f"subSequence is missing: {', '.join(missing)}", location=ctx,
                ))
    return findings


def check_no_parent_child_relations(data, parent_of):
    findings = []
    for p in data.get("perspectives", []) or []:
        if "relations" not in p:
            continue
        for rel in p["relations"]:
            src = rel.get("from")
            for tgt in split_relation_targets(rel.get("to", "")):
                if parent_of.get(src) == tgt or parent_of.get(tgt) == src:
                    findings.append(Finding(
                        "WARNING", "parent-child-relation",
                        f"Relation '{src}' -> '{tgt}' connects a resource to its own "
                        f"parent/child; containment is already shown by the tree.",
                        location=p.get("name"),
                    ))
    return findings


def check_label_description_pairing(data):
    findings = []
    for p in data.get("perspectives", []) or []:
        if "sequence" not in p:
            continue
        for step, ctx, is_sub in iter_all_steps(p["sequence"].get("steps", []), p.get("name", "")):
            if is_sub:
                continue
            if step.get("label") and not step.get("description") and step.get("color") != "gray":
                findings.append(Finding(
                    "ERROR", "missing-description",
                    "Step has a label but no description, and isn't a plain "
                    "color: gray return-path hop.", location=ctx,
                ))
    return findings


def check_block_literal_style(lines):
    """`description:` and `notes:` values must use YAML's block literal style
    (`|`), not a plain/quoted scalar or folded (`>`) style. Literal style is
    required so a paragraph can start with a special character like a
    backtick (a plain scalar can't start with one) and so intentional line
    breaks are preserved instead of being collapsed or reflowed.
    """
    findings = []
    scrubbed = _strip_block_scalar_bodies(lines)
    for i, line in enumerate(scrubbed):
        m = DESC_NOTES_KEY_RE.match(line)
        if not m:
            continue
        key_name, rest = m.group(2), m.group(3).strip()
        if not BLOCK_LITERAL_VALUE_RE.match(rest):
            shown = rest if rest else "(empty)"
            findings.append(Finding(
                "ERROR", "non-literal-block-scalar",
                f"'{key_name}:' does not use block literal style; found "
                f"{shown!r} instead of '|'. Use '{key_name}: |' so the value "
                f"can start with special characters and preserve intentional "
                f"line breaks.",
                location=f"line {i + 1}",
            ))
    return findings


# ---------------------------------------------------------------------------
# Heuristic (WARNING-level) checks
# ---------------------------------------------------------------------------

def check_compact_block_style(lines):
    """Flag mapping keys whose following list isn't in compact block-sequence
    style (dashes should align with the parent key, not be indented under it).
    Heuristic: relies on text-based indentation matching, not the parsed AST,
    since yaml.safe_load discards this distinction.
    """
    findings = []
    scrubbed = _strip_block_scalar_bodies(lines)
    n = len(scrubbed)
    for i, line in enumerate(scrubbed):
        m = BARE_KEY_RE.match(line)
        if not m:
            continue
        key_indent, key_name = len(m.group(1)), m.group(2)
        j = i + 1
        while j < n and scrubbed[j].strip() == "":
            j += 1
        if j >= n:
            continue
        dash_m = DASH_RE.match(scrubbed[j])
        if not dash_m:
            continue
        dash_indent = len(dash_m.group(1))
        if dash_indent != key_indent:
            findings.append(Finding(
                "WARNING", "non-compact-list-style",
                f"'{key_name}:' is followed by a list indented {dash_indent} spaces "
                f"(expected {key_indent}, matching the key). Use compact block-sequence "
                f"style: list dashes align with their parent key.",
                location=f"line {j + 1}",
            ))
    return findings


def _iter_description_texts(data):
    """Yield (location, text) for every description:/notes: string in the doc."""

    def walk_resources(resources, path):
        for r in resources or []:
            new_path = f"{path}/{r.get('name', '<unnamed>')}" if path else r.get("name", "<unnamed>")
            if isinstance(r.get("description"), str):
                yield (f"resource:{new_path}", r["description"])
            yield from walk_resources(r.get("children", []), new_path)

    def walk_steps(steps, ctx):
        for step in steps or []:
            if "subSequence" in step:
                ss = step["subSequence"]
                new_ctx = f"{ctx} > subSequence:{ss.get('name', '<unnamed>')}"
                if isinstance(ss.get("notes"), str):
                    yield (new_ctx, ss["notes"])
                yield from walk_steps(ss.get("steps", []), new_ctx)
            elif isinstance(step.get("description"), str):
                yield (f"{ctx} > step:{step.get('label', '<unlabeled>')}", step["description"])

    yield from walk_resources(data.get("resources", []), "")

    for p in data.get("perspectives", []) or []:
        ctx = f"perspective:{p.get('name', '<unnamed>')}"
        if isinstance(p.get("notes"), str):
            yield (ctx, p["notes"])
        if "sequence" in p:
            yield from walk_steps(p["sequence"].get("steps", []), ctx)


def check_hard_wrapped_paragraphs(data):
    """Flag block scalars that look manually word-wrapped: multiple lines of
    similar length with no blank line separating them. A real multi-paragraph
    note (blank line between paragraphs) is left alone; this is a heuristic,
    not a hard rule, so false positives/negatives are expected.
    """
    findings = []
    for location, text in _iter_description_texts(data):
        # Lines starting with "#" are Markdown headings (e.g. a "##### [file:line](url)"
        # code citation). They stand alone by design and are never wrapped prose, so
        # drop them before measuring rather than skipping the whole block scalar.
        lines = [l for l in text.rstrip("\n").split("\n")
                 if not l.lstrip().startswith("#")]
        if len(lines) < 2 or any(l.strip() == "" for l in lines):
            continue
        lengths = [len(l) for l in lines[:-1]]  # exclude last, naturally-short line
        if lengths and min(lengths) > 40 and (max(lengths) - min(lengths)) <= 25:
            findings.append(Finding(
                "WARNING", "possible-hard-wrap",
                f"{len(lines)} lines of similar length with no blank line between "
                f"them; check this wasn't manually wrapped instead of written as "
                f"one flowing line.", location=location,
            ))
    return findings


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_all_checks(data, raw_lines):
    by_id, parent_of, id_list, _name_list = build_resource_index(data)

    findings, referenced = check_undefined_references(data, by_id)
    findings += check_unused_resources(data, referenced)
    findings += check_name_id_hygiene(by_id, id_list)
    findings += check_sequence_closure(data)
    findings += check_call_return_parity(data)
    findings += check_subsequence_completeness(data)
    findings += check_no_parent_child_relations(data, parent_of)
    findings += check_label_description_pairing(data)
    findings += check_block_literal_style(raw_lines)
    findings += check_compact_block_style(raw_lines)
    findings += check_hard_wrapped_paragraphs(data)
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", nargs="?", default="ilograph.yaml",
                         help="Path to the Ilograph YAML file (default: ilograph.yaml)")
    parser.add_argument("--strict", action="store_true",
                         help="Exit non-zero on WARNINGs too, not just ERRORs")
    args = parser.parse_args()

    try:
        with open(args.path, "r", encoding="utf-8") as f:
            raw_text = f.read()
    except OSError as e:
        sys.exit(f"Could not read {args.path}: {e}")

    try:
        data = yaml.safe_load(raw_text)
    except yaml.YAMLError as e:
        sys.exit(f"{args.path} is not valid YAML:\n{e}")

    if not isinstance(data, dict) or "resources" not in data or "perspectives" not in data:
        sys.exit(f"{args.path} does not look like an Ilograph file "
                  f"(expected top-level 'resources:' and 'perspectives:' keys).")

    findings = run_all_checks(data, raw_text.splitlines())
    errors = [f for f in findings if f.level == "ERROR"]
    warnings = [f for f in findings if f.level == "WARNING"]

    if errors:
        print(f"=== ERRORS ({len(errors)}) ===")
        for f in errors:
            print(f"  {f}")
        print()

    if warnings:
        print(f"=== WARNINGS ({len(warnings)}) — heuristic, please eyeball these ===")
        for f in warnings:
            print(f"  {f}")
        print()

    if not errors and not warnings:
        print(f"{args.path}: all checks passed, no issues found.")

    fail = bool(errors) or (args.strict and bool(warnings))
    print(f"RESULT: {'FAIL' if fail else 'PASS'} "
          f"({len(errors)} error(s), {len(warnings)} warning(s))")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
