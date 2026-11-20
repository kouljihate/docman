"""Copy the local Document Manager database into a cloud MongoDB (e.g. Atlas).

Run it from the local stack, with the bundled mongo service up, so the source
data is reachable:

    docker compose --profile local-db up -d
    docker compose exec app python copy_to_atlas.py \
        --target "mongodb+srv://<user>:<password>@cluster0.vhxrozb.mongodb.net/cse" --yes

The target may also come from MONGO_TARGET_URI in the environment, which keeps
the credential out of the shell history and out of `docker compose exec` args.

What it copies: every non-system collection, with `_id` values preserved and
the collection's indexes recreated. Files on disk (backend/documents) are not
copied; only the database is.

Safety:
- prints the plan and does nothing unless you pass --dry-run or --yes,
- connects to and pings the target first, so a bad credential fails before
  anything is written,
- refuses to write into a non-empty target collection unless you pass --drop
  (replace it) or --append (add to it),
- compares document counts afterwards and reports any mismatch.
"""
import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pymongo import MongoClient
from pymongo.errors import PyMongoError
from pymongo.uri_parser import parse_uri

from config import VERSION

BATCH_SIZE = 500
DEFAULT_SOURCE = os.environ.get("LOCAL_MONGO_URI") or "mongodb://mongo:27017/cse"
DEFAULT_DB = "cse"


def mask_uri(uri: str) -> str:
    """Hide the password so the connection string can be printed safely."""
    return re.sub(r"(//[^:/@]+:)[^@]*@", r"\1***@", uri)


def database_name(uri: str, override: str = None) -> str:
    if override:
        return override
    try:
        name = parse_uri(uri).get("database")
    except Exception:
        name = None
    return name or DEFAULT_DB


def connect(uri: str, label: str):
    client = MongoClient(uri, serverSelectionTimeoutMS=15000, appname=f"docman-copy-{VERSION}")
    try:
        client.admin.command("ping")
    except PyMongoError as exc:
        raise SystemExit(f"ERROR: cannot connect to the {label} database ({mask_uri(uri)}): {exc}")
    return client


def copy_collection(source_db, target_db, name: str, mode: str) -> int:
    """Copy one collection and its indexes; return the number of documents written."""
    collection = source_db[name]
    index_info = collection.index_information()

    if name in target_db.list_collection_names():
        existing = target_db[name].estimated_document_count()
        if existing and mode == "abort":
            raise SystemExit(
                f"ERROR: target collection '{name}' already holds {existing} documents. "
                "Re-run with --drop to replace it or --append to add to it."
            )
        if mode == "drop":
            target_db[name].drop()
            print(f"  {name}: dropped {existing} existing documents")

    total = collection.count_documents({})
    written = 0
    batch = []
    for doc in collection.find({}):
        batch.append(doc)
        if len(batch) >= BATCH_SIZE:
            target_db[name].insert_many(batch, ordered=True)
            written += len(batch)
            batch = []
    if batch:
        target_db[name].insert_many(batch, ordered=True)
        written += len(batch)

    # Recreate indexes after the bulk load (faster, and _id already exists).
    for index_name, spec in index_info.items():
        if index_name == "_id_":
            continue
        keys = list(spec.get("key", []))
        options = {k: v for k, v in spec.items() if k not in ("key", "v", "ns")}
        options.setdefault("name", index_name)
        try:
            target_db[name].create_index(keys, **options)
        except PyMongoError as exc:
            print(f"  WARNING: could not recreate index '{index_name}' on {name}: {exc}")

    print(f"  {name}: {written}/{total} documents, {max(len(index_info) - 1, 0)} indexes")
    return written


def main() -> int:
    parser = argparse.ArgumentParser(
        description=f"Copy Document Manager {VERSION} data from a local MongoDB into a cloud MongoDB"
    )
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="Source MongoDB URI (default: %(default)s)")
    parser.add_argument(
        "--target", default=os.environ.get("MONGO_TARGET_URI", ""), help="Target MongoDB URI (or set MONGO_TARGET_URI)"
    )
    parser.add_argument("--source-db", help="Source database name (default: taken from the source URI)")
    parser.add_argument("--target-db", help="Target database name (default: taken from the target URI)")
    parser.add_argument("--drop", action="store_true", help="Replace target collections that already hold data")
    parser.add_argument("--append", action="store_true", help="Add to target collections that already hold data")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan without writing anything")
    parser.add_argument("--yes", action="store_true", help="Actually write to the target database")
    args = parser.parse_args()

    if not args.target:
        print("ERROR: no target database. Pass --target or set MONGO_TARGET_URI.")
        return 1
    if args.drop and args.append:
        print("ERROR: --drop and --append are mutually exclusive.")
        return 1
    mode = "drop" if args.drop else ("append" if args.append else "abort")

    source_name = database_name(args.source, args.source_db)
    target_name = database_name(args.target, args.target_db)
    print(f"Source: {mask_uri(args.source)} (database: {source_name})")
    print(f"Target: {mask_uri(args.target)} (database: {target_name})")

    source = connect(args.source, "source")
    source_db = source[source_name]
    collections = sorted(name for name in source_db.list_collection_names() if not name.startswith("system."))
    if not collections:
        raise SystemExit(f"ERROR: the source database '{source_name}' has no collections to copy.")

    counts = {name: source_db[name].count_documents({}) for name in collections}
    print(f"Collections: {len(collections)} ({sum(counts.values())} documents)")
    for name in collections:
        print(f"  {name}: {counts[name]}")

    if args.dry_run:
        print("Dry run: nothing was written.")
        return 0
    if not args.yes:
        print("Nothing written. Re-run with --yes to copy these collections.")
        return 0

    target = connect(args.target, "target")
    target_db = target[target_name]
    print("Copying ...")
    for name in collections:
        copy_collection(source_db, target_db, name, mode)

    print("Verifying counts ...")
    mismatched = []
    for name in collections:
        got = target_db[name].count_documents({})
        if got != counts[name]:
            mismatched.append((name, counts[name], got))
    for name, expected, got in mismatched:
        print(f"  MISMATCH {name}: expected {expected}, found {got}")
    if mismatched:
        print("Copy finished with count mismatches; re-run with --drop after checking the target.")
        return 1

    print(f"Done: {len(collections)} collections copied into '{target_name}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
