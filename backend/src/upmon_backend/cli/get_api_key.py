import argparse
import sys

from ..access import _load, derive_api_key
from ..config import Settings


def main():
    parser = argparse.ArgumentParser(
        description="Print the API key for an email listed in users.yaml"
    )
    parser.add_argument("email")
    args = parser.parse_args()

    settings = Settings()
    email = args.email.strip().lower()

    users = _load(settings.users_config, settings.api_key_secret)
    if users is None:
        print(f"Access config {settings.users_config} not found", file=sys.stderr)
        sys.exit(1)
    if email not in users:
        print(f"Email not in {settings.users_config}: {email}", file=sys.stderr)
        print("Known:", ", ".join(sorted(users)), file=sys.stderr)
        sys.exit(1)

    print(derive_api_key(settings.api_key_secret, email))


if __name__ == "__main__":
    main()
