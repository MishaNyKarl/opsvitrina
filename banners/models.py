from django.db import models
from django.core.validators import RegexValidator

from core.models import OwnedModel


BANNER_UTM_PARAM_VALIDATOR = RegexValidator(
    regex=r'^[A-Za-z_][A-Za-z0-9_.-]*$',
    message='Имя параметра может содержать латинские буквы, цифры, "_", "." и "-", но должно начинаться с буквы или "_".',
)


class BannerStatus(models.TextChoices):
    DRAFT = 'draft', 'Черновик'
    ACTIVE = 'active', 'Активен'
    PAUSED = 'paused', 'Пауза'
    ARCHIVED = 'archived', 'Архив'


class BannerSlot(models.TextChoices):
    TOP_LEFT = 'top_left', 'Верхний левый'
    TOP_RIGHT = 'top_right', 'Верхний правый'
    IN_ARTICLE = 'in_article', 'Внутри статьи'
    SIDEBAR_1 = 'sidebar_1', 'Боковой 1'
    SIDEBAR_2 = 'sidebar_2', 'Боковой 2'
    SIDEBAR_WIDE = 'sidebar_wide', 'Боковой широкий'
    POPUP = 'popup', 'Pop-up'


class BannerTier(models.IntegerChoices):
    FIRST = 1, 'Первый эшелон'
    SECOND = 2, 'Второй эшелон'


class BannerGroup(OwnedModel):
    name = models.CharField('Название группы', max_length=160)
    description = models.TextField('Описание', blank=True)
    target_url = models.URLField('Рекламная ссылка', max_length=2000, blank=True)
    banner_utm_param = models.CharField(
        'Имя UTM-параметра баннера',
        max_length=64,
        default='ad_vtr_name',
        validators=[BANNER_UTM_PARAM_VALIDATOR],
        help_text='Параметр, в который подставляется UTM/tracking key баннера.',
    )
    status = models.CharField(
        'Статус',
        max_length=24,
        choices=BannerStatus.choices,
        default=BannerStatus.ACTIVE,
    )
    slot = models.CharField(
        'Слот показа',
        max_length=32,
        choices=BannerSlot.choices,
        default=BannerSlot.SIDEBAR_1,
    )
    excluded_slots = models.JSONField('Не показывать в слотах', default=list, blank=True)
    articles = models.ManyToManyField(
        'articles.Article',
        verbose_name='Статьи',
        blank=True,
        related_name='banner_groups',
    )
    article_groups = models.ManyToManyField(
        'articles.ArticleGroup',
        verbose_name='Группы статей',
        blank=True,
        related_name='banner_groups',
    )

    class Meta:
        verbose_name = 'Группа баннеров'
        verbose_name_plural = 'Группы баннеров'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', 'created_at']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['slot', 'status']),
        ]

    def __str__(self):
        return self.name

    def can_show_in_slot(self, slot):
        return slot not in (self.excluded_slots or [])


class CreativeImage(OwnedModel):
    group = models.ForeignKey(
        BannerGroup,
        verbose_name='Группа баннеров',
        on_delete=models.CASCADE,
        related_name='images',
    )
    image = models.ImageField('Изображение', upload_to='banners/images/')
    original_name = models.CharField('Имя файла', max_length=255, blank=True)

    class Meta:
        verbose_name = 'Картинка креатива'
        verbose_name_plural = 'Картинки креативов'
        ordering = ['created_at']

    def __str__(self):
        return self.original_name or f'Image #{self.pk}'


class CreativeHeadline(OwnedModel):
    group = models.ForeignKey(
        BannerGroup,
        verbose_name='Группа баннеров',
        on_delete=models.CASCADE,
        related_name='headlines',
    )
    text = models.CharField('Заголовок', max_length=255)

    class Meta:
        verbose_name = 'Заголовок креатива'
        verbose_name_plural = 'Заголовки креативов'
        ordering = ['created_at']

    def __str__(self):
        return self.text


class Banner(OwnedModel):
    group = models.ForeignKey(
        BannerGroup,
        verbose_name='Группа баннеров',
        on_delete=models.CASCADE,
        related_name='banners',
    )
    image = models.ForeignKey(
        CreativeImage,
        verbose_name='Картинка',
        on_delete=models.CASCADE,
        related_name='banners',
    )
    headline = models.ForeignKey(
        CreativeHeadline,
        verbose_name='Заголовок',
        on_delete=models.CASCADE,
        related_name='banners',
    )
    status = models.CharField(
        'Статус',
        max_length=24,
        choices=BannerStatus.choices,
        default=BannerStatus.ACTIVE,
    )
    utm_key = models.CharField('UTM-метка баннера', max_length=120, unique=True)
    banner_utm_param = models.CharField(
        'Имя UTM-параметра баннера',
        max_length=64,
        blank=True,
        validators=[BANNER_UTM_PARAM_VALIDATOR],
        help_text='Если пусто, используется настройка группы.',
    )
    target_url = models.URLField('Вторая ссылка', max_length=2000, blank=True)
    display_tier = models.PositiveSmallIntegerField(
        'Эшелон показа',
        choices=BannerTier.choices,
        default=BannerTier.FIRST,
    )
    priority = models.PositiveSmallIntegerField('Приоритет', default=50)
    impressions = models.PositiveIntegerField('Показы', default=0)
    clicks = models.PositiveIntegerField('Клики', default=0)

    class Meta:
        verbose_name = 'Баннер'
        verbose_name_plural = 'Баннеры'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['group', 'status']),
            models.Index(fields=['owner', 'created_at']),
            models.Index(fields=['priority', 'status']),
            models.Index(fields=['display_tier', 'status']),
        ]

    def __str__(self):
        return f'{self.headline.text[:60]}'

    @property
    def effective_banner_utm_param(self):
        return self.banner_utm_param or self.group.banner_utm_param or 'ad_vtr_name'

    @property
    def ctr(self):
        if not self.impressions:
            return 0
        return round((self.clicks / self.impressions) * 100, 2)


class BannerPlacement(OwnedModel):
    banner = models.ForeignKey(
        Banner,
        verbose_name='Закрепленный баннер',
        on_delete=models.CASCADE,
        related_name='placements',
    )
    article = models.ForeignKey(
        'articles.Article',
        verbose_name='Статья',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='banner_placements',
    )
    article_group = models.ForeignKey(
        'articles.ArticleGroup',
        verbose_name='Группа статей',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='banner_placements',
    )
    slot = models.CharField('Слот', max_length=32, choices=BannerSlot.choices)
    display_tier = models.PositiveSmallIntegerField(
        'Эшелон показа',
        choices=BannerTier.choices,
        default=BannerTier.FIRST,
    )
    is_active = models.BooleanField('Активно', default=True)

    class Meta:
        verbose_name = 'Закрепление баннера'
        verbose_name_plural = 'Закрепления баннеров'
        ordering = ['slot', 'display_tier']
        constraints = [
            models.UniqueConstraint(
                fields=['article', 'slot', 'display_tier'],
                condition=models.Q(article__isnull=False),
                name='unique_article_banner_placement',
            ),
            models.UniqueConstraint(
                fields=['article_group', 'slot', 'display_tier'],
                condition=models.Q(article_group__isnull=False),
                name='unique_article_group_banner_placement',
            ),
        ]
        indexes = [
            models.Index(fields=['article', 'slot', 'display_tier']),
            models.Index(fields=['article_group', 'slot', 'display_tier']),
            models.Index(fields=['banner', 'is_active']),
        ]

    def __str__(self):
        target = self.article or self.article_group
        return f'{target}: {self.slot} / {self.get_display_tier_display()}'
