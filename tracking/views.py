import csv

from django.contrib.auth import get_user_model
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.db.models import Avg, Count, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date
from django.utils.timezone import make_aware
from django.views.decorators.http import require_POST
from datetime import datetime, time

from articles.models import Article, ArticleGroup, Vertical
from banners.models import Banner, BannerGroup
from .forms import TrackerProfileForm
from .models import ArticleBehaviorEvent, EventType, PostbackEvent, TrackerProfile, VisitEvent


ARTICLE_SORTS = {
    'title',
    '-title',
    'name',
    '-name',
    'pageviews',
    '-pageviews',
    'outbound_clicks',
    '-outbound_clicks',
    'banner_clicks',
    '-banner_clicks',
    'internal_clicks',
    '-internal_clicks',
    'engagement_clicks',
    '-engagement_clicks',
    'avg_scroll',
    '-avg_scroll',
    'avg_time',
    '-avg_time',
}

BANNER_SORTS = {
    'id',
    '-id',
    'group__name',
    '-group__name',
    'impressions',
    '-impressions',
    'clicks',
    '-clicks',
    'priority',
    '-priority',
    'display_tier',
    '-display_tier',
}


@login_required
def tracker_profile_list(request):
    profiles = TrackerProfile.objects.visible_for(request.user)
    return render(request, 'tracking/tracker_profile_list.html', {
        'page_title': 'Профили трекеров',
        'profiles': profiles,
    })


@login_required
def tracker_profile_create(request):
    if request.method == 'POST':
        form = TrackerProfileForm(request.POST)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.owner = request.user
            profile.team = request.user.team
            profile.save()
            messages.success(request, 'Профиль трекера создан.')
            return redirect('tracking:tracker_profiles')
    else:
        form = TrackerProfileForm()

    return render(request, 'tracking/tracker_profile_form.html', {
        'page_title': 'Новый профиль трекера',
        'form': form,
        'profile': None,
    })


@login_required
def tracker_profile_update(request, pk):
    profile = get_object_or_404(TrackerProfile.objects.visible_for(request.user), pk=pk)
    if request.method == 'POST':
        form = TrackerProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль трекера обновлён.')
            return redirect('tracking:tracker_profiles')
    else:
        form = TrackerProfileForm(instance=profile)

    return render(request, 'tracking/tracker_profile_form.html', {
        'page_title': 'Редактирование трекера',
        'form': form,
        'profile': profile,
    })


@login_required
@require_POST
def tracker_profile_delete(request, pk):
    profile = get_object_or_404(TrackerProfile.objects.visible_for(request.user), pk=pk)
    name = profile.name
    profile.delete()
    messages.success(request, f'Профиль трекера “{name}” удалён.')
    return redirect('tracking:tracker_profiles')


def _date_range(request):
    date_from = parse_date(request.GET.get('date_from', '').strip())
    date_to = parse_date(request.GET.get('date_to', '').strip())
    start = make_aware(datetime.combine(date_from, time.min)) if date_from else None
    end = make_aware(datetime.combine(date_to, time.max)) if date_to else None
    return date_from, date_to, start, end


def _pct(part, total):
    return round((part / total) * 100, 2) if total else 0


def _int(value):
    return int(value or 0)


def _float(value):
    return round(float(value or 0), 2)


def _filtered_events(request):
    events = (
        ArticleBehaviorEvent.objects
        .visible_for(request.user)
        .select_related('article', 'article__vertical', 'owner')
        .prefetch_related('article__groups')
    )
    _date_from, _date_to, start, end = _date_range(request)
    if start:
        events = events.filter(created_at__gte=start)
    if end:
        events = events.filter(created_at__lte=end)

    article_id = request.GET.get('article', '').strip()
    article_group_id = request.GET.get('article_group', '').strip()
    vertical_id = request.GET.get('vertical', '').strip()
    geo = request.GET.get('geo', '').strip()
    buyer_id = request.GET.get('buyer', '').strip()
    source = request.GET.get('source', '').strip()

    if article_id:
        events = events.filter(article_id=article_id)
    if article_group_id:
        events = events.filter(article__groups__id=article_group_id)
    if vertical_id:
        events = events.filter(article__vertical_id=vertical_id)
    if geo:
        events = events.filter(article__country__iexact=geo)
    if buyer_id:
        events = events.filter(owner_id=buyer_id)
    if source:
        events = events.filter(
            models.Q(query_params__utm_source=source)
            | models.Q(query_params__source=source)
            | models.Q(query_params__traffic_source=source)
        )
    return events.distinct()


