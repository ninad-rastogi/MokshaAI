"""
One-time migration command to import existing JSON chat files to PostgreSQL.

Usage:
    python manage.py migrate_json_chats
    python manage.py migrate_json_chats --user user@example.com
"""

import json
import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from chat.models import Chat, Message

logger = logging.getLogger("chat.management.migrate")


class Command(BaseCommand):
    help = "Migrate existing JSON chat files to PostgreSQL"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            type=str,
            required=True,
            help="Email of the user to assign chats to",
        )

    def handle(self, *args, **options):
        from users.models import User

        user_email = options["user"]

        try:
            user = User.objects.get(email=user_email)
        except User.DoesNotExist:
            raise CommandError(
                f"User '{user_email}' not found. " f"Create the user first."
            )

        chats_dir = settings.DATA_DIR / "chats"
        if not chats_dir.exists():
            self.stdout.write(
                self.style.WARNING(f"Chats directory not found: {chats_dir}")
            )
            return

        json_files = list(chats_dir.glob("*.json"))
        if not json_files:
            self.stdout.write(self.style.WARNING("No JSON chat files found."))
            return

        migrated = 0
        skipped = 0

        for json_file in json_files:
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                chat_id = data.get("id", json_file.stem)
                chat_name = data.get("name", "New Spiritual Conversation")

                # Check if already migrated
                if Chat.objects.filter(id=chat_id).exists():
                    self.stdout.write(f"  Skipping {json_file.name} (already exists)")
                    skipped += 1
                    continue

                # Create chat
                chat = Chat.objects.create(
                    id=chat_id,
                    user=user,
                    name=chat_name,
                )

                # Create messages
                messages = data.get("messages", [])
                for msg_data in messages:
                    Message.objects.create(
                        chat=chat,
                        role=msg_data.get("role", "user"),
                        content=msg_data.get("content", ""),
                        mode=msg_data.get("mode", ""),
                    )

                migrated += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Migrated {json_file.name} " f"({len(messages)} messages)"
                    )
                )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  Error migrating {json_file.name}: {e}")
                )

        self.stdout.write(
            self.style.SUCCESS(f"\nDone! Migrated: {migrated}, Skipped: {skipped}")
        )
