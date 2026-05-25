import json
import random
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models, transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import escapejs
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .forms import ArticleForm, ArticleGroupForm
from .models import Article, ArticleGroup, ArticleGroupMembership, ArticleStatus, ArticleType, Vertical
from banners.models import Banner, BannerGroup, BannerPlacement, BannerSlot, BannerStatus, BannerTier, CreativeHeadline, CreativeImage
from tracking.models import ArticleBehaviorEvent, VisitEvent


HTML_SLOT_PATTERN = re.compile(
    r'<(?P<tag>[a-zA-Z][\w:-]*)(?P<attrs_before>[^>]*)\sdata-vitrina-slot=(?P<quote>[\'"])(?P<slot>[\w-]+)(?P=quote)(?P<attrs_after>[^>]*)>.*?</(?P=tag)>',
    re.IGNORECASE | re.DOTALL,
)


def _article_banner_utm_key(article):
    prefix = f'article_{article.id}_{article.public_id.hex[:8]}'
    return f'{prefix}_{Banner.objects.filter(utm_key__startswith=prefix).count() + 1}'


def _append_query_string(url, query_string):
    if not query_string:
        return url
    parts = urlsplit(url)
    query_items = parse_qsl(parts.query, keep_blank_values=True)
    query_items.extend(parse_qsl(query_string, keep_blank_values=True))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query_items), parts.fragment))


def _merge_query_strings(*query_strings):
    query_items = []
    for query_string in query_strings:
        if query_string:
            query_items.extend(parse_qsl(query_string, keep_blank_values=True))
    return urlencode(query_items)


def _append_article_mark(url, article):
    if not article.outbound_mark_enabled or not article.outbound_mark_param:
        return url

    parts = urlsplit(url)
    query_items = parse_qsl(parts.query, keep_blank_values=True)
    param_exists = any(key == article.outbound_mark_param for key, _value in query_items)

    if article.outbound_mark_replace_existing:
        query_items = [
            (key, value)
            for key, value in query_items
            if key != article.outbound_mark_param
        ]

    if article.outbound_mark_replace_existing or not param_exists:
        query_items.append((article.outbound_mark_param, article.get_outbound_mark_value()))

    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query_items), parts.fragment))


def _query_dict(query_string):
    return dict(parse_qsl(query_string or '', keep_blank_values=True))


def _client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _article_tracking_config(article):
    tracker_profile = article.get_tracker_profile()
    return {
        'articlePublicId': str(article.public_id),
        'eventUrl': reverse('article_behavior_event', kwargs={'public_id': article.public_id}),
        'outboundMarkEnabled': article.outbound_mark_enabled,
        'outboundMarkParam': article.outbound_mark_param,
        'outboundMarkValue': article.get_outbound_mark_value(),
        'outboundMarkReplaceExisting': article.outbound_mark_replace_existing,
        'externalTracker': tracker_profile.frontend_config() if tracker_profile else None,
    }


def _html_tracking_snippet(article):
    config = json.dumps(_article_tracking_config(article), ensure_ascii=False)
    return (
        '<script>'
        f'window.OPSVITRINA_ARTICLE_TRACKING = JSON.parse("{escapejs(config)}");'
        '</script>'
        '<script src="/static/js/article_tracking.js" defer></script>'
    )


def _inject_html_tracking(html, article):
    snippet = _html_tracking_snippet(article)
    lower_html = html.lower()
    body_index = lower_html.rfind('</body>')
    if body_index != -1:
        return html[:body_index] + snippet + html[body_index:]
    return html + snippet


def _request_banner_tier(request):
    raw_tier = (
        request.GET.get('banner_tier')
        or request.GET.get('echelon')
        or request.GET.get('tier')
        or BannerTier.FIRST
    )
    try:
        tier = int(raw_tier)
    except (TypeError, ValueError):
        return BannerTier.FIRST
    return tier if tier in {BannerTier.FIRST, BannerTier.SECOND} else BannerTier.FIRST


def _article_banners(article, request, enabled_slots=None):
    display_tier = _request_banner_tier(request)
    article_group_ids = list(article.groups.values_list('id', flat=True))
    banners = list(
        Banner.objects
        .filter(status=BannerStatus.ACTIVE, group__status=BannerStatus.ACTIVE, display_tier=display_tier)
        .select_related('group', 'image', 'headline')
        .filter(
            models.Q(group__articles=article)
            | models.Q(group__article_groups__in=article_group_ids)
            | (models.Q(group__articles__isnull=True) & models.Q(group__article_groups__isnull=True))
        )
        .distinct()
        .order_by('-priority', 'id')
    )
    if enabled_slots is None:
        slot_names = [slot for slot, _label in BannerSlot.choices]
    else:
        slot_names = [
            slot
            for slot in enabled_slots
            if slot in {choice for choice, _label in BannerSlot.choices}
        ]
    slots = {slot: None for slot in slot_names}
    used_banner_ids = set()
    placement_slots = _placement_banners(article, display_tier, slot_names)
    for slot, banner in placement_slots.items():
        if not banner:
            continue
        slots[slot] = banner
        used_banner_ids.add(banner.id)

    for slot in slots:
        if slots[slot]:
            continue
        candidates = [
            banner
            for banner in banners
            if banner.id not in used_banner_ids and banner.group.can_show_in_slot(slot)
        ]
        if not candidates:
            continue
        weights = [max(banner.priority, 0) + 1 for banner in candidates]
        banner = random.choices(candidates, weights=weights, k=1)[0]
        slots[slot] = banner
        used_banner_ids.add(banner.id)
    shown_ids = [banner.id for banner in slots.values() if banner]
    if shown_ids:
        Banner.objects.filter(id__in=shown_ids).update(impressions=models.F('impressions') + 1)
    return slots


def _placement_banners(article, display_tier, slot_names):
    placements = (
        BannerPlacement.objects
        .filter(is_active=True, display_tier=display_tier, slot__in=slot_names)
        .filter(models.Q(article=article) | models.Q(article_group__in=article.groups.all()))
        .select_related('banner', 'banner__group', 'banner__image', 'banner__headline', 'article_group', 'article')
        .order_by('article_group_id')
    )
    group_pins = {}
    article_pins = {}
    for placement in placements:
        banner = placement.banner
        if banner.status != BannerStatus.ACTIVE or banner.group.status != BannerStatus.ACTIVE:
            continue
        if banner.display_tier != display_tier or not banner.group.can_show_in_slot(placement.slot):
            continue
        if placement.article_id == article.id:
            article_pins[placement.slot] = banner
        elif placement.article_group_id and placement.slot not in group_pins:
            group_pins[placement.slot] = banner
    return {slot: article_pins.get(slot) or group_pins.get(slot) for slot in slot_names}


def _normalize_slot_name(slot_name):
    return (slot_name or '').strip().lower().replace('-', '_')


def _html_article_slots(html):
    return {
        _normalize_slot_name(match.group('slot'))
        for match in HTML_SLOT_PATTERN.finditer(html)
    }


def _html_banner_slot(request, banner, slot_name):
    return render_to_string(
        'articles/partials/html_banner_slot.html',
        {
            'banner': banner,
            'slot_name': slot_name,
        },
        request=request,
    )


def _inject_html_banner_assets(html):
    stylesheet = '<link rel="stylesheet" href="/static/css/html_article_banners.css">'
    if stylesheet in html:
        return html
    lower_html = html.lower()
    head_index = lower_html.rfind('</head>')
    if head_index != -1:
        return html[:head_index] + stylesheet + html[head_index:]
    return stylesheet + html


def _inject_html_banners(html, article, request):
    requested_slots = _html_article_slots(html)
    if not requested_slots:
        return html

    banner_slots = _article_banners(article, request, enabled_slots=requested_slots)

    def replace_slot(match):
        slot_name = _normalize_slot_name(match.group('slot'))
        if slot_name not in banner_slots:
            return match.group(0)
        banner_html = _html_banner_slot(request, banner_slots.get(slot_name), slot_name)
        return banner_html or match.group(0)

    html = HTML_SLOT_PATTERN.sub(replace_slot, html)
    return _inject_html_banner_assets(html)


def _render_article_response(request, article, extra_query_string=''):
    if article.article_type == ArticleType.EXTERNAL and article.external_url:
        target_url = _append_query_string(
            article.external_url,
            _merge_query_strings(request.META.get('QUERY_STRING', ''), extra_query_string),
        )
        target_url = _append_article_mark(target_url, article)
        return redirect(target_url)

    if article.article_type == ArticleType.HTML:
        if not article.html_file:
            raise Http404('HTML file not found')
        with article.html_file.open('rb') as html_file:
            html = html_file.read().decode('utf-8', errors='ignore')
            html = _inject_html_banners(html, article, request)
            return HttpResponse(_inject_html_tracking(html, article), content_type='text/html; charset=utf-8')

    return render(request, 'articles/article_preview.html', {
        'article': article,
        'banner_slots': _article_banners(article, request),
        'tracking_config': _article_tracking_config(article),
    })


