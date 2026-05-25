import uuid

from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django_ckeditor_5.fields import CKEditor5Field

from core.models import OwnedModel, TimestampedModel


class ArticleStatus(models.TextChoices):
    DRAFT = 'draft', 'Черновик'
    ACTIVE = 'active', 'Активна'
    PAUSED = 'paused', 'Пауза'
    ARCHIVED = 'archived', 'Архив'


class ArticleType(models.TextChoices):
    INTERNAL = 'internal', 'Статья на платформе'
    EXTERNAL = 'external', 'Внешний ленд'
    HTML = 'html', 'HTML-файл'


class OutboundMarkValueMode(models.TextChoices):
    ARTICLE_ID = 'article_id', 'ID статьи'
    PUBLIC_ID = 'public_id', 'Публичный ID'
    CUSTOM = 'custom', 'Свое значение'


class Category(TimestampedModel):
    name = models.CharField('Название', max_length=120, unique=True)
    slug = models.SlugField('Slug', max_length=140, unique=True, blank=True)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Vertical(TimestampedModel):
    name = models.CharField('Название', max_length=120, unique=True)
    slug = models.SlugField('Slug', max_length=140, unique=True, blank=True)

    class Meta:
        verbose_name = 'Вертикаль'
        verbose_name_plural = 'Вертикали'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ArticleGroup(OwnedModel):
    name = models.CharField('Название группы', max_length=160)
    slug = models.SlugField('Slug', max_length=180, blank=True)
    geo = models.CharField('GEO', max_length=2, blank=True)
    vertical = models.ForeignKey(
        Vertical,
        verbose_name='Вертикаль',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='article_groups',
    )
    description = models.TextField('Описание', blank=True)
    tracker_profile = models.ForeignKey(
        'tracking.TrackerProfile',
        verbose_name='Профиль трекера',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='article_groups',
    )

    class Meta:
        verbose_name = 'Группа статей'
        verbose_name_plural = 'Группы статей'
        ordering = ['name']
        indexes = [
            models.Index(fields=['owner', 'created_at']),
            models.Index(fields=['geo', 'vertical']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:180]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Article(OwnedModel):
    title = models.CharField('Заголовок', max_length=255)
    slug = models.SlugField('Slug', max_length=280, blank=True)
    public_id = models.UUIDField('Публичный ID', default=uuid.uuid4, unique=True, editable=False)
    article_type = models.CharField(
        'Тип статьи',
        max_length=24,
        choices=ArticleType.choices,
        default=ArticleType.INTERNAL,
    )
    category = models.ForeignKey(
        Category,
        verbose_name='Категория',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='articles',
    )
    vertical = models.ForeignKey(
        Vertical,
        verbose_name='Вертикаль',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='articles',
    )
    groups = models.ManyToManyField(
        ArticleGroup,
        verbose_name='Группы статей',
        blank=True,
        related_name='articles',
    )
    tags = models.CharField('Теги', max_length=255, blank=True)
    country = models.CharField('Страна', max_length=2, blank=True)
    language = models.CharField('Язык', max_length=8, blank=True)
    image = models.ImageField('Изображение', upload_to='articles/', blank=True)
    body = CKEditor5Field('Текст статьи', config_name='default', blank=True)
    external_url = models.URLField('Внешний ленд', blank=True)
    html_file = models.FileField('HTML-файл', upload_to='articles/html/', blank=True)
    outbound_mark_enabled = models.BooleanField('Добавлять метку к исходящим ссылкам', default=True)
    outbound_mark_param = models.CharField('Имя UTM/параметра', max_length=80, default='article_id')
    outbound_mark_value_mode = models.CharField(
        'Значение UTM/параметра',
        max_length=24,
        choices=OutboundMarkValueMode.choices,
        default=OutboundMarkValueMode.ARTICLE_ID,
    )
    outbound_mark_custom_value = models.CharField('Свое значение UTM/параметра', max_length=160, blank=True)
    outbound_mark_replace_existing = models.BooleanField('Перезаписывать существующий параметр', default=False)
    tracker_profile = models.ForeignKey(
        'tracking.TrackerProfile',
        verbose_name='Профиль трекера',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='articles',
        help_text='Если пусто, используется профиль первой группы статьи.',
    )
    status = models.CharField(
        'Статус',
        max_length=24,
        choices=ArticleStatus.choices,
        default=ArticleStatus.ACTIVE,
    )

    class Meta:
        verbose_name = 'Статья'
        verbose_name_plural = 'Статьи'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['article_type', 'status']),
            models.Index(fields=['country', 'vertical']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['owner', 'created_at']),
            models.Index(fields=['public_id']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:280]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    def get_public_url(self):
        return reverse('public_article', kwargs={'public_id': self.public_id})

    def get_outbound_mark_value(self):
        if self.outbound_mark_value_mode == OutboundMarkValueMode.PUBLIC_ID:
            return str(self.public_id)
        if self.outbound_mark_value_mode == OutboundMarkValueMode.CUSTOM:
            return self.outbound_mark_custom_value
        return str(self.id)

    def get_tracker_profile(self):
        if self.tracker_profile_id and self.tracker_profile and self.tracker_profile.is_active:
            return self.tracker_profile
        group = self.groups.filter(tracker_profile__isnull=False, tracker_profile__is_active=True).select_related('tracker_profile').first()
        return group.tracker_profile if group else None
