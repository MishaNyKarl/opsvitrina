from django import forms

from articles.models import Article

from .models import Domain, Flow, TrafficSource


class FlowForm(forms.ModelForm):
    class Meta:
        model = Flow
        fields = (
            'name',
            'article',
            'domain',
            'traffic_source',
            'design',
            'status',
            'no_redirect',
            'collect_push_base',
            'show_back_button',
            'show_popup',
            'analytics_enabled',
        )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['article'].queryset = Article.objects.visible_for(user)
        self.fields['domain'].queryset = Domain.objects.filter(is_active=True)
        self.fields['traffic_source'].queryset = TrafficSource.objects.all()
