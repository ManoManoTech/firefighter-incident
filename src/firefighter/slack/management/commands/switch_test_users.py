"""Django management command to switch Slack user IDs for test environment.

This command:
1. Fetches all users from the test Slack workspace
2. Generates a mapping file based on email addresses
3. Updates the database with test Slack user IDs
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from firefighter.incidents.models.user import User
from firefighter.slack.models.user import SlackUser

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Generate and apply Slack user mapping for test environment"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--generate-only",
            action="store_true",
            help="Only generate the mapping file, don't apply changes",
        )
        parser.add_argument(
            "--mapping-file",
            type=str,
            default="slack_test_mapping.json",
            help="Path to the mapping file (default: slack_test_mapping.json)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be changed without making actual changes",
        )
        parser.add_argument(
            "--restore",
            action="store_true",
            help="Restore original Slack IDs from mapping file",
        )

    def _raise_mapping_file_not_found(self, mapping_file: Path) -> None:
        """Raise error when mapping file is not found."""
        error_msg = f"Mapping file {mapping_file} not found"
        raise CommandError(error_msg)

    def _raise_slack_token_not_configured(self) -> None:
        """Raise error when Slack token is not configured."""
        raise CommandError("SLACK_BOT_TOKEN not configured")

    def handle(self, *args: Any, **options: Any) -> None:
        """Main command handler."""
        mapping_file = Path(options["mapping_file"])

        try:
            if options["restore"]:
                # Restore original Slack IDs from mapping file
                if not mapping_file.exists():
                    self._raise_mapping_file_not_found(mapping_file)

                self.stdout.write("📄 Loading mapping from file...")
                slack_mapping = self._load_mapping_file(mapping_file)

                self.stdout.write("🔄 Restoring original Slack IDs...")
                updated_count = self._restore_mapping(slack_mapping, dry_run=options["dry_run"])

                if options["dry_run"]:
                    self.stdout.write(
                        self.style.WARNING(f"🔍 DRY RUN: Would restore {updated_count} users")
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(f"✅ Restored {updated_count} users to original Slack IDs")
                    )
                return

            if not settings.SLACK_BOT_TOKEN:
                self._raise_slack_token_not_configured()

            # Step 1: Generate mapping by querying test Slack workspace
            self.stdout.write("🔍 Fetching users from test Slack workspace...")
            slack_mapping = self._generate_slack_mapping()

            # Step 2: Save mapping to file
            self._save_mapping_file(slack_mapping, mapping_file)
            self.stdout.write(
                self.style.SUCCESS(f"✅ Mapping file saved to {mapping_file}")
            )

            if options["generate_only"]:
                self.stdout.write("📄 Generation complete. Use --apply to update database.")
                return

            # Step 3: Apply mapping to database
            self.stdout.write("📝 Applying mapping to database...")
            updated_count = self._apply_mapping(slack_mapping, dry_run=options["dry_run"])

            if options["dry_run"]:
                self.stdout.write(
                    self.style.WARNING(f"🔍 DRY RUN: Would update {updated_count} users")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"✅ Updated {updated_count} users with test Slack IDs")
                )

        except SlackApiError as e:
            error_msg = f"Slack API error: {e.response['error']}"
            raise CommandError(error_msg) from e
        except Exception as e:
            error_msg = f"Error: {e}"
            raise CommandError(error_msg) from e

    def _generate_slack_mapping(self) -> dict[str, dict[str, Any]]:
        """Generate mapping by querying test Slack workspace."""
        client = WebClient(token=settings.SLACK_BOT_TOKEN)

        # Get all users from test Slack workspace
        try:
            response = client.users_list()
            slack_users = response["members"]
        except SlackApiError as e:
            error_msg = f"Failed to fetch Slack users: {e.response['error']}"
            raise CommandError(error_msg) from e

        # Create mapping: email -> test_slack_id
        slack_email_to_id = {}
        for slack_user in slack_users:
            if slack_user.get("deleted") or slack_user.get("is_bot"):
                continue

            profile = slack_user.get("profile", {})
            email = profile.get("email")
            if email:
                slack_email_to_id[email.lower()] = slack_user["id"]

        self.stdout.write(f"📧 Found {len(slack_email_to_id)} users with emails in test Slack")

        # Get all users from database
        db_users = User.objects.exclude(email__isnull=True).exclude(email="")

        # Generate mapping for users that exist in both places
        mapping = {}
        matched_count = 0
        not_found_count = 0

        for db_user in db_users:
            if db_user.email and db_user.email.lower() in slack_email_to_id:
                test_slack_id = slack_email_to_id[db_user.email.lower()]
                # Get current slack_id from SlackUser relation
                current_slack_id = None
                if hasattr(db_user, "slack_user") and db_user.slack_user:
                    current_slack_id = db_user.slack_user.slack_id

                mapping[db_user.email] = {
                    "original_slack_id": current_slack_id,
                    "test_slack_id": test_slack_id,
                    "name": f"{db_user.first_name} {db_user.last_name}".strip(),
                }
                matched_count += 1
            else:
                not_found_count += 1

        self.stdout.write(f"🎯 Matched {matched_count} users between database and test Slack")
        if not_found_count > 0:
            self.stdout.write(f"⚠️  {not_found_count} database users not found in test Slack")
        return mapping

    def _save_mapping_file(self, mapping: dict[str, Any], file_path: Path) -> None:
        """Save mapping to JSON file."""
        with file_path.open("w", encoding="utf-8") as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)

    def _load_mapping_file(self, file_path: Path) -> dict[str, Any]:
        """Load mapping from JSON file."""
        with file_path.open(encoding="utf-8") as f:
            return json.load(f)

    def _apply_mapping(self, mapping: dict[str, Any], *, dry_run: bool = False) -> int:
        """Apply the mapping to update database users."""
        updated_count = 0

        for email, user_data in mapping.items():
            test_slack_id = user_data["test_slack_id"]

            try:
                user = User.objects.get(email=email)

                # Get current slack_id from SlackUser relation
                current_slack_id = None
                if hasattr(user, "slack_user") and user.slack_user:
                    current_slack_id = user.slack_user.slack_id

                if current_slack_id == test_slack_id:
                    continue  # Already has the test ID

                if dry_run:
                    self.stdout.write(
                        f"🔄 Would update {email}: {current_slack_id} -> {test_slack_id}"
                    )
                elif hasattr(user, "slack_user") and user.slack_user:
                    user.slack_user.slack_id = test_slack_id
                    user.slack_user.save(update_fields=["slack_id"])
                    self.stdout.write(f"✅ Updated {email}: {current_slack_id} -> {test_slack_id}")
                else:
                    # Create new SlackUser if it doesn't exist
                    SlackUser.objects.create(user=user, slack_id=test_slack_id)
                    self.stdout.write(f"✅ Created SlackUser for {email}: -> {test_slack_id}")

                updated_count += 1

            except User.DoesNotExist:
                self.stdout.write(f"❌ User not found in database: {email}")
            except (SlackUser.DoesNotExist, ValueError) as e:
                self.stdout.write(f"❌ Error updating {email}: {e}")

        return updated_count

    def _restore_mapping(self, mapping: dict[str, Any], *, dry_run: bool = False) -> int:
        """Restore original Slack IDs from mapping."""
        updated_count = 0

        for email, user_data in mapping.items():
            original_slack_id = user_data["original_slack_id"]

            try:
                user = User.objects.get(email=email)

                # Get current slack_id from SlackUser relation
                current_slack_id = None
                if hasattr(user, "slack_user") and user.slack_user:
                    current_slack_id = user.slack_user.slack_id

                if current_slack_id == original_slack_id:
                    continue  # Already has the original ID

                if dry_run:
                    self.stdout.write(
                        f"🔄 Would restore {email}: {current_slack_id} -> {original_slack_id}"
                    )
                elif hasattr(user, "slack_user") and user.slack_user:
                    if original_slack_id:
                        user.slack_user.slack_id = original_slack_id
                        user.slack_user.save(update_fields=["slack_id"])
                        self.stdout.write(f"✅ Restored {email}: {current_slack_id} -> {original_slack_id}")
                    else:
                        # If original was None, delete the SlackUser
                        user.slack_user.delete()
                        self.stdout.write(f"✅ Removed SlackUser for {email}: {current_slack_id} -> None")
                else:
                    self.stdout.write(f"⚠️  User {email} has no SlackUser to restore")
                    continue

                updated_count += 1

            except User.DoesNotExist:
                self.stdout.write(f"❌ User not found in database: {email}")
            except (SlackUser.DoesNotExist, ValueError) as e:
                self.stdout.write(f"❌ Error restoring {email}: {e}")

        return updated_count
