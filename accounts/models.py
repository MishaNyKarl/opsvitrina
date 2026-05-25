from django.contrib.auth.models import AbstractUser
from django.db import models


class UserRole(models.TextChoices):
    ADMIN = 'admin', 'Администратор'
    MANAGER = 'manager', 'Менеджер'
    BUYER = 'buyer', 'Баер'
    ANALYST = 'analyst', 'Аналитик'


class Team(models.Model):
    name = models.CharField('Название', max_length=120, unique=True)
    is_active = models.BooleanField('Активна', default=True)
    created_at = models.DateTimeField('Создана', auto_now_add=True)

    class Meta:
        verbose_name = 'Команда'
        verbose_name_plural = 'Команды'
        ordering = ['name']

    def __str__(self):
        return self.name


class User(AbstractUser):
    role = models.CharField(
        'Роль',
        max_length=24,
        choices=UserRole.choices,
        default=UserRole.BUYER,
    )
    team = models.ForeignKey(
        Team,
        verbose_name='Команда',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
    )

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    @property
    def can_view_all_data(self):
        return self.is_superuser or self.role == UserRole.ADMIN

    @property
    def can_view_team_data(self):
        return self.can_view_all_data or self.role in {UserRole.MANAGER, UserRole.ANALYST}
