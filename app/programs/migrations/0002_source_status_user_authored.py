from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('programs', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='awardversion',
            name='source_status',
            field=models.CharField(choices=[('unverified', 'Unverified'), ('user_authored', 'User-authored'), ('reviewed', 'Reviewed'), ('verified', 'Verified'), ('disputed', 'Disputed')], default='unverified', max_length=20),
        ),
    ]
