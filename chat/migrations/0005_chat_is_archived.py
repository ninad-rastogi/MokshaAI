"""Add archived state for chats."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0004_generation_runs"),
    ]

    operations = [
        migrations.AddField(
            model_name="chat",
            name="is_archived",
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]
