from django.db import migrations


def create_profiles(apps, schema_editor):
    User = apps.get_model("auth", "User")
    Profile = apps.get_model("accounts", "Profile")
    users = list(User.objects.order_by("pk"))
    admin_ids = {u.pk for u in users if u.is_superuser or u.is_staff}
    if users and not admin_ids:
        admin_ids.add(users[0].pk)  # the first user is the admin
    for u in users:
        Profile.objects.get_or_create(user=u, defaults={"role": "admin" if u.pk in admin_ids else "user"})


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial"), ("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(create_profiles, migrations.RunPython.noop)]
