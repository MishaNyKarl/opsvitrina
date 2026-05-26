from django import forms

from articles.models import Article, ArticleGroup, ArticleStatus, Vertical

from .models import BANNER_UTM_PARAM_VALIDATOR, Banner, BannerGroup, BannerSlot, BannerTier


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput(attrs={'multiple': True}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(file_data, initial) for file_data in data]
        return [single_file_clean(data, initial)] if data else []


class BannerUploadForm(forms.Form):
    group_name = forms.CharField(label='Название группы', max_length=160)
    description = forms.CharField(label='Описание', required=False, widget=forms.Textarea(attrs={'rows': 3}))
    target_url = forms.CharField(
        label='Вторая ссылка',
        required=False,
        max_length=2000,
        help_text='Можно использовать шаблоны: {click_id}, {cost}, {ad_name}, {campaign}, {state_id}, {ad_vtr_name} или имя параметра из поля ниже.',
    )
    banner_utm_param = forms.CharField(
        label='Имя UTM-параметра баннера',
        max_length=64,
        initial='ad_vtr_name',
        validators=[BANNER_UTM_PARAM_VALIDATOR],
        help_text='Например: ad_vtr_name. В этот параметр будет подставляться UTM/tracking key баннера.',
    )
    priority = forms.IntegerField(label='Приоритет', min_value=0, max_value=100, initial=50)
    display_tier = forms.ChoiceField(
        label='Эшелон показа',
        choices=BannerTier.choices,
        initial=BannerTier.FIRST,
    )
    excluded_slots = forms.MultipleChoiceField(
        label='Не показывать в слотах',
        required=False,
        choices=BannerSlot.choices,
        widget=forms.CheckboxSelectMultiple,
        help_text='Если ничего не выбрать, баннеры из группы смогут показываться во всех слотах.',
    )
    articles = forms.ModelMultipleChoiceField(
        label='Показывать на статьях',
        required=False,
        queryset=Article.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )
    article_groups = forms.ModelMultipleChoiceField(
        label='Показывать на группах статей',
        required=False,
        queryset=ArticleGroup.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )
    images = MultipleFileField(label='Картинки')
    headlines = forms.CharField(
        label='Заголовки',
        widget=forms.Textarea(attrs={'rows': 6, 'placeholder': 'Один заголовок на строку'}),
    )

    def __init__(self, *args, user=None, article_filter_data=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            articles = Article.objects.visible_for(user).select_related('vertical')
            if article_filter_data:
                query = article_filter_data.get('q')
                status = article_filter_data.get('status')
                country = article_filter_data.get('country')
                vertical = article_filter_data.get('vertical')
                article_group = article_filter_data.get('article_group')
                if query:
                    articles = articles.filter(title__icontains=query)
                if status:
                    articles = articles.filter(status=status)
                if country:
                    articles = articles.filter(country__iexact=country)
                if vertical:
                    articles = articles.filter(vertical=vertical)
                if article_group:
                    articles = articles.filter(groups=article_group)
            self.fields['articles'].queryset = articles.distinct().order_by('title')
            self.fields['article_groups'].queryset = ArticleGroup.objects.visible_for(user)

    def clean_images(self):
        images = self.cleaned_data['images']
        if not images:
            raise forms.ValidationError('Загрузите хотя бы одну картинку.')
        for image in images:
            if not image.content_type.startswith('image/'):
                raise forms.ValidationError('Можно загружать только изображения.')
        return images

    def clean_headlines(self):
        raw_headlines = self.cleaned_data['headlines']
        headlines = []
        seen = set()
        for line in raw_headlines.splitlines():
            headline = line.strip()
            if headline and headline not in seen:
                headlines.append(headline)
                seen.add(headline)
        if not headlines:
            raise forms.ValidationError('Добавьте хотя бы один заголовок.')
        return headlines


class BannerFilterForm(forms.Form):
    q = forms.CharField(label='Поиск', required=False)
    group = forms.ModelChoiceField(label='Группа', required=False, queryset=BannerGroup.objects.none())
    display_tier = forms.ChoiceField(
        label='Эшелон',
        required=False,
        choices=(('', 'Все эшелоны'),) + tuple(BannerTier.choices),
    )
    status = forms.ChoiceField(
        label='Статус',
        required=False,
        choices=(
            ('', 'Все статусы'),
            ('active', 'Активен'),
            ('draft', 'Черновик'),
            ('paused', 'Пауза'),
            ('archived', 'Архив'),
        ),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['group'].queryset = BannerGroup.objects.visible_for(user)


class BannerArticleFilterForm(forms.Form):
    q = forms.CharField(label='Поиск по статьям', required=False)
    article_group = forms.ModelChoiceField(
        label='Группа статей',
        required=False,
        queryset=ArticleGroup.objects.none(),
        empty_label='Все группы',
    )
    status = forms.ChoiceField(
        label='Статус',
        required=False,
        choices=(('', 'Все статусы'),) + tuple(ArticleStatus.choices),
    )
    country = forms.CharField(
        label='GEO',
        required=False,
        max_length=2,
        widget=forms.TextInput(attrs={'placeholder': 'US'}),
    )
    vertical = forms.ModelChoiceField(
        label='Вертикаль',
        required=False,
        queryset=Vertical.objects.none(),
        empty_label='Все вертикали',
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['article_group'].queryset = ArticleGroup.objects.visible_for(user)
            self.fields['vertical'].queryset = Vertical.objects.all()


class BannerGroupForm(forms.ModelForm):
    target_url = forms.CharField(
        label='Рекламная ссылка',
        required=False,
        max_length=2000,
        help_text='Можно использовать шаблоны: {click_id}, {cost}, {ad_name}, {campaign}, {state_id}, {ad_vtr_name} или имя UTM-параметра баннера.',
    )
    excluded_slots = forms.MultipleChoiceField(
        label='Не показывать в слотах',
        required=False,
        choices=BannerSlot.choices,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = BannerGroup
        fields = (
            'name',
            'description',
            'target_url',
            'banner_utm_param',
            'status',
            'excluded_slots',
            'articles',
            'article_groups',
        )
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'articles': forms.CheckboxSelectMultiple,
            'article_groups': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['articles'].queryset = Article.objects.visible_for(user)
            self.fields['article_groups'].queryset = ArticleGroup.objects.visible_for(user)


class BannerForm(forms.ModelForm):
    target_url = forms.CharField(
        label='Вторая ссылка',
        required=False,
        max_length=2000,
        help_text='Можно использовать шаблоны: {click_id}, {cost}, {ad_name}, {campaign}, {state_id}, {ad_vtr_name} или имя UTM-параметра баннера. Если пусто, используется ссылка группы.',
    )

    class Meta:
        model = Banner
        fields = (
            'status',
            'target_url',
            'utm_key',
            'banner_utm_param',
            'priority',
            'display_tier',
        )
        help_texts = {
            'utm_key': 'Эта метка подставится в {ad_vtr_name}.',
            'banner_utm_param': 'Если пусто, используется имя параметра из группы баннеров.',
        }
