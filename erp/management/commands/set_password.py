import getpass

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Change the password of any user in the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "username",
            help="Username (or email) of the account to update.",
        )
        parser.add_argument(
            "--password",
            dest="password",
            default=None,
            help=(
                "New password. If omitted you will be prompted interactively "
                "(recommended — avoids the password appearing in shell history)."
            ),
        )

    def handle(self, *args, **options):
        User = get_user_model()
        identifier = options["username"]

        # Look up by the model's USERNAME_FIELD first, fall back to email
        username_field = User.USERNAME_FIELD
        try:
            user = User.objects.get(**{username_field: identifier})
        except User.DoesNotExist:
            if username_field != "email":
                try:
                    user = User.objects.get(email=identifier)
                except User.DoesNotExist:
                    raise CommandError(f"No user found with {username_field} or email '{identifier}'.")
            else:
                raise CommandError(f"No user found with email '{identifier}'.")

        new_password = options["password"]
        if not new_password:
            new_password = getpass.getpass("New password: ")
            confirm = getpass.getpass("Confirm new password: ")
            if new_password != confirm:
                raise CommandError("Passwords do not match. No changes saved.")

        if not new_password:
            raise CommandError("Password cannot be empty.")

        user.set_password(new_password)
        user.save(update_fields=["password"])

        self.stdout.write(
            self.style.SUCCESS(f"Password changed successfully for user '{getattr(user, User.USERNAME_FIELD)}'.")
        )
