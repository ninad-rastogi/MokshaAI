from django.db import migrations, models
from pgvector.django import VectorExtension
import pgvector.django.vector


class Migration(migrations.Migration):
    dependencies = [("chat", "0002_documentchunk")]

    operations = [
        VectorExtension(),
        migrations.RemoveField(model_name="documentchunk", name="embedding"),
        migrations.AddField(
            model_name="documentchunk",
            name="embedding",
            field=pgvector.django.vector.VectorField(dimensions=1024, null=True),
        ),
        migrations.AddField(
            model_name="message",
            name="sources",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="documentchunk",
            name="index_version",
            field=models.UUIDField(db_index=True, null=True),
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS document_chunks_embedding_hnsw "
            "ON document_chunks USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64);",
            "DROP INDEX IF EXISTS document_chunks_embedding_hnsw;",
        ),
    ]
