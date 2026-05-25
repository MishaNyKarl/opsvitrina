from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import render

from articles.models import Article
from flows.models import Flow
from tracking.models import EventType, PostbackEvent, VisitEvent


@login_required
def dashboard(request):
    articles = Article.objects.visible_for(request.user)
    flows = Flow.objects.visible_for(request.user)
    visits = VisitEvent.objects.visible_for(request.user)
    postbacks = PostbackEvent.objects.visible_for(request.user)

    context = {
        'page_title': 'Статистика',
        'article_count': articles.count(),
        'flow_count': flows.count(),
        'click_count': visits.filter(event_type=EventType.CLICK).count(),
        'pageview_count': visits.filter(event_type=EventType.PAGEVIEW).count(),
        'lead_count': postbacks.count(),
        'payout_total': postbacks.aggregate(total=Sum('payout'))['total'] or 0,
        'recent_flows': flows.select_related('article', 'owner')[:5],
        'status_rows': postbacks.values('status').annotate(count=Count('id'), payout=Sum('payout')).order_by('status'),
    }
    return render(request, 'core/dashboard.html', context)
