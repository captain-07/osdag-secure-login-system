from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from files.models import File

User = get_user_model()

# Same emails/password as their seed-data.json and the quick-fill buttons
# in index.html — so those buttons work against your real backend unmodified.
SEED_USERS = [
    {"email": "alice@example.com", "password": "Password123!",
     "files": ["resume_alice.pdf", "profile_photo.jpg"]},
    {"email": "bob@example.com", "password": "Password123!",
     "files": ["project_notes.txt", "invoice_march.pdf"]},
    {"email": "carol@example.com", "password": "Password123!",
     "files": ["test_plan.docx", "vacation.png"]},
]


class Command(BaseCommand):
    help = "Seeds 3 test users (matching the provided seed-data.json) with sample files."

    def handle(self, *args, **options):
        for u in SEED_USERS:
            user, created = User.objects.get_or_create(email=u["email"])
            if created:
                # set_password hashes it — never assign to user.password directly.
                user.set_password(u["password"])
                user.save()
                self.stdout.write(self.style.SUCCESS(f"Created {user.email}"))
            else:
                self.stdout.write(f"{user.email} already exists, skipping")

            for fname in u["files"]:
                if not File.objects.filter(owner=user, filename=fname).exists():
                    dummy = ContentFile(f"Dummy content for {fname}".encode(), name=fname)
                    File.objects.create(
                        owner=user, filename=fname, file=dummy,
                        mime_type="application/octet-stream", size_bytes=dummy.size,
                    )
            self.stdout.write(f"Seeded files for {user.email}")

        self.stdout.write(self.style.SUCCESS("Done."))