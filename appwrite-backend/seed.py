"""
Seeds 3 users + their files into Appwrite using the Server SDK + API key.
This runs server-side (never in the browser) because creating users
directly and setting arbitrary document permissions requires the
privileged Server API key, not the public client SDK.
"""
import os
from appwrite.client import Client
from appwrite.services.users import Users
from appwrite.services.tables_db import TablesDB
from appwrite.services.storage import Storage
from appwrite.id import ID
from appwrite.input_file import InputFile
from appwrite.permission import Permission
from appwrite.query import Query
from appwrite.role import Role

ENDPOINT = os.environ["APPWRITE_ENDPOINT"]
PROJECT_ID = os.environ["APPWRITE_PROJECT_ID"]
API_KEY = os.environ["APPWRITE_API_KEY"]
DATABASE_ID = os.environ["APPWRITE_DATABASE_ID"]
FILES_COLLECTION_ID = os.environ["APPWRITE_FILES_COLLECTION_ID"]
BUCKET_ID = os.environ["APPWRITE_BUCKET_ID"]

client = Client().set_endpoint(ENDPOINT).set_project(PROJECT_ID).set_key(API_KEY)
users = Users(client)
tablesdb = TablesDB(client)
storage = Storage(client)

# Appwrite list endpoints are paginated (default page size 25). Loop over every
# page so re-runs of this script with more than 25 existing users/rows still
# detect them instead of hitting unique-constraint errors / duplicate uploads.
PAGE_SIZE = 25


def _all_users():
    # The SDK types `.total` as float (3.0), but range() needs ints.
    total = int(users.list(queries=[Query.limit(PAGE_SIZE)], total=True).total)
    for offset in range(0, total, PAGE_SIZE):
        page = users.list(
            queries=[Query.limit(PAGE_SIZE), Query.offset(offset)]
        )
        yield from page.users


def _all_rows():
    total = int(
        tablesdb.list_rows(
            database_id=DATABASE_ID,
            table_id=FILES_COLLECTION_ID,
            total=True,
        ).total
    )
    for offset in range(0, total, PAGE_SIZE):
        page = tablesdb.list_rows(
            database_id=DATABASE_ID,
            table_id=FILES_COLLECTION_ID,
            queries=[Query.limit(PAGE_SIZE), Query.offset(offset)],
        )
        yield from page.rows

SEED_USERS = [
    {"email": "alice@example.com", "password": "Password123!", "name": "Alice Nakamura",
     "files": ["resume_alice.pdf", "profile_photo.jpg"]},
    {"email": "bob@example.com", "password": "Password123!", "name": "Bob Alvarez",
     "files": ["project_notes.txt", "invoice_march.pdf"]},
    {"email": "carol@example.com", "password": "Password123!", "name": "Carol Whitfield",
     "files": ["test_plan.docx", "vacation.png"]},
]

existing = {u.email: u.id for u in _all_users()}
existing_rows = set()
for r in _all_rows():
    existing_rows.add((r.data["ownerId"], r.data["filename"]))

for u in SEED_USERS:
    # Re-runs are safe: if the email already exists, reuse the user instead
    # of erroring on the unique-email constraint.
    if u["email"] in existing:
        user_id = existing[u["email"]]
        print(f"User {u['email']} already exists ({user_id}), reusing")
    else:
        # Users API creates the user directly (hashing handled internally by
        # Appwrite) — no client-side signup flow needed for seeding.
        user = users.create(user_id=ID.unique(), email=u["email"], password=u["password"], name=u["name"])
        user_id = user.id
        print(f"Created user {u['email']} ({user_id})")

    for fname in u["files"]:
        if (user_id, fname) in existing_rows:
            print(f"  Skip {fname} for {u['email']} (already seeded)")
            continue
        # Upload the actual bytes to storage first...
        dummy_bytes = f"Dummy content for {fname}".encode()
        uploaded = storage.create_file(
            bucket_id=BUCKET_ID,
            file_id=ID.unique(),
            file=InputFile.from_bytes(dummy_bytes, filename=fname),
            # Scoping read permission to this exact user is what makes
            # isolation enforcement Appwrite's job, not our code's job.
            permissions=[Permission.read(Role.user(user_id))],
        )

        # ...then create the metadata row pointing at it, same per-user
        # permission pattern. This database is TablesDB type, so we use
        # create_row (tables/rows), NOT the deprecated create_document.
        tablesdb.create_row(
            database_id=DATABASE_ID,
            table_id=FILES_COLLECTION_ID,
            row_id=ID.unique(),
            data={
                "ownerId": user_id,
                "filename": fname,
                "mimeType": "application/octet-stream",
                "sizeBytes": len(dummy_bytes),
                "storageFileId": uploaded.id,
            },
            permissions=[Permission.read(Role.user(user_id))],
        )
    print(f"Seeded {len(u['files'])} files for {u['email']}")

print("Done.")