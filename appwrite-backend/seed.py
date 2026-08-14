"""
Seeds 3 users + their files into Appwrite using the Server SDK + API key.
This runs server-side (never in the browser) because creating users
directly and setting arbitrary document permissions requires the
privileged Server API key, not the public client SDK.
"""
import os
from appwrite.client import Client
from appwrite.services.users import Users
from appwrite.services.databases import Databases
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
databases = Databases(client)
storage = Storage(client)

SEED_USERS = [
    {"email": "alice@example.com", "password": "Password123!", "name": "Alice Nakamura",
     "files": ["resume_alice.pdf", "profile_photo.jpg"]},
    {"email": "bob@example.com", "password": "Password123!", "name": "Bob Alvarez",
     "files": ["project_notes.txt", "invoice_march.pdf"]},
    {"email": "carol@example.com", "password": "Password123!", "name": "Carol Whitfield",
     "files": ["test_plan.docx", "vacation.png"]},
]

for u in SEED_USERS:
    # Users API creates the user directly (hashing handled internally by
    # Appwrite) — no client-side signup flow needed for seeding.
    user = users.create(user_id=ID.unique(), email=u["email"], password=u["password"], name=u["name"])
    user_id = user["$id"]
    print(f"Created user {u['email']} ({user_id})")

    for fname in u["files"]:
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

        # ...then create the metadata document pointing at it, same
        # per-user permission pattern.
        databases.create_document(
            database_id=DATABASE_ID,
            collection_id=FILES_COLLECTION_ID,
            document_id=ID.unique(),
            data={
                "ownerId": user_id,
                "filename": fname,
                "mimeType": "application/octet-stream",
                "sizeBytes": len(dummy_bytes),
                "storageFileId": uploaded["$id"],
            },
            permissions=[Permission.read(Role.user(user_id))],
        )
    print(f"Seeded {len(u['files'])} files for {u['email']}")

print("Done.")