def _sync_group_memberships(group):
    existing_article_ids = set(group.memberships.values_list('article_id', flat=True))
    missing_article_ids = (
        group.articles
        .exclude(id__in=existing_article_ids)
        .values_list('id', flat=True)
    )
    ArticleGroupMembership.objects.bulk_create([
        ArticleGroupMembership(group=group, article_id=article_id)
        for article_id in missing_article_ids
    ])


def _eligible_group_memberships(group):
    _sync_group_memberships(group)
    return (
        ArticleGroupMembership.objects
        .filter(
            group=group,
            article__groups=group,
            is_active=True,
            priority__gt=0,
            article__status=ArticleStatus.ACTIVE,
        )
        .select_related('article', 'article__category', 'article__vertical', 'article__owner')
        .order_by('id')
    )


def _select_group_membership(group):
    memberships = list(_eligible_group_memberships(group))
    if not memberships:
        raise Http404('No active articles in group')

    def score(membership):
        return membership.impressions / max(membership.priority, 1)

    selected = min(memberships, key=lambda membership: (score(membership), membership.id))
    ArticleGroupMembership.objects.filter(pk=selected.pk).update(impressions=models.F('impressions') + 1)
    selected.impressions += 1
    return selected


def _eligible_article_banners(article, display_tier, slot, user):
    article_group_ids = list(article.groups.values_list('id', flat=True))
    return (
        Banner.objects
        .visible_for(user)
        .filter(status=BannerStatus.ACTIVE, group__status=BannerStatus.ACTIVE, display_tier=display_tier)
        .select_related('group', 'image', 'headline')
        .filter(
            models.Q(group__articles=article)
            | models.Q(group__article_groups__in=article_group_ids)
            | (models.Q(group__articles__isnull=True) & models.Q(group__article_groups__isnull=True))
        )
        .distinct()
        .order_by('-priority', '-impressions', 'id')
    )


def _article_banner_dashboard(article, user):
    article_groups = list(article.groups.all())
    group = article_groups[0] if article_groups else None
    placements = (
        BannerPlacement.objects
        .filter(models.Q(article=article) | models.Q(article_group__in=article_groups))
        .select_related('banner', 'banner__headline', 'banner__image', 'article_group')
    )
    article_pins = {
        (placement.slot, placement.display_tier): placement
        for placement in placements
        if placement.article_id == article.id and placement.is_active
    }
    group_pins = {}
    for placement in placements:
        key = (placement.slot, placement.display_tier)
        if placement.article_group_id and placement.is_active and key not in group_pins:
            group_pins[key] = placement

    rows = []
    for tier, tier_label in BannerTier.choices:
        for slot, slot_label in BannerSlot.choices:
            candidates = [
                banner
                for banner in _eligible_article_banners(article, tier, slot, user)
                if banner.group.can_show_in_slot(slot)
            ]
            key = (slot, tier)
            rows.append({
                'slot': slot,
                'slot_label': slot_label,
                'tier': tier,
                'tier_label': tier_label,
                'article_pin': article_pins.get(key),
                'group_pin': group_pins.get(key),
                'effective_pin': article_pins.get(key) or group_pins.get(key),
                'candidates': candidates,
            })

    return {
        'rows': rows,
        'article_group': group,
    }


@login_required
def article_list(request):
    articles = Article.objects.visible_for(request.user).select_related('category', 'vertical', 'owner', 'team').prefetch_related('groups')

    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    article_type = request.GET.get('type', '').strip()
    country = request.GET.get('country', '').strip()
    vertical_id = request.GET.get('vertical', '').strip()
    group_id = request.GET.get('group', '').strip()

    if query:
        articles = articles.filter(title__icontains=query)
    if status:
        articles = articles.filter(status=status)
    if article_type:
        articles = articles.filter(article_type=article_type)
    if country:
        articles = articles.filter(country__iexact=country)
    if vertical_id:
        articles = articles.filter(vertical_id=vertical_id)
    if group_id:
        articles = articles.filter(groups__id=group_id)

    paginator = Paginator(articles, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'articles/article_list.html', {
        'page_title': 'Статьи',
        'page_obj': page_obj,
        'query': query,
        'status': status,
        'article_type': article_type,
        'country': country,
        'vertical_id': vertical_id,
        'group_id': group_id,
        'verticals': Vertical.objects.all(),
        'groups': ArticleGroup.objects.visible_for(request.user),
    })


