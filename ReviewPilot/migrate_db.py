from sqlalchemy import inspect, text

from app import create_app
from app.models import db

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)

    existing_columns = {
        column["name"]
        for column in inspector.get_columns("reply_versions")
    }

    new_columns = {
        "is_deleted": "BOOLEAN NOT NULL DEFAULT 0",
        "deleted_at": "DATETIME",
    }

    with db.engine.begin() as connection:
        for column_name, column_definition in new_columns.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(
                        f"ALTER TABLE reply_versions "
                        f"ADD COLUMN {column_name} {column_definition}"
                    )
                )
                print(f"Added column: {column_name}")
            else:
                print(f"Already exists: {column_name}")

    print("Reply-version migration completed successfully.")