def _filtered_banners(request):
    banners = Banner.objects.visible_for(request.user).select_related('group', 'headline', 'image', 'owner')
    banner_group_id = request.GET.get('banner_group', '').strip()
    banner_status = request.GET.get('banner_status', '').strip()
    banner_tier = request.GET.get('banner_tier', '').strip()
    banner_id = request.GET.get('banner', '').strip()
    buyer_id = request.GET.get('buyer', '').strip()

    if banner_group_id:
        banners = banners.filter(group_id=banner_group_id)
    if banner_status:
        banners = banners.filter(status=banner_status)
    if banner_tier:
        banners = banners.filter(display_tier=banner_tier)
    if banner_id:
        banners = banners.filter(id=banner_id)
    if buyer_id:
        banners = banners.filter(owner_id=buyer_id)
    return banners


def _article_rows(events, sort):
    rows = list(
        events.values(
            'article_id',
            'article__title',
            'article__country',
            'article__vertical__name',
            'owner__username',
        ).annotate(
            pageviews=Count('id', filter=models.Q(event_type='pageview')),
            clicks=Count('id', filter=models.Q(event_type='click')),
            outbound_clicks=Count('id', filter=models.Q(event_type='outbound_click')),
            banner_clicks=Count('id', filter=models.Q(event_type='outbound_click', target_url__icontains='/banners/')),
            internal_clicks=Count('id', filter=models.Q(event_type='outbound_click', target_url__icontains='internal_source=next_feed')),
            engagement_clicks=Count('id', filter=models.Q(event_type='engagement_click')),
            events=Count('id'),
            sessions=Count('session_id', distinct=True),
            avg_scroll=Avg('scroll_depth'),
            avg_time=Avg('time_on_page'),
        )
    )
    normalized = []
    for row in rows:
        pageviews = _int(row['pageviews'])
        outbound_clicks = _int(row['outbound_clicks'])
        banner_clicks = _int(row['banner_clicks'])
        internal_clicks = _int(row['internal_clicks'])
        normalized.append({
            'article_id': row['article_id'],
            'title': row['article__title'],
            'geo': row['article__country'] or '-',
            'vertical': row['article__vertical__name'] or '-',
            'buyer': row['owner__username'] or '-',
            'pageviews': pageviews,
            'clicks': _int(row['clicks']),
            'outbound_clicks': outbound_clicks,
            'banner_clicks': banner_clicks,
            'internal_clicks': internal_clicks,
            'engagement_clicks': _int(row['engagement_clicks']),
            'events': _int(row['events']),
            'sessions': _int(row['sessions']),
            'avg_scroll': _float(row['avg_scroll']),
            'avg_time': _float(row['avg_time']),
            'outbound_ctr': _pct(outbound_clicks, pageviews),
            'banner_ctr': _pct(banner_clicks, pageviews),
            'internal_ctr': _pct(internal_clicks, pageviews),
        })
    return _sort_rows(normalized, sort, '-pageviews')


