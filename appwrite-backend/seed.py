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

SEED_USERS = [
    {"email": "alice@example.com", "password": "Password123!", "name": "Alice Nakamura",
     "files": ["resume_alice.pdf", "profile_photo.jpg"]},
    {"email": "bob@example.com", "password": "Password123!", "name": "Bob Alvarez",
     "files": ["project_notes.txt", "invoice_march.pdf"]},
    {"email": "carol@example.com", "password": "Password123!", "name": "Carol Whitfield",
     "files": ["test_plan.docx", "vacation.png"]},
]

existing = {u.email: u.id for u in users.list().users}
existing_rows = set()
rows = tablesdb.list_rows(database_id=DATABASE_ID, table_id=FILES_COLLECTION_ID, total=True)
for r in rows.rows:
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