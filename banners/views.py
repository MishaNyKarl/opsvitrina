from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .forms import BannerFilterForm, BannerForm, BannerGroupForm, BannerUploadForm
from .models import Banner, BannerGroup, BannerPlacement, BannerStatus, CreativeHeadline, CreativeImage
from core.tracking_urls import PLACEHOLDER_PATTERN, append_query_string as append_tracking_query_string, tracking_query_string


BANNER_URL_PLACEHOLDER_PATTERN = PLACEHOLDER_PATTERN


def _banner_utm_key(group, image, headline, index):
    base = slugify(f'{group.id}-{image.id}-{headline.id}') or f'banner-{group.id}-{index}'
    return f'bn_{base}_{index}'


def _banner_utm_param(banner):
    return banner.effective_banner_utm_param


def _append_banner_mark(url, banner, include_banner_id=True):
    parts = urlsplit(url)
    query_items = parse_qsl(parts.query, keep_blank_values=True)
    banner_utm_param = _banner_utm_param(banner)
    if include_banner_id and not any(key == 'banner_id' for key, _value in query_items):
        query_items.append(('banner_id', str(banner.id)))
    if not any(key == banner_utm_param for key, _value in query_items):
        query_items.append((banner_utm_param, banner.utm_key))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query_items), parts.fragment))


def _first_value(params, *names):
    for name in names:
        value = params.get(name)
        if value not in (None, ''):
            return value
    return ''


def _usable_value(params, *names):
    value = _first_value(params, *names)
    if BANNER_URL_PLACEHOLDER_PATTERN.search(value):
        return ''
    return value


def _banner_url_values(banner, query_string):
    params = dict(parse_qsl(query_string or '', keep_blank_values=True))
    values = dict(params)
    click_id = _first_value(params, 'click_id', 'clickid', 'phx_click_id', 'subid')
    banner_utm_param = _banner_utm_param(banner)
    values.update({
        'click_id': click_id,
        'clickid': click_id,
        'phx_click_id': _first_value(params, 'phx_click_id') or click_id,
        'subid': _first_value(params, 'subid') or click_id,
        'article_id': _usable_value(params, 'article_id'),
        'article_public_id': _usable_value(params, 'article_public_id', 'article_uuid'),
        'article_uuid': _usable_value(params, 'article_uuid', 'article_public_id'),
        'ad_vtr_name': banner.utm_key,
        'banner_utm': banner.utm_key,
        'banner_id': str(banner.id),
        banner_utm_param: banner.utm_key,
    })
    return values


def _render_banner_url_template(url, banner, query_string):
    values = _banner_url_values(banner, query_string)

    def replace_placeholder(match):
        return str(values.get(match.group(1), ''))

    return BANNER_URL_PLACEHOLDER_PATTERN.sub(replace_placeholder, url)


def _resolved_banner_query_string(banner, query_string):
    values = _banner_url_values(banner, query_string)
    banner_utm_param = _banner_utm_param(banner)
    return tracking_query_string(
        query_string,
        values,
        force_values={
            'ad_vtr_name': banner.utm_key,
            'banner_utm': banner.utm_key,
            'banner_id': banner.id,
            banner_utm_param: banner.utm_key,
        },
    )


def _build_banner_target_url(target_url, banner, query_string):
    resolved_query_string = _resolved_banner_query_string(banner, query_string)
    if BANNER_URL_PLACEHOLDER_PATTERN.search(target_url):
        target_url = _render_banner_url_template(target_url, banner, query_string)
    target_url = append_tracking_query_string(target_url, resolved_query_string, skip_existing=True)
    return _append_banner_mark(target_url, banner)


@login_required
def banner_list(request):
    form = BannerFilterForm(request.GET or None, user=request.user)
    banners = Banner.objects.visible_for(request.user).select_related('group', 'image', 'headline', 'owner', 'team')
    groups = BannerGroup.objects.visible_for(request.user).prefetch_related('images', 'headlines', 'banners')

    if form.is_valid():
        query = form.cleaned_data.get('q')
        group = form.cleaned_data.get('group')
        display_tier = form.cleaned_data.get('display_tier')
        status = form.cleaned_data.get('status')
        if query:
            banners = banners.filter(headline__text__icontains=query)
        if group:
            banners = banners.filter(group=group)
        if display_tier:
            banners = banners.filter(display_tier=display_tier)
        if status:
            banners = banners.filter(status=status)

    paginator = Paginator(banners, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'banners/banner_list.html', {
        'page_title': 'Баннеры',
        'form': form,
        'groups': groups,
        'page_obj': page_obj,
    })


