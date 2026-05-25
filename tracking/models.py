from django.db import models

from core.models import OwnedModel


def default_tracker_events():
    return {
        'pageview': 'event10',
        'time_10s': 'event11',
        'time_30s': 'event12',
        'time_60s': 'event13',
        'scroll_25': 'event14',
        'scroll_50': 'event15',
        'scroll_75': 'event16',
        'any_click': 'event20',
    }


class TrackerProfile(OwnedModel):
    name = models.CharField('Название профиля', max_length=160)
    endpoint_url = models.URLField('Ссылка трекера', max_length=2000)
    inbound_click_id_param = models.CharField(
        'Параметр clickid во входящей ссылке',
        max_length=80,
        default='clickid',
    )
    update_click_id_param = models.CharField(
        'Параметр clickid для отправки в трекер',
        max_length=80,
        default='upd_clickid',
    )
    event_value = models.CharField('Значение события', max_length=40, default='1')
    event_params = models.JSONField('Параметры событий', default=default_tracker_events, blank=True)
    is_active = models.BooleanField('Активен', default=True)

    class Meta:
        verbose_name = 'Профиль трекера'
        verbose_name_plural = 'Профили трекеров'
        ordering = ['name']
        indexes = [
            models.Index(fields=['owner', 'created_at']),
            models.Index(fields=['is_active', 'created_at']),
        ]

    def __str__(self):
        return self.name

    def frontend_config(self):
        return {
            'endpointUrl': self.endpoint_url,
            'inboundClickIdParam': self.inbound_click_id_param,
            'updateClickIdParam': self.update_click_id_param,
            'eventValue': self.event_value,
            'eventParams': self.event_params or default_tracker_events(),
        }


class EventType(models.TextChoices):
    CLICK = 'click', 'Клик'
    PAGEVIEW = 'pageview', 'Просмотр'


class ConversionStatus(models.TextChoices):
    NEW = 'new', 'Новый'
    APPROVED = 'approved', 'Апрув'
    REJECTED = 'rejected', 'Отклонен'
    HOLD = 'hold', 'Холд'


class ArticleBehaviorEvent(OwnedModel):
    article = models.ForeignKey(
        'articles.Article',
        verbose_name='Статья',
        on_delete=models.PROTECT,
        related_name='behavior_events',
    )
    event_type = models.CharField('Тип события', max_length=40, db_index=True)
    session_id = models.CharField('Session ID', max_length=80, blank=True, db_index=True)
    click_id = models.CharField('Click ID из трекера', max_length=255, blank=True, db_index=True)
    target_url = models.URLField('Целевая ссылка', blank=True)
    page_url = models.URLField('URL страницы', blank=True)
    referrer = models.URLField('Referrer', blank=True)
    scroll_depth = models.PositiveSmallIntegerField('Глубина скролла, %', default=0)
    time_on_page = models.PositiveIntegerField('Время на странице, сек.', default=0)
    query_params = models.JSONField('Параметры входа', default=dict, blank=True)
    payload = models.JSONField('Payload', default=dict, blank=True)
    ip_address = models.GenericIPAddressField('IP', null=True, blank=True)
    user_agent = models.TextField('User-Agent', blank=True)

    class Meta:
        verbose_name = 'Поведенческое событие статьи'
        verbose_name_plural = 'Поведенческие события статей'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['article', 'event_type', 'created_at']),
            models.Index(fields=['owner', 'created_at']),
            models.Index(fields=['session_id', 'created_at']),
        ]

    def __str__(self):
        return f'{self.article_id}: {self.event_type}'


class VisitEvent(OwnedModel):
    flow = models.ForeignKey(
        'flows.Flow',
        verbose_name='Поток',
        on_delete=models.PROTECT,
        related_name='visit_events',
    )
    article = models.ForeignKey(
        'articles.Article',
        verbose_name='Статья',
        on_delete=models.PROTECT,
        related_name='visit_events',
    )
    event_type = models.CharField('Тип события', max_length=24, choices=EventType.choices)
    click_id = models.CharField('Click ID из трекера', max_length=255, blank=True, db_index=True)
    query_params = models.JSONField('Параметры перехода', default=dict, blank=True)
    ip_address = models.GenericIPAddressField('IP', null=True, blank=True)
    user_agent = models.TextField('User-Agent', blank=True)

    class Meta:
        verbose_name = 'Событие визита'
        verbose_name_plural = 'События визитов'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['flow', 'event_type', 'created_at']),
            models.Index(fields=['owner', 'created_at']),
        ]

    def __str__(self):
        return f'{self.event_type}: {self.flow_id}'


class PostbackEvent(OwnedModel):
    flow = models.ForeignKey(
        'flows.Flow',
        verbose_name='Поток',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='postback_events',
    )
    click_id = models.CharField('Click ID', max_length=255, db_index=True)
    partner = models.CharField('Партнерская программа', max_length=120, blank=True)
    status = models.CharField(
        'Статус',
        max_length=24,
        choices=ConversionStatus.choices,
        default=ConversionStatus.NEW,
    )
    payout = models.DecimalField('Выплата', max_digits=12, decimal_places=2, default=0)
    currency = models.CharField('Валюта', max_length=8, default='USD')
    raw_payload = models.JSONField('Raw payload', default=dict, blank=True)

    class Meta:
        verbose_name = 'Postback'
        verbose_name_plural = 'Postback'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['click_id', 'created_at']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['owner', 'created_at']),
        ]

    def __str__(self):
        return f'{self.click_id}: {self.status}'
