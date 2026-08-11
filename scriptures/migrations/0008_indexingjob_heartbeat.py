from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [  # noqa: RUF012
        ("scriptures", "0004_scriptureindexversion_indexingjob_index_version_and_more"),
    ]

    operations = [  # noqa: RUF012
        migrations.AddField(
            model_name="indexingjob",
            name="heartbeat_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