@login_required
def article_group_list(request):
    groups = ArticleGroup.objects.visible_for(request.user).select_related('vertical', 'owner', 'team').prefetch_related('articles')

    query = request.GET.get('q', '').strip()
    geo = request.GET.get('geo', '').strip()
    vertical_id = request.GET.get('vertical', '').strip()
    status = request.GET.get('status', '').strip()

    if query:
        groups = groups.filter(models.Q(name__icontains=query) | models.Q(description__icontains=query))
    if geo:
        groups = groups.filter(geo__iexact=geo)
    if vertical_id:
        groups = groups.filter(vertical_id=vertical_id)
    if status:
        groups = groups.filter(status=status)

    groups = groups.annotate(article_count=models.Count('articles', distinct=True))
    paginator = Paginator(groups, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'articles/article_group_list.html', {
        'page_title': 'Группы статей',
        'page_obj': page_obj,
        'query': query,
        'geo': geo,
        'vertical_id': vertical_id,
        'status': status,
        'verticals': Vertical.objects.all(),
    })


@login_required
@require_POST
def article_bulk_action(request):
    action = request.POST.get('action')
    article_ids = request.POST.getlist('article_ids')
    articles = Article.objects.visible_for(request.user).filter(id__in=article_ids)

    if not article_ids:
        messages.error(request, 'Выберите хотя бы одну статью.')
        return redirect('articles:list')

    if action == 'add_to_group':
        group_id = request.POST.get('group')
        group = get_object_or_404(ArticleGroup.objects.visible_for(request.user), pk=group_id)
        updated_count = 0
        with transaction.atomic():
            for article in articles:
                article.groups.add(group)
                ArticleGroupMembership.objects.get_or_create(
                    group=group,
                    article=article,
                    defaults={
                        'priority': 50,
                        'utm_query': '',
                        'is_active': True,
                    },
                )
                updated_count += 1
        messages.success(request, f'Статей добавлено в группу “{group.name}”: {updated_count}.')
        return redirect('articles:list')
    if action in {'activate', 'deactivate'}:
        new_status = ArticleStatus.ACTIVE if action == 'activate' else ArticleStatus.DRAFT
        updated_count = articles.update(status=new_status)
        action_label = 'включено' if action == 'activate' else 'выключено'
        messages.success(request, f'Статей {action_label}: {updated_count}.')
        return redirect('articles:list')

    messages.error(request, 'Неизвестное массовое действие.')
    return redirect('articles:list')


@login_required
@require_POST
def article_toggle_status(request, pk):
    article = get_object_or_404(Article.objects.visible_for(request.user), pk=pk)
    article.status = ArticleStatus.DRAFT if article.status == ArticleStatus.ACTIVE else ArticleStatus.ACTIVE
    article.save(update_fields=['status', 'updated_at'])
    return redirect(request.POST.get('next') or 'articles:list')


@login_required
@require_POST
def article_group_toggle_status(request, pk):
    group = get_object_or_404(ArticleGroup.objects.visible_for(request.user), pk=pk)
    group.status = ArticleStatus.DRAFT if group.status == ArticleStatus.ACTIVE else ArticleStatus.ACTIVE
    group.save(update_fields=['status', 'updated_at'])
    return redirect(request.POST.get('next') or 'articles:group_list')


@login_required
def article_create(request):
    if request.method == 'POST':
        form = ArticleForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            article = form.save(commit=False)
            article.owner = request.user
            article.save()
            form.save_article_group(article, request.user)
            return redirect('articles:list')
    else:
        form = ArticleForm(user=request.user)

    return render(request, 'articles/article_form.html', {
        'page_title': 'Новая статья',
        'form': form,
        'article': None,
    })


@login_required
def article_update(request, pk):
    article = get_object_or_404(Article.objects.visible_for(request.user), pk=pk)

    if request.method == 'POST':
        form = ArticleForm(request.POST, request.FILES, instance=article, user=request.user)
        if form.is_valid():
            article = form.save()
            form.save_article_group(article, request.user)
            return redirect('articles:list')
    else:
        form = ArticleForm(instance=article, user=request.user)

    return render(request, 'articles/article_form.html', {
        'page_title': 'Редактирование статьи',
        'form': form,
        'article': article,
        'banner_dashboard': _article_banner_dashboard(article, request.user),
    })


