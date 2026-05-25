from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from .forms import FlowForm
from .models import Flow


@login_required
def flow_list(request):
    flows = Flow.objects.visible_for(request.user).select_related('article', 'owner', 'team', 'traffic_source')

    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()

    if query:
        flows = flows.filter(name__icontains=query)
    if status:
        flows = flows.filter(status=status)

    paginator = Paginator(flows, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'flows/flow_list.html', {
        'page_title': 'Новостные потоки',
        'page_obj': page_obj,
        'query': query,
        'status': status,
    })


@login_required
def flow_create(request):
    if request.method == 'POST':
        form = FlowForm(request.POST, user=request.user)
        if form.is_valid():
            flow = form.save(commit=False)
            flow.owner = request.user
            flow.save()
            form.save_m2m()
            return redirect('flows:list')
    else:
        form = FlowForm(user=request.user)

    return render(request, 'flows/flow_form.html', {
        'page_title': 'Новый поток',
        'form': form,
        'flow': None,
    })


@login_required
def flow_update(request, pk):
    flow = get_object_or_404(Flow.objects.visible_for(request.user), pk=pk)

    if request.method == 'POST':
        form = FlowForm(request.POST, instance=flow, user=request.user)
        if form.is_valid():
            form.save()
            return redirect('flows:list')
    else:
        form = FlowForm(instance=flow, user=request.user)

    return render(request, 'flows/flow_form.html', {
        'page_title': 'Редактирование потока',
        'form': form,
        'flow': flow,
    })