def _article_group_rows(events, sort):
    rows = []
    # Build groups from the filtered event set so empty unrelated groups do not clutter the table.
    group_ids = list(events.values_list('article__groups__id', flat=True).exclude(article__groups__id__isnull=True).distinct())
    groups = ArticleGroup.objects.filter(id__in=group_ids).select_related('vertical')
    for group in groups:
        group_events = events.filter(article__groups=group)
        aggregate = group_events.aggregate(
            pageviews=Count('id', filter=models.Q(event_type='pageview')),
            clicks=Count('id', filter=models.Q(event_type='click')),
            outbound_clicks=Count('id', filter=models.Q(event_type='outbound_click')),
            banner_clicks=Count('id', filter=models.Q(event_type='outbound_click', target_url__icontains='/banners/')),
            internal_clicks=Count('id', filter=models.Q(event_type='outbound_click', target_url__icontains='internal_source=next_feed')),
            engagement_clicks=Count('id', filter=models.Q(event_type='engagement_click')),
            events=Count('id'),
            sessions=Count('session_id', distinct=True),
            avg_scroll=Avg('scroll_depth'),
            avg_time=Avg('time_on_page'),
        )
        pageviews = _int(aggregate['pageviews'])
        outbound_clicks = _int(aggregate['outbound_clicks'])
        banner_clicks = _int(aggregate['banner_clicks'])
        internal_clicks = _int(aggregate['internal_clicks'])
        rows.append({
            'group_id': group.id,
            'name': group.name,
            'geo': group.geo or '-',
            'vertical': group.vertical.name if group.vertical else '-',
            'articles_count': group.articles.count(),
            'pageviews': pageviews,
            'clicks': _int(aggregate['clicks']),
            'outbound_clicks': outbound_clicks,
            'banner_clicks': banner_clicks,
            'internal_clicks': internal_clicks,
            'engagement_clicks': _int(aggregate['engagement_clicks']),
            'events': _int(aggregate['events']),
            'sessions': _int(aggregate['sessions']),
            'avg_scroll': _float(aggregate['avg_scroll']),
            'avg_time': _float(aggregate['avg_time']),
            'outbound_ctr': _pct(outbound_clicks, pageviews),
            'banner_ctr': _pct(banner_clicks, pageviews),
            'internal_ctr': _pct(internal_clicks, pageviews),
        })
    return _sort_rows(rows, sort, '-pageviews')


def _sort_rows(rows, sort, default_sort):
    sort = sort if sort in ARTICLE_SORTS else default_sort
    reverse = sort.startswith('-')
    key = sort[1:] if reverse else sort
    aliases = {'title': 'title'}
    key = aliases.get(key, key)
    return sorted(rows, key=lambda row: row.get(key) or 0, reverse=reverse)


def _banner_rows(banners, sort):
    if sort not in BANNER_SORTS and sort not in {'ctr', '-ctr'}:
        sort = '-impressions'
    rows = list(banners)
    if sort in {'ctr', '-ctr'}:
        rows.sort(key=lambda banner: banner.ctr, reverse=sort.startswith('-'))
    else:
        rows = list(banners.order_by(sort))
    return rows, sort


def _banner_group_rows(banners):
    return (
        banners
        .values('group_id', 'group__name')
        .annotate(
            banners_count=Count('id'),
            impressions=Sum('impressions'),
            clicks=Sum('clicks'),
        )
        .order_by('group__name')
    )


def _filter_context(request):
    User = get_user_model()
    return {
        'filters': {
            'date_from': request.GET.get('date_from', ''),
            'date_to': request.GET.get('date_to', ''),
            'geo': request.GET.get('geo', ''),
            'source': request.GET.get('source', ''),
            'article_id': request.GET.get('article', ''),
            'article_group_id': request.GET.get('article_group', ''),
            'vertical_id': request.GET.get('vertical', ''),
            'banner_group_id': request.GET.get('banner_group', ''),
            'banner_id': request.GET.get('banner', ''),
            'buyer_id': request.GET.get('buyer', ''),
        },
        'filter_articles': Article.objects.visible_for(request.user).order_by('title'),
        'filter_article_groups': ArticleGroup.objects.visible_for(request.user).order_by('name'),
        'filter_verticals': Vertical.objects.order_by('name'),
        'filter_banner_groups': BannerGroup.objects.visible_for(request.user).order_by('name'),
        'filter_banners': Banner.objects.visible_for(request.user).select_related('headline').order_by('headline__text'),
        'filter_buyers': User.objects.filter(models.Q(articles__isnull=False) | models.Q(banners__isnull=False)).distinct().order_by('username'),
    }


def _csv_response(filename, headers, rows):
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return response


