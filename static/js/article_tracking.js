(function () {
  const config = window.OPSVITRINA_ARTICLE_TRACKING;
  if (!config || !config.eventUrl) {
    return;
  }

  const startedAt = Date.now();
  const scrollMarks = [25, 50, 75, 100];
  const sentScrollMarks = new Set();
  const externalSent = new Set();

  function getSessionId() {
    const key = 'opsvitrina_article_session_id';
    let value = window.localStorage.getItem(key);
    if (!value) {
      value = `${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
      window.localStorage.setItem(key, value);
    }
    return value;
  }

  const sessionId = getSessionId();

  function queryParams() {
    const params = {};
    new URLSearchParams(window.location.search).forEach((value, key) => {
      params[key] = value;
    });
    return params;
  }

  function timeOnPage() {
    return Math.max(0, Math.round((Date.now() - startedAt) / 1000));
  }

  function currentScrollDepth() {
    const doc = document.documentElement;
    const body = document.body;
    const scrollTop = window.scrollY || doc.scrollTop || body.scrollTop || 0;
    const scrollHeight = Math.max(body.scrollHeight, doc.scrollHeight);
    const viewport = window.innerHeight || doc.clientHeight || 0;
    const available = Math.max(1, scrollHeight - viewport);
    return Math.min(100, Math.round((scrollTop / available) * 100));
  }

  function payload(eventType, extra) {
    return Object.assign({
      event_type: eventType,
      session_id: sessionId,
      page_url: window.location.href,
      referrer: document.referrer,
      query_params: queryParams(),
      scroll_depth: currentScrollDepth(),
      time_on_page: timeOnPage(),
    }, extra || {});
  }

  function send(eventType, extra, useBeacon) {
    const body = JSON.stringify(payload(eventType, extra));
    if (useBeacon && navigator.sendBeacon) {
      navigator.sendBeacon(config.eventUrl, new Blob([body], { type: 'application/json' }));
      return;
    }
    fetch(config.eventUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
      keepalive: true,
      credentials: 'same-origin',
    }).catch(() => {});
  }

  function externalTracker() {
    return config.externalTracker || null;
  }

  function externalClickId(tracker) {
    const params = new URLSearchParams(window.location.search);
    const configuredName = tracker.inboundClickIdParam || 'clickid';
    return (
      params.get(configuredName) ||
      params.get('clickid') ||
      params.get('click_id') ||
      params.get('phx_click_id') ||
      params.get('subid') ||
      ''
    );
  }

  function sendExternal(eventKey) {
    const tracker = externalTracker();
    if (!tracker || !tracker.endpointUrl || externalSent.has(eventKey)) {
      return;
    }

    const eventParams = tracker.eventParams || {};
    const eventParam = eventParams[eventKey];
    const clickId = externalClickId(tracker);
    if (!eventParam || !clickId) {
      return;
    }

    externalSent.add(eventKey);
    try {
      const url = new URL(tracker.endpointUrl, window.location.href);
      url.searchParams.set(tracker.updateClickIdParam || 'upd_clickid', clickId);
      url.searchParams.set(eventParam, tracker.eventValue || '1');
      fetch(url.toString(), {
        mode: 'no-cors',
        credentials: 'omit',
        keepalive: true,
      }).catch(() => {});
    } catch (error) {}
  }

  function shouldMarkUrl(url) {
    return config.outboundMarkEnabled && /^https?:$/i.test(url.protocol);
  }

  function markedUrl(rawUrl) {
    const url = new URL(rawUrl, window.location.href);
    if (!shouldMarkUrl(url)) {
      return url.toString();
    }
    const param = config.outboundMarkParam || 'article_id';
    const value = config.outboundMarkValue || config.articlePublicId;
    if (config.outboundMarkReplaceExisting || !url.searchParams.has(param)) {
      url.searchParams.set(param, value);
    }
    return url.toString();
  }

  document.addEventListener('click', function (event) {
    sendExternal('any_click');

    const link = event.target.closest && event.target.closest('a[href]');
    if (!link) {
      send('click', {
        target_url: '',
        element_text: (event.target.textContent || '').trim().slice(0, 160),
      });
      return;
    }

    const originalHref = link.getAttribute('href');
    if (!originalHref || originalHref.startsWith('#') || originalHref.startsWith('javascript:')) {
      return;
    }

    const nextUrl = markedUrl(originalHref);
    if (nextUrl !== link.href) {
      link.href = nextUrl;
    }

    send('outbound_click', {
      target_url: nextUrl,
      element_text: (link.textContent || '').trim().slice(0, 160),
    }, true);
  }, true);

  window.addEventListener('scroll', function () {
    const depth = currentScrollDepth();
    scrollMarks.forEach((mark) => {
      if (depth >= mark && !sentScrollMarks.has(mark)) {
        sentScrollMarks.add(mark);
        send('scroll_depth', { scroll_depth: mark });
        if (mark === 25) sendExternal('scroll_25');
        if (mark === 50) sendExternal('scroll_50');
        if (mark === 75) sendExternal('scroll_75');
      }
    });
  }, { passive: true });

  window.addEventListener('pagehide', function () {
    send('leave', {}, true);
  });

  send('pageview');
  sendExternal('pageview');
  window.setTimeout(() => sendExternal('time_10s'), 10000);
  window.setTimeout(() => send('time_15s'), 15000);
  window.setTimeout(() => send('time_30s'), 30000);
  window.setTimeout(() => sendExternal('time_30s'), 30000);
  window.setTimeout(() => send('time_60s'), 60000);
  window.setTimeout(() => sendExternal('time_60s'), 60000);
}());
