from typing import ClassVar

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies: ClassVar = [
        ("scriptures", "0008_indexingjob_heartbeat"),
    ]

    operations: ClassVar = [
        migrations.AddField(
            model_name="indexingjob",
            name="ocr_pages_processed",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="indexingjob",
            name="ocr_checkpoint_pages",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
