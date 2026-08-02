"""Persist browser theme preference on the user account."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0002_alter_user_managers"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="preferred_theme",
            field=models.CharField(default="system", max_length=20),
        ),
    ]
