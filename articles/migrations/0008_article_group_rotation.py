# Generated manually for weighted article group rotation.

import uuid

from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


def fill_group_public_ids(apps, schema_editor):
    ArticleGroup = apps.get_model('articles', 'ArticleGroup')
    for group in ArticleGroup.objects.filter(public_id__isnull=True):
        group.public_id = uuid.uuid4()
        group.save(update_fields=['public_id'])


def create_group_memberships(apps, schema_editor):
    Article = apps.get_model('articles', 'Article')
    ArticleGroupMembership = apps.get_model('articles', 'ArticleGroupMembership')
    through_model = Article.groups.through
    now = timezone.now()
    memberships = []
    for relation in through_model.objects.all().iterator():
        memberships.append(ArticleGroupMembership(
            group_id=relation.articlegroup_id,
            article_id=relation.article_id,
            priority=50,
            utm_query='',
            is_active=True,
            impressions=0,
            created_at=now,
            updated_at=now,
        ))
    ArticleGroupMembership.objects.bulk_create(memberships, ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        ('articles', '0007_article_tracker_profile_articlegroup_tracker_profile'),
    ]

    operations = [
        migrations.AddField(
            model_name='articlegroup',
            name='public_id',
            field=models.UUIDField(blank=True, editable=False, null=True, verbose_name='Публичный ID'),
        ),
        migrations.CreateModel(
            name='ArticleGroupMembership',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('priority', models.PositiveIntegerField(default=50, verbose_name='Приоритет')),
                ('utm_query', models.CharField(blank=True, max_length=500, verbose_name='UTM для этой статьи')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активна в группе')),
                ('impressions', models.PositiveIntegerField(default=0, verbose_name='Показы из группы')),
                ('article', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='group_memberships', to='articles.article', verbose_name='Статья')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to='articles.articlegroup', verbose_name='Группа статей')),
            ],
            options={
                'verbose_name': 'Статья в группе',
                'verbose_name_plural': 'Статьи в группах',
                'ordering': ['group', 'article'],
            },
        ),
        migrations.RunPython(fill_group_public_ids, migrations.RunPython.noop),
        migrations.RunPython(create_group_memberships, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='articlegroup',
            name='public_id',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name='Публичный ID'),
        ),
        migrations.AddConstraint(
            model_name='articlegroupmembership',
            constraint=models.UniqueConstraint(fields=('group', 'article'), name='unique_article_group_membership'),
        ),
        migrations.AddIndex(
            model_name='articlegroupmembership',
            index=models.Index(fields=['group', 'is_active', 'priority'], name='articles_ar_group_i_5988dc_idx'),
        ),
        migrations.AddIndex(
            model_name='articlegroupmembership',
            index=models.Index(fields=['article', 'group'], name='articles_ar_article_62f61e_idx'),
        ),
    ]
