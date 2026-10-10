"""CF-06: reproducible checks of reviewed Markdown declarations and local links.

Only execute declaration blocks from the trusted repository contract. This checks
documentation consistency, not implemented search/trash behavior or DEC approval.
"""

import argparse
import dataclasses
import inspect
import re
import sys
import types
from pathlib import Path
from typing import get_type_hints
from urllib.parse import unquote
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
MODEL_FIELDS = {
    "SearchNotesCriteria": (
        "text",
        "category_id",
        "priority",
        "start_date",
        "end_date",
        "date_field",
        "sort",
        "direction",
        "limit",
        "cursor",
    ),
    "CompiledNoteCriteria": (
        "text",
        "category_id",
        "priority",
        "utc_start",
        "utc_end_exclusive",
        "date_field",
        "sort",
        "direction",
        "limit",
        "cursor",
    ),
    "TrashNoteInput": ("note_id", "expected_version"),
    "RestoreNoteInput": ("note_id", "expected_version"),
    "PurgeNoteInput": ("note_id", "expected_version", "confirmed"),
    "ListTrashInput": ("limit", "cursor"),
    "TrashedNote": ("note", "deleted_at"),
    "TrashPage": ("items", "next_cursor"),
    "TrashedNoteView": ("note", "deleted_at"),
    "TrashListView": ("items", "next_cursor"),
}
PORT_METHODS = {
    "SearchRepository": ("search",),
    "TrashRepository": ("move_to_trash", "restore", "list_trashed", "purge_confirmed"),
}


def verify_declarations(source: str) -> int:
    blocks = re.findall(r"```python\n(.*?)\n```", source, re.DOTALL)
    if len(blocks) != 5:
        raise ValueError("Expected all five declaration blocks.")
    module = types.ModuleType("_noteapp_contract_review_" + uuid4().hex)
    namespace = module.__dict__
    sys.modules[module.__name__] = module
    try:
        for index, block in enumerate(blocks, 1):
            exec(compile(block, f"contract-block-{index}", "exec"), namespace)
        models = {
            name: model
            for name, model in namespace.items()
            if inspect.isclass(model)
            and model.__module__ == module.__name__
            and dataclasses.is_dataclass(model)
        }
        if models.keys() != MODEL_FIELDS.keys():
            raise ValueError("Documented model set changed without contract review.")
        for name, fields in MODEL_FIELDS.items():
            model = models[name]
            actual_fields = tuple(field.name for field in dataclasses.fields(model))
            if not model.__dataclass_params__.frozen or actual_fields != fields:
                raise ValueError(f"Immutable field contract changed: {name}.")
            if set(get_type_hints(model, namespace)) != set(fields):
                raise ValueError(f"Missing typed model fields: {name}.")
        for name, methods in PORT_METHODS.items():
            port = namespace.get(name)
            if port is None or not getattr(port, "_is_protocol", False):
                raise ValueError(f"Missing protocol: {name}.")
            for method_name in methods:
                method = getattr(port, method_name, None)
                if not inspect.isfunction(method):
                    raise ValueError(f"Missing port method: {name}.{method_name}.")
                hints = get_type_hints(method, namespace)
                parameters = set(inspect.signature(method).parameters) - {"self"}
                if set(hints) != parameters | {"return"}:
                    raise ValueError(f"Missing typed port signature: {name}.{method_name}.")
        default = namespace["SearchNotesCriteria"]()
        if (
            (default.text, default.limit, default.cursor) != ("", 30, None)
            or default.date_field is not namespace["DateField"].UPDATED_AT
            or default.sort is not namespace["SortMode"].UPDATED_AT
            or default.direction is not namespace["SortDirection"].DESC
        ):
            raise ValueError("Proposed search defaults changed without contract review.")
        if namespace["PurgeNoteInput"]("existing-id", 1).confirmed is not False:
            raise ValueError("Purge confirmation must default to False.")
    except (SyntaxError, NameError, TypeError, AttributeError, ImportError) as error:
        raise ValueError("Invalid or unresolved contract declaration.") from error
    finally:
        sys.modules.pop(module.__name__, None)
    return len(blocks)


def verify_documentation(root: Path = ROOT) -> tuple[int, int]:
    contract = root / "docs/architecture/PHASE2_PUBLIC_CONTRACTS.md"
    docs = [
        root / "docs/adr/0002-phase2-query-trash-contract.md",
        root / "docs/testing/PHASE2_P2_02_REVIEW.md",
        *sorted((root / "docs/architecture").glob("PHASE2_*.md")),
        *sorted((root / "docs/srs/phase 2").rglob("*.md")),
    ]
    try:
        block_count = verify_declarations(contract.read_text(encoding="utf-8"))
        sources = {doc: doc.read_text(encoding="utf-8") for doc in docs}
        link_count = 0
        for doc, source in sources.items():
            for target in re.findall(r"\]\(([^)]+)\)", source):
                if target.startswith(("http:", "https:", "#")):
                    continue
                path = doc.parent / unquote(target.split("#")[0])
                if not path.exists():
                    raise ValueError(f"Broken local link in {doc.relative_to(root)}: {target}.")
                link_count += 1
    except (OSError, UnicodeError) as error:
        raise ValueError("Required contract documentation is missing or unreadable.") from error
    return block_count, link_count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Trusted checkout root")
    args = parser.parse_args()
    try:
        blocks, links = verify_documentation(args.root.resolve())
    except ValueError as error:
        print(f"Contract check failed: {error}", file=sys.stderr)
        return 1
    print(f"Verified {blocks} declaration blocks, 10 frozen models, 2 typed ports, {links} links.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
