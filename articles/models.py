import uuid

from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django_ckeditor_5.fields import CKEditor5Field

from core.models import OwnedModel, TimestampedModel


TRACKING_PARAM_VALIDATOR = RegexValidator(
    regex=r'^[A-Za-z_][A-Za-z0-9_.-]*$',
    message='Имя параметра может содержать латинские буквы, цифры, "_", "." и "-", но должно начинаться с буквы или "_".',
)


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


class ArticleUiLanguage(models.TextChoices):
    RU = 'ru', 'Русский'
    EN = 'en', 'English'
    FR = 'fr', 'Français'
    PT = 'pt', 'Português'
    ES = 'es', 'Español'


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
    public_id = models.UUIDField('Публичный ID', default=uuid.uuid4, unique=True, editable=False)
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
    ui_language = models.CharField(
        'Язык интерфейса витрины',
        max_length=8,
        choices=ArticleUiLanguage.choices,
        default=ArticleUiLanguage.RU,
        help_text='Язык кнопок и служебных текстов на публичных статьях этой группы.',
    )
    tracker_profile = models.ForeignKey(
        'tracking.TrackerProfile',
        verbose_name='Профиль трекера',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='article_groups',
    )
    next_article_groups = models.ManyToManyField(
        'self',
        verbose_name='Группы для блока "Другие статьи"',
        blank=True,
        symmetrical=False,
        related_name='used_as_next_feed_for',
        help_text='Если пусто, в нижней ленте используются статьи из этой группы.',
    )
    status = models.CharField(
        'Статус',
        max_length=24,
        choices=ArticleStatus.choices,
        default=ArticleStatus.ACTIVE,
    )

    class Meta:
        verbose_name = 'Группа статей'
        verbose_name_plural = 'Группы статей'
        ordering = ['name']
        indexes = [
            models.Index(fields=['owner', 'created_at']),
            models.Index(fields=['geo', 'vertical']),
            models.Index(fields=['status', 'created_at']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:180]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_public_url(self):
        return reverse('public_article_group', kwargs={'public_id': self.public_id})


class ArticleGroupMembership(TimestampedModel):
    group = models.ForeignKey(
        ArticleGroup,
        verbose_name='Группа статей',
        on_delete=models.CASCADE,
        related_name='memberships',
    )
    article = models.ForeignKey(
        'Article',
        verbose_name='Статья',
        on_delete=models.CASCADE,
        related_name='group_memberships',
    )
    priority = models.PositiveIntegerField('Приоритет', default=50)
    utm_query = models.CharField('UTM для этой статьи', max_length=500, blank=True)
    is_active = models.BooleanField('Активна в группе', default=True)
    impressions = models.PositiveIntegerField('Показы из группы', default=0)

    class Meta:
        verbose_name = 'Статья в группе'
        verbose_name_plural = 'Статьи в группах'
        ordering = ['group', 'article']
        constraints = [
            models.UniqueConstraint(fields=['group', 'article'], name='unique_article_group_membership'),
        ]
        indexes = [
            models.Index(fields=['group', 'is_active', 'priority']),
            models.Index(fields=['article', 'group']),
        ]

    def __str__(self):
        return f'{self.group} / {self.article}'


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
    next_article_groups = models.ManyToManyField(
        ArticleGroup,
        verbose_name='Группы для нижней ленты',
        blank=True,
        related_name='next_feed_articles',
        help_text='Если пусто, используются настройки группы входа или группы самой статьи.',
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
    article_utm_key = models.CharField(
        'UTM-метка статьи',
        max_length=120,
        blank=True,
        help_text='Эта метка подставляется в ad_vtr_name и выбранный UTM-параметр статьи.',
    )
    article_utm_param = models.CharField(
        'Имя UTM-параметра статьи',
        max_length=80,
        default='article_name',
        validators=[TRACKING_PARAM_VALIDATOR],
        help_text='Например: article_name. В этот параметр будет подставляться UTM-метка статьи.',
    )
    engagement_event_enabled = models.BooleanField(
        'Отправлять событие вовлеченного клика',
        default=False,
        help_text='Срабатывает один раз: больше 60 секунд на статье, скролл 25%+ и клик по баннеру или следующей статье.',
    )
    engagement_event_param = models.CharField(
        'Параметр события в трекере',
        max_length=80,
        default='event30',
        validators=[TRACKING_PARAM_VALIDATOR],
        help_text='Например event30. Этот параметр будет отправлен в профиль трекера.',
    )
    engagement_event_value = models.CharField('Значение события', max_length=80, default='1')
    engagement_tracker_url = models.URLField(
        'Ссылка трекера для события вовлеченности',
        max_length=2000,
        blank=True,
        help_text='Если заполнено, событие вовлеченности отправляется сюда. Если пусто, используется ссылка из профиля трекера.',
    )
    engagement_utm_param = models.CharField(
        'UTM-параметр для клика',
        max_length=80,
        blank=True,
        default='utm_content',
        validators=[TRACKING_PARAM_VALIDATOR],
        help_text='Будет добавлен к URL баннера или следующей статьи при срабатывании события. Оставьте пустым, если метка не нужна.',
    )
    engagement_utm_value = models.CharField('UTM-значение для клика', max_length=160, blank=True, default='engaged_click')
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

    @property
    def effective_article_utm_key(self):
        return self.article_utm_key or f'article_{self.id}'

    @property
    def effective_article_utm_param(self):
        return self.article_utm_param or 'article_name'

    def get_tracker_profile(self):
        if self.tracker_profile_id and self.tracker_profile and self.tracker_profile.is_active:
            return self.tracker_profile
        group = self.groups.filter(tracker_profile__isnull=False, tracker_profile__is_active=True).select_related('tracker_profile').first()
        return group.tracker_profile if group else None
