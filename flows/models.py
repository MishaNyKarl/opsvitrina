import uuid

from django.db import models

from core.models import OwnedModel, TimestampedModel


class FlowStatus(models.TextChoices):
    ACTIVE = 'active', 'Активный'
    PAUSED = 'paused', 'Пауза'
    ARCHIVED = 'archived', 'Архив'


class Domain(TimestampedModel):
    name = models.CharField('Домен', max_length=255, unique=True)
    is_active = models.BooleanField('Активен', default=True)

    class Meta:
        verbose_name = 'Домен'
        verbose_name_plural = 'Домены'
        ordering = ['name']

    def __str__(self):
        return self.name


class TrafficSource(TimestampedModel):
    name = models.CharField('Название', max_length=120, unique=True)
    slug = models.SlugField('Slug', max_length=140, unique=True)

    class Meta:
        verbose_name = 'Источник трафика'
        verbose_name_plural = 'Источники трафика'
        ordering = ['name']

    def __str__(self):
        return self.name


class Flow(OwnedModel):
    name = models.CharField('Название потока', max_length=120)
    public_id = models.UUIDField('Публичный ID', default=uuid.uuid4, unique=True, editable=False)
    article = models.ForeignKey(
        'articles.Article',
        verbose_name='Статья',
        on_delete=models.PROTECT,
        related_name='flows',
    )
    domain = models.ForeignKey(
        Domain,
        verbose_name='Домен',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='flows',
    )
    traffic_source = models.ForeignKey(
        TrafficSource,
        verbose_name='Источник трафика',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='flows',
    )
    design = models.CharField('Дизайн', max_length=80, blank=True)
    status = models.CharField(
        'Статус',
        max_length=24,
        choices=FlowStatus.choices,
        default=FlowStatus.ACTIVE,
    )
    no_redirect = models.BooleanField('Без редиректа', default=False)
    collect_push_base = models.BooleanField('Сбор push-базы', default=False)
    show_back_button = models.BooleanField('Кнопка Назад', default=True)
    show_popup = models.BooleanField('Показ Pop-Up', default=True)
    analytics_enabled = models.BooleanField('Системы аналитики', default=True)

    class Meta:
        verbose_name = 'Поток'
        verbose_name_plural = 'Потоки'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['owner', 'created_at']),
            models.Index(fields=['public_id']),
        ]

    def __str__(self):
        return self.name