@login_required
@require_POST
def article_delete(request, pk):
    article = get_object_or_404(Article.objects.visible_for(request.user), pk=pk)
    title = article.title
    with transaction.atomic():
        BannerPlacement.objects.filter(article=article).delete()
        ArticleBehaviorEvent.objects.filter(article=article).delete()
        VisitEvent.objects.filter(article=article).delete()
        article.delete()
    messages.success(request, f'Статья “{title}” удалена.')
    return redirect('articles:list')


@login_required
def article_group_update(request, pk):
    group = get_object_or_404(ArticleGroup.objects.visible_for(request.user), pk=pk)
    if request.method == 'POST':
        form_action = request.POST.get('form_action', 'settings')
        if form_action == 'memberships':
            _sync_group_memberships(group)
            with transaction.atomic():
                for membership in group.memberships.select_related('article'):
                    prefix = f'membership_{membership.id}'
                    try:
                        priority = int(request.POST.get(f'{prefix}_priority') or 0)
                    except (TypeError, ValueError):
                        priority = 0
                    membership.priority = max(priority, 0)
                    membership.utm_query = (request.POST.get(f'{prefix}_utm_query') or '').strip().lstrip('?')
                    membership.is_active = request.POST.get(f'{prefix}_is_active') == 'on'
                    membership.save(update_fields=['priority', 'utm_query', 'is_active', 'updated_at'])

                add_article_id = request.POST.get('add_article')
                if add_article_id:
                    article = get_object_or_404(Article.objects.visible_for(request.user), pk=add_article_id)
                    article.groups.add(group)
                    ArticleGroupMembership.objects.get_or_create(group=group, article=article)

            messages.success(request, 'Настройки ротации группы обновлены.')
            return redirect('articles:group_update', pk=group.pk)
        else:
            form = ArticleGroupForm(request.POST, instance=group, user=request.user)
            if form.is_valid():
                form.save()
                messages.success(request, 'Группа статей обновлена.')
                return redirect('articles:group_update', pk=group.pk)
    else:
        form = ArticleGroupForm(instance=group, user=request.user)

    _sync_group_memberships(group)
    memberships = group.memberships.select_related('article').order_by('article__title')
    used_article_ids = memberships.values_list('article_id', flat=True)
    available_articles = (
        Article.objects
        .visible_for(request.user)
        .filter(status=ArticleStatus.ACTIVE)
        .exclude(id__in=used_article_ids)
        .order_by('title')
    )

    return render(request, 'articles/article_group_form.html', {
        'page_title': 'Редактирование группы статей',
        'form': form,
        'group': group,
        'memberships': memberships,
        'available_articles': available_articles,
        'public_url': request.build_absolute_uri(group.get_public_url()),
    })


@login_required
@require_POST
def article_group_delete(request, pk):
    group = get_object_or_404(ArticleGroup.objects.visible_for(request.user), pk=pk)
    name = group.name
    group.delete()
    messages.success(request, f'Группа статей “{name}” удалена.')
    return redirect('articles:list')


@login_required
@require_POST
def article_pin_banner(request, pk):
    article = get_object_or_404(Article.objects.visible_for(request.user).prefetch_related('groups'), pk=pk)
    action = request.POST.get('action')
    scope = request.POST.get('scope')
    slot = request.POST.get('slot')
    display_tier = request.POST.get('display_tier')
    banner_id = request.POST.get('banner')

    valid_slots = {choice for choice, _label in BannerSlot.choices}
    valid_tiers = {str(choice) for choice, _label in BannerTier.choices}
    if slot not in valid_slots or display_tier not in valid_tiers or scope not in {'article', 'group'}:
        messages.error(request, 'Некорректные параметры закрепления.')
        return redirect('articles:update', pk=article.pk)

    target_kwargs = {'article': article} if scope == 'article' else {}
    if scope == 'group':
        article_group = article.groups.first()
        if not article_group:
            messages.error(request, 'Чтобы закрепить баннер на группу, сначала добавьте статью в группу.')
            return redirect('articles:update', pk=article.pk)
        target_kwargs = {'article_group': article_group}

    if action == 'unpin':
        BannerPlacement.objects.filter(
            **target_kwargs,
            slot=slot,
            display_tier=int(display_tier),
        ).delete()
        messages.success(request, 'Закрепление снято, слот снова работает в авторотации.')
        return redirect('articles:update', pk=article.pk)

    banner = get_object_or_404(
        Banner.objects.visible_for(request.user).select_related('group'),
        pk=banner_id,
        status=BannerStatus.ACTIVE,
        group__status=BannerStatus.ACTIVE,
        display_tier=int(display_tier),
    )
    if not banner.group.can_show_in_slot(slot):
        messages.error(request, 'Этот баннер нельзя закрепить в выбранный слот: слот исключен в настройках группы баннера.')
        return redirect('articles:update', pk=article.pk)

    placement, _created = BannerPlacement.objects.update_or_create(
        **target_kwargs,
        slot=slot,
        display_tier=int(display_tier),
        defaults={
            'owner': request.user,
            'team': request.user.team,
            'banner': banner,
            'is_active': True,
        },
    )
    target_name = 'статью' if scope == 'article' else 'группу статей'
    messages.success(request, f'Баннер #{placement.banner_id} закреплен на {target_name}.')
    return redirect('articles:update', pk=article.pk)


