from django.conf import settings
from django.db import models


class TimestampedModel(models.Model):
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        abstract = True


class OwnedQuerySet(models.QuerySet):
    def visible_for(self, user):
        if not user or not user.is_authenticated:
            return self.none()
        if user.can_view_all_data:
            return self
        if user.can_view_team_data and user.team_id:
            return self.filter(team_id=user.team_id)
        return self.filter(owner_id=user.id)


class OwnedModel(TimestampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Владелец',
        on_delete=models.PROTECT,
        related_name='%(class)ss',
    )
    team = models.ForeignKey(
        'accounts.Team',
        verbose_name='Команда',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='%(class)ss',
    )

    objects = OwnedQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.owner_id and not self.team_id:
            self.team = self.owner.team
        super().save(*args, **kwargs)
