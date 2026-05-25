from django import forms

from .models import TrackerProfile, default_tracker_events


class TrackerProfileForm(forms.ModelForm):
    pageview_event = forms.CharField(label='Загрузка статьи', required=False, max_length=80)
    time_10s_event = forms.CharField(label='10 секунд на статье', required=False, max_length=80)
    time_30s_event = forms.CharField(label='30 секунд на статье', required=False, max_length=80)
    time_60s_event = forms.CharField(label='60 секунд на статье', required=False, max_length=80)
    scroll_25_event = forms.CharField(label='Скролл 25%', required=False, max_length=80)
    scroll_50_event = forms.CharField(label='Скролл 50%', required=False, max_length=80)
    scroll_75_event = forms.CharField(label='Скролл 75%', required=False, max_length=80)
    any_click_event = forms.CharField(label='Любой клик', required=False, max_length=80)

    class Meta:
        model = TrackerProfile
        fields = (
            'name',
            'endpoint_url',
            'inbound_click_id_param',
            'update_click_id_param',
            'event_value',
            'is_active',
        )
        help_texts = {
            'endpoint_url': 'Например: https://lifestoryhub.net/click',
            'inbound_click_id_param': 'Имя параметра, с которым clickid приходит на статью.',
            'update_click_id_param': 'Имя параметра, с которым clickid отправляется в трекер.',
            'event_value': 'Обычно 1.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        events = default_tracker_events()
        if self.instance and self.instance.pk:
            events.update(self.instance.event_params or {})
        for key, value in events.items():
            field_name = f'{key}_event'
            if field_name in self.fields:
                self.fields[field_name].initial = value

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.event_params = {
            'pageview': self.cleaned_data.get('pageview_event') or '',
            'time_10s': self.cleaned_data.get('time_10s_event') or '',
            'time_30s': self.cleaned_data.get('time_30s_event') or '',
            'time_60s': self.cleaned_data.get('time_60s_event') or '',
            'scroll_25': self.cleaned_data.get('scroll_25_event') or '',
            'scroll_50': self.cleaned_data.get('scroll_50_event') or '',
            'scroll_75': self.cleaned_data.get('scroll_75_event') or '',
            'any_click': self.cleaned_data.get('any_click_event') or '',
        }
        if commit:
            instance.save()
            self.save_m2m()
        return instance