@login_required
def banner_upload(request):
    if request.method == 'POST':
        form = BannerUploadForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            with transaction.atomic():
                group = BannerGroup.objects.create(
                    owner=request.user,
                    team=request.user.team,
                    name=form.cleaned_data['group_name'],
                    description=form.cleaned_data['description'],
                    target_url=form.cleaned_data['target_url'],
                    banner_utm_param=form.cleaned_data['banner_utm_param'],
                    excluded_slots=form.cleaned_data['excluded_slots'],
                )
                group.articles.set(form.cleaned_data['articles'])
                group.article_groups.set(form.cleaned_data['article_groups'])

                images = []
                for uploaded_image in form.cleaned_data['images']:
                    images.append(CreativeImage.objects.create(
                        owner=request.user,
                        team=request.user.team,
                        group=group,
                        image=uploaded_image,
                        original_name=uploaded_image.name,
                    ))

                headlines = []
                for headline_text in form.cleaned_data['headlines']:
                    headlines.append(CreativeHeadline.objects.create(
                        owner=request.user,
                        team=request.user.team,
                        group=group,
                        text=headline_text,
                    ))

                created_count = 0
                for image in images:
                    for headline in headlines:
                        created_count += 1
                        Banner.objects.create(
                            owner=request.user,
                            team=request.user.team,
                            group=group,
                            image=image,
                            headline=headline,
                            target_url=form.cleaned_data['target_url'],
                            priority=form.cleaned_data['priority'],
                            display_tier=form.cleaned_data['display_tier'],
                            utm_key=_banner_utm_key(group, image, headline, created_count),
                        )

            messages.success(
                request,
                f'Группа создана: {len(images)} картинок × {len(headlines)} заголовков = {created_count} баннеров.',
            )
            return redirect('banners:list')
    else:
        form = BannerUploadForm(user=request.user)

    return render(request, 'banners/banner_upload.html', {
        'page_title': 'Загрузка креативов',
        'form': form,
    })


@login_required
def banner_group_update(request, pk):
    group = get_object_or_404(BannerGroup.objects.visible_for(request.user), pk=pk)
    if request.method == 'POST':
        form = BannerGroupForm(request.POST, instance=group, user=request.user)
        if form.is_valid():
            form.save()
            group.banners.update(target_url=group.target_url)
            messages.success(request, 'Группа баннеров обновлена.')
            return redirect('banners:list')
    else:
        form = BannerGroupForm(instance=group, user=request.user)

    return render(request, 'banners/banner_group_form.html', {
        'page_title': 'Редактирование группы',
        'form': form,
        'group': group,
    })


@login_required
@require_POST
def banner_group_delete(request, pk):
    group = get_object_or_404(BannerGroup.objects.visible_for(request.user), pk=pk)
    name = group.name
    group.delete()
    messages.success(request, f'Группа баннеров “{name}” удалена.')
    return redirect('banners:list')


@login_required
@require_POST
def banner_group_toggle_status(request, pk):
    group = get_object_or_404(BannerGroup.objects.visible_for(request.user), pk=pk)
    group.status = BannerStatus.DRAFT if group.status == BannerStatus.ACTIVE else BannerStatus.ACTIVE
    group.save(update_fields=['status', 'updated_at'])
    return redirect(request.POST.get('next') or 'banners:list')


@login_required
def banner_update(request, pk):
    banner = get_object_or_404(
        Banner.objects.visible_for(request.user).select_related('group', 'image', 'headline'),
        pk=pk,
    )
    if request.method == 'POST':
        form = BannerForm(request.POST, instance=banner)
        if form.is_valid():
            form.save()
            messages.success(request, 'Баннер обновлён.')
            return redirect('banners:list')
    else:
        form = BannerForm(instance=banner)

    return render(request, 'banners/banner_form.html', {
        'page_title': 'Редактирование баннера',
        'form': form,
        'banner': banner,
    })


@login_required
@require_POST
def banner_delete(request, pk):
    banner = get_object_or_404(Banner.objects.visible_for(request.user), pk=pk)
    banner_id = banner.id
    with transaction.atomic():
        BannerPlacement.objects.filter(banner=banner).delete()
        banner.delete()
    messages.success(request, f'Баннер #{banner_id} удалён.')
    return redirect('banners:list')


@login_required
@require_POST
def banner_toggle_status(request, pk):
    banner = get_object_or_404(Banner.objects.visible_for(request.user), pk=pk)
    banner.status = BannerStatus.DRAFT if banner.status == BannerStatus.ACTIVE else BannerStatus.ACTIVE
    banner.save(update_fields=['status', 'updated_at'])
    return redirect(request.POST.get('next') or 'banners:list')


def banner_click(request, pk):
    banner = get_object_or_404(
        Banner.objects.select_related('group'),
        pk=pk,
        status='active',
        group__status='active',
    )
    target_url = banner.target_url or banner.group.target_url
    if not target_url:
        raise Http404('Target URL not configured')

    Banner.objects.filter(pk=banner.pk).update(clicks=models.F('clicks') + 1)
    target_url = _build_banner_target_url(target_url, banner, request.META.get('QUERY_STRING', ''))
    return redirect(target_url)