def _export(request, article_rows, article_group_rows, banner_rows):
    export_type = request.GET.get('export', '').strip()
    if export_type == 'articles':
        return _csv_response(
            'article_stats.csv',
            ['ID', 'Article', 'GEO', 'Vertical', 'Buyer', 'Pageviews', 'Clicks', 'Outbound clicks', 'Outbound CTR', 'Banner clicks', 'Banner CTR', 'Internal clicks', 'Internal CTR', 'Engagement clicks', 'Events', 'Sessions', 'Avg scroll', 'Avg time'],
            [
                [row['article_id'], row['title'], row['geo'], row['vertical'], row['buyer'], row['pageviews'], row['clicks'], row['outbound_clicks'], row['outbound_ctr'], row['banner_clicks'], row['banner_ctr'], row['internal_clicks'], row['internal_ctr'], row['engagement_clicks'], row['events'], row['sessions'], row['avg_scroll'], row['avg_time']]
                for row in article_rows
            ],
        )
    if export_type == 'article_groups':
        return _csv_response(
            'article_group_stats.csv',
            ['ID', 'Group', 'GEO', 'Vertical', 'Articles', 'Pageviews', 'Clicks', 'Outbound clicks', 'Outbound CTR', 'Banner clicks', 'Banner CTR', 'Internal clicks', 'Internal CTR', 'Engagement clicks', 'Events', 'Sessions', 'Avg scroll', 'Avg time'],
            [
                [row['group_id'], row['name'], row['geo'], row['vertical'], row['articles_count'], row['pageviews'], row['clicks'], row['outbound_clicks'], row['outbound_ctr'], row['banner_clicks'], row['banner_ctr'], row['internal_clicks'], row['internal_ctr'], row['engagement_clicks'], row['events'], row['sessions'], row['avg_scroll'], row['avg_time']]
                for row in article_group_rows
            ],
        )
    if export_type == 'banners':
        return _csv_response(
            'banner_stats.csv',
            ['ID', 'Headline', 'Group', 'Impressions', 'Clicks', 'CTR', 'Priority', 'Tier', 'Status'],
            [
                [banner.id, banner.headline.text, banner.group.name, banner.impressions, banner.clicks, banner.ctr, banner.priority, banner.get_display_tier_display(), banner.get_status_display()]
                for banner in banner_rows
            ],
        )
    return None


@login_required
def stats(request):
    visits = VisitEvent.objects.visible_for(request.user).select_related('flow', 'article')
    postbacks = PostbackEvent.objects.visible_for(request.user).select_related('flow')

    flow_id = request.GET.get('flow', '').strip()
    if flow_id:
        visits = visits.filter(flow_id=flow_id)
        postbacks = postbacks.filter(flow_id=flow_id)

    flow_rows = visits.values('flow_id', 'flow__name').annotate(
        clicks=Count('id', filter=models.Q(event_type=EventType.CLICK)),
        pageviews=Count('id', filter=models.Q(event_type=EventType.PAGEVIEW)),
    ).order_by('flow__name')

    postback_rows = postbacks.values('flow_id').annotate(
        leads=Count('id'),
        payout=Sum('payout'),
    )
    postbacks_by_flow = {row['flow_id']: row for row in postback_rows}

    rows = []
    for row in flow_rows:
        conversion = postbacks_by_flow.get(row['flow_id'], {})
        rows.append({
            'flow_id': row['flow_id'],
            'flow_name': row['flow__name'],
            'clicks': row['clicks'],
            'pageviews': row['pageviews'],
            'leads': conversion.get('leads', 0),
            'payout': conversion.get('payout') or 0,
        })

    events = _filtered_events(request)
    banners = _filtered_banners(request)
    article_sort = request.GET.get('article_sort', '-pageviews')
    article_group_sort = request.GET.get('article_group_sort', '-pageviews')
    banner_sort = request.GET.get('banner_sort', '-impressions')

    article_rows = _article_rows(events, article_sort)
    article_group_rows = _article_group_rows(events, article_group_sort)
    banner_rows, banner_sort = _banner_rows(banners, banner_sort)
    banner_groups = _banner_group_rows(banners)

    export_response = _export(request, article_rows, article_group_rows, banner_rows)
    if export_response:
        return export_response

    context = {
        'page_title': 'Статистика',
        'rows': rows,
        'article_rows': article_rows,
        'article_group_rows': article_group_rows,
        'banner_rows': banner_rows,
        'banner_groups': banner_groups,
        'article_sort': article_sort,
        'article_group_sort': article_group_sort,
        'banner_sort': banner_sort,
        'banner_status': request.GET.get('banner_status', '').strip(),
        'banner_tier': request.GET.get('banner_tier', '').strip(),
    }
    context.update(_filter_context(request))
    return render(request, 'tracking/stats.html', context)
