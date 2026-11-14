from django.db import migrations, models


def restaurants_to_bars(apps, schema_editor):
    """이미 저장된 장소 중 카카오 세부 분류가 술집인 곳을 식당(FD6) → 술집(BAR)으로"""
    apps.get_model('api', 'Place').objects.filter(category='FD6', category_detail__contains='술집').update(category='BAR')


def bars_to_restaurants(apps, schema_editor):
    apps.get_model('api', 'Place').objects.filter(category='BAR').update(category='FD6')


class Migration(migrations.Migration):
    dependencies = [('api', '0009_collections')]

    operations = [
        migrations.AlterField(
            model_name='place',
            name='category',
            field=models.CharField(choices=[('CE7', '카페'), ('FD6', '식당'), ('BAR', '술집')], max_length=3, verbose_name='분류'),
        ),
        migrations.RunPython(restaurants_to_bars, bars_to_restaurants),
    ]
