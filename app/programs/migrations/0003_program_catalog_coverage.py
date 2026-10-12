from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('programs', '0002_source_status_user_authored'),
    ]

    operations = [
        migrations.AddField(
            model_name='program',
            name='catalog_source_url',
            field=models.URLField(blank=True, help_text='Where the owner publishes the list of entries.'),
        ),
        migrations.AddField(
            model_name='program',
            name='catalog_expected_count',
            field=models.PositiveIntegerField(blank=True, help_text='How many entries the program has, if you know. Empty means unknown.', null=True),
        ),
        migrations.AddField(
            model_name='program',
            name='catalog_validated_complete',
            field=models.BooleanField(default=False, help_text='Tick only after you checked every entry against its source.'),
        ),
    ]
