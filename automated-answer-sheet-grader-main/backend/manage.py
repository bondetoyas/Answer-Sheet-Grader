"""Admin helper:  python manage.py create-user <username> [--admin]   (prompts for password)"""

import getpass
import sys

import main


def create_user_cli(username: str, is_admin: bool = False):
    main.init_database()
    password = getpass.getpass("Password (min 8 chars): ")
    if password != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match.")
    try:
        with main.db() as con:
            main.create_user(con, username, password, is_admin)
    except ValueError as error:
        sys.exit(str(error))
    except main.sqlite3.IntegrityError:
        sys.exit("That username already exists.")
    print(f"User {username!r} created.")


if __name__ == "__main__":
    if len(sys.argv) in (3, 4) and sys.argv[1] == "create-user":
        create_user_cli(sys.argv[2], "--admin" in sys.argv[3:])
    else:
        sys.exit(__doc__)