@login_required
def article_preview(request, pk):
    article = get_object_or_404(
        Article.objects.visible_for(request.user).select_related('category', 'owner'),
        pk=pk,
    )
    return _render_article_response(request, article)


@login_required
@require_POST
def article_create_banner(request, pk):
    article = get_object_or_404(Article.objects.visible_for(request.user).prefetch_related('groups'), pk=pk)
    if not article.image:
        messages.error(request, 'Чтобы создать баннер из статьи, сначала добавьте главную картинку.')
        return redirect('articles:list')

    with transaction.atomic():
        group = BannerGroup.objects.create(
            owner=request.user,
            team=request.user.team,
            name=f'Баннер статьи #{article.id}',
            description=f'Автоматически создан из статьи: {article.title}',
            target_url=request.build_absolute_uri(article.get_public_url()),
        )
        group.articles.add(article)

        image = CreativeImage.objects.create(
            owner=request.user,
            team=request.user.team,
            group=group,
            image=article.image.name,
            original_name=article.image.name.rsplit('/', 1)[-1],
        )
        headline = CreativeHeadline.objects.create(
            owner=request.user,
            team=request.user.team,
            group=group,
            text=article.title,
        )
        banner = Banner.objects.create(
            owner=request.user,
            team=request.user.team,
            group=group,
            image=image,
            headline=headline,
            target_url=request.build_absolute_uri(article.get_public_url()),
            utm_key=_article_banner_utm_key(article),
            display_tier=BannerTier.SECOND,
            priority=50,
        )

    messages.success(request, f'Баннер #{banner.id} создан из статьи и привязан ко второму эшелону.')
    return redirect('banners:update', pk=banner.pk)


def public_article(request, public_id):
    article = get_object_or_404(
        Article.objects.select_related('category', 'vertical', 'owner'),
        public_id=public_id,
        status=ArticleStatus.ACTIVE,
    )
    return _render_article_response(request, article)


def public_article_group(request, public_id):
    group = get_object_or_404(ArticleGroup, public_id=public_id, status=ArticleStatus.ACTIVE)
    membership = _select_group_membership(group)
    target_url = _append_query_string(
        membership.article.get_public_url(),
        _merge_query_strings(request.META.get('QUERY_STRING', ''), membership.utm_query),
    )
    return redirect(target_url)


@csrf_exempt
@require_POST
def article_behavior_event(request, public_id):
    article = get_object_or_404(Article, public_id=public_id, status=ArticleStatus.ACTIVE)
    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        data = {}

    click_id = data.get('click_id') or data.get('clickid') or data.get('subid') or ''
    query_params = data.get('query_params') or {}
    if not click_id and isinstance(query_params, dict):
        click_id = query_params.get('clickid') or query_params.get('click_id') or query_params.get('subid') or ''

    ArticleBehaviorEvent.objects.create(
        owner=article.owner,
        team=article.team,
        article=article,
        event_type=(data.get('event_type') or 'unknown')[:40],
        session_id=(data.get('session_id') or '')[:80],
        click_id=str(click_id)[:255],
        target_url=(data.get('target_url') or '')[:200],
        page_url=(data.get('page_url') or '')[:200],
        referrer=(data.get('referrer') or '')[:200],
        scroll_depth=int(data.get('scroll_depth') or 0),
        time_on_page=int(data.get('time_on_page') or 0),
        query_params=query_params if isinstance(query_params, dict) else {},
        payload=data,
        ip_address=_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )
    return HttpResponse(status=204)
