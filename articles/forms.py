from django import forms

from tracking.models import TrackerProfile

from .models import Article, ArticleGroup, ArticleGroupMembership, ArticleStatus, ArticleType, OutboundMarkValueMode


class ArticleForm(forms.ModelForm):
    article_groups = forms.ModelMultipleChoiceField(
        label='Группы статей',
        required=False,
        queryset=ArticleGroup.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        help_text='Статья может входить в несколько групп. Группы нужны для общих ссылок, ротации и правил показа.',
    )
    new_article_group = forms.CharField(
        label='Создать новую группу статей',
        required=False,
        max_length=160,
        help_text='Заполните это поле, если нужной группы ещё нет.',
    )

    class Meta:
        model = Article
        fields = (
            'title',
            'article_type',
            'category',
            'vertical',
            'article_groups',
            'new_article_group',
            'next_article_groups',
            'tags',
            'country',
            'language',
            'image',
            'body',
            'external_url',
            'html_file',
            'outbound_mark_enabled',
            'outbound_mark_param',
            'outbound_mark_value_mode',
            'outbound_mark_custom_value',
            'outbound_mark_replace_existing',
            'engagement_event_enabled',
            'engagement_event_param',
            'engagement_event_value',
            'engagement_utm_param',
            'engagement_utm_value',
            'tracker_profile',
            'status',
        )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].initial = ArticleStatus.ACTIVE
        if user is not None:
            self.fields['article_groups'].queryset = ArticleGroup.objects.visible_for(user)
            self.fields['next_article_groups'].queryset = ArticleGroup.objects.visible_for(user)
            self.fields['tracker_profile'].queryset = TrackerProfile.objects.visible_for(user).filter(is_active=True)
        if self.instance and self.instance.pk:
            self.fields['article_groups'].initial = self.instance.groups.all()

    def clean(self):
        cleaned_data = super().clean()
        article_type = cleaned_data.get('article_type')
        body = cleaned_data.get('body')
        external_url = cleaned_data.get('external_url')
        html_file = cleaned_data.get('html_file')
        article_groups = cleaned_data.get('article_groups')
        new_article_group = (cleaned_data.get('new_article_group') or '').strip()

        if article_groups and new_article_group:
            self.add_error('new_article_group', 'Выберите существующие группы или создайте новую, не оба варианта сразу.')
        if article_type == ArticleType.INTERNAL and not body:
            self.add_error('body', 'Для статьи на платформе нужно заполнить текст.')
        if article_type == ArticleType.EXTERNAL and not external_url:
            self.add_error('external_url', 'Для внешнего ленда нужно указать ссылку.')
        if article_type == ArticleType.HTML and not html_file:
            self.add_error('html_file', 'Для HTML-статьи нужно загрузить .html файл.')
        if html_file and not html_file.name.lower().endswith(('.html', '.htm')):
            self.add_error('html_file', 'Загрузите файл с расширением .html или .htm.')
        if cleaned_data.get('outbound_mark_enabled') and not cleaned_data.get('outbound_mark_param'):
            self.add_error('outbound_mark_param', 'Укажите имя параметра для исходящих ссылок.')
        if (
            cleaned_data.get('outbound_mark_enabled')
            and cleaned_data.get('outbound_mark_value_mode') == OutboundMarkValueMode.CUSTOM
            and not cleaned_data.get('outbound_mark_custom_value')
        ):
            self.add_error('outbound_mark_custom_value', 'Укажите свое значение параметра.')
        if cleaned_data.get('engagement_event_enabled'):
            if not cleaned_data.get('engagement_event_param'):
                self.add_error('engagement_event_param', 'Укажите параметр события для трекера.')
            if not cleaned_data.get('engagement_event_value'):
                self.add_error('engagement_event_value', 'Укажите значение события.')
            if cleaned_data.get('engagement_utm_param') and not cleaned_data.get('engagement_utm_value'):
                self.add_error('engagement_utm_value', 'Укажите значение UTM-метки или очистите имя UTM-параметра.')

        return cleaned_data

    def save_article_group(self, article, user):
        new_group_name = (self.cleaned_data.get('new_article_group') or '').strip()
        selected_groups = list(self.cleaned_data.get('article_groups') or [])

        if new_group_name:
            selected_groups = [ArticleGroup.objects.create(
                owner=user,
                team=user.team,
                name=new_group_name,
                geo=article.country,
                vertical=article.vertical,
            )]

        article.groups.set(selected_groups)
        if selected_groups:
            selected_group_ids = [group.id for group in selected_groups]
            for selected_group in selected_groups:
                ArticleGroupMembership.objects.get_or_create(
                    group=selected_group,
                    article=article,
                    defaults={
                        'priority': 50,
                        'utm_query': '',
                        'is_active': True,
                    },
                )
            ArticleGroupMembership.objects.filter(article=article).exclude(group_id__in=selected_group_ids).delete()
        else:
            ArticleGroupMembership.objects.filter(article=article).delete()
        return selected_groups


class ArticleGroupForm(forms.ModelForm):
    class Meta:
        model = ArticleGroup
        fields = (
            'name',
            'geo',
            'vertical',
            'description',
            'ui_language',
            'tracker_profile',
            'next_article_groups',
            'status',
        )
        help_texts = {
            'next_article_groups': 'Из этих групп будут подбираться карточки в нижнем блоке "Другие статьи". Если пусто, используется сама группа.',
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'next_article_groups': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['tracker_profile'].queryset = TrackerProfile.objects.visible_for(user).filter(is_active=True)
            self.fields['next_article_groups'].queryset = ArticleGroup.objects.visible_for(user)
