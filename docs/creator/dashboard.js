let accessKey = '', overview, ticketId;
const el = id => document.getElementById(id);
const hosted = el('login-form').dataset?.hosted === 'true';
const apiOrigin = el('login-form').dataset?.apiOrigin || '';
if (hosted && !apiOrigin) {
  el('login-form').hidden = true;
  el('status').textContent = 'The hosted Creator desk is waiting for its private service. Use your local Creator desk for now.';
}
const node = (tag, value, cls) => { const n = document.createElement(tag); n.textContent = value; if (cls) n.className = cls; return n; };
const date = value => new Date(value).toLocaleString();
async function api(path, options = {}) {
  const res = await fetch(apiOrigin + path, { ...options, redirect: 'error', credentials: 'omit', headers: { Authorization: 'Bearer ' + accessKey, 'Content-Type': 'application/json' } });
  const data = await res.json(); if (!res.ok) throw Error(data.error || 'Request failed'); return data;
}
function error(e) { el('status').textContent = e.message; }
async function refresh() {
  overview = await api('/admin/overview');
  el('login').hidden = true; el('workspace').hidden = false; el('signout').hidden = false;
  for (const [id, value] of Object.entries({ total: overview.installations, monthly: overview.active30Days, daily: overview.active24Hours, open: overview.openTickets })) el(id).textContent = value.toLocaleString();
  el('breakdowns').replaceChildren(...[['Product', overview.products], ['Brand', overview.brands], ['Android', overview.osVersions]].flatMap(([title, values]) => [node('h3', title), ...values.map(v => node('p', v.label + ' · ' + v.count))]));
  el('quality').replaceChildren(...Object.entries(overview.quality30Days).map(([key, value]) => node('p', key.replace(/([A-Z])/g, ' $1') + ' · ' + value)));
  el('notice').textContent = overview.notice;
  renderSponsors(overview.sponsors);
  el('countries').replaceChildren(...overview.countries.map(c => { const row = node('div', '', 'country'); row.append(node('span', c.country), node('strong', c.count)); return row; }));
  el('devices').replaceChildren(...overview.devices.map(d => { const row = document.createElement('tr'); for (const value of [d.id.slice(0, 8), d.profile.product || '—', [d.profile.brand, d.profile.model].filter(Boolean).join(' / '), d.profile.osVersion || '—', d.profile.appVersion || '—', d.country || 'Not shared', date(d.last_seen)]) row.append(node('td', value)); return row; }));
  el('cities').replaceChildren(...(overview.cities || []).map(c => node('p', [c.country,c.region,c.city].filter(Boolean).join(' / ') + ' · ' + c.count + ' installations · ' + c.source)));
  el('locations').replaceChildren(...overview.devices.map(d => {
    const row = document.createElement('tr'), p = d.location?.position, place = d.location?.place;
    for (const value of [d.id.slice(0,8), place ? [place.country,place.region,place.city].filter(Boolean).join(' / ') : 'Not shared', place ? place.source + (place.isMock ? ' / SIMULATED' : '') + ' / ' + date(place.measuredAt) : '—', p?.latitude ?? 'Unavailable', p?.longitude ?? 'Unavailable', p ? p.accuracyMeters + ' m' : '—', p ? p.precision + ' / ' + p.provider + (p.isMock ? ' / SIMULATED' : '') : '—', p ? date(p.measuredAt) : '—']) row.append(node('td', value));
    return row;
  }));
  el('tickets').replaceChildren(...overview.tickets.map(t => { const b = node('button', '', 'ticket'); b.type = 'button'; b.append(node('span', t.subject), node('span', t.status + ' · ' + date(t.updated_at))); b.addEventListener('click', () => showTicket(t.id).catch(error)); return b; }));
  el('status').textContent = 'Updated ' + date(overview.measuredAt);
}
function renderSponsors(s) {
  const format = g => { try { return new Intl.NumberFormat(undefined, {style:'currency',currency:g.currency}).format(g.estimatedRevenueMicros / 1e6); } catch { return (g.estimatedRevenueMicros / 1e6).toFixed(4) + ' ' + g.currency; } };
  el('sponsor-results').replaceChildren(...(s.groups.length ? s.groups.map(g => node('p', `${g.starts} ad starts · ${g.impressions} viewable · ${g.completions} completed · ${format(g)} estimated`)) : [node('p','No paid ad plays reported.')]), node('p',`Tests: ${s.test.starts} starts · ${s.test.completions} completed · zero revenue`));
  el('sponsor-notice').textContent = s.notice;
  const c = s.config;
  for (const [id,value] of Object.entries({'sponsor-enabled':String(c.enabled),'sponsor-test':String(c.test),'sponsor-name':c.sponsor || '', 'sponsor-url':c.mediaUrl || '', 'sponsor-hash':c.sha256 || '', 'sponsor-bytes':c.bytes || '', 'sponsor-duration':c.durationMs || '', 'sponsor-currency':c.currency,'sponsor-cpm':c.cpmMicros/1e6,'sponsor-rights':String(c.rightsConfirmed === true)})) el(id).value=value;
  if (c.endsAt) { const d = new Date(c.endsAt); el('sponsor-end').value = new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16); }
}
el('sponsor-form').onsubmit = async e => {
  e.preventDefault(); const button=e.submitter; button.disabled=true;
  try {
    const data={ enabled:el('sponsor-enabled').value==='true',test:el('sponsor-test').value==='true',sponsor:el('sponsor-name').value,
      mediaUrl:el('sponsor-url').value,sha256:el('sponsor-hash').value,bytes:Number(el('sponsor-bytes').value),durationMs:Number(el('sponsor-duration').value),
      currency:el('sponsor-currency').value,cpmMicros:Math.round(Number(el('sponsor-cpm').value)*1e6),endsAt:new Date(el('sponsor-end').value).getTime(),rightsConfirmed:el('sponsor-rights').value==='true'};
    renderSponsors(await api('/admin/sponsors',{method:'PUT',body:JSON.stringify(data)}));
    el('sponsor-save-status').textContent='Saved. Cached opportunities expire within 60 seconds.';
  } catch(e) { el('sponsor-save-status').textContent=e.message; } finally {button.disabled=false;}
};
async function showTicket(id) {
  const t = await api('/admin/tickets/' + id); ticketId = id;
  el('ticket-detail').hidden = false; el('ticket-title').textContent = t.subject; el('ticket-id').textContent = 'Ticket ' + id + ' · ' + t.category;
  el('ticket-message').textContent = t.message; el('attachment').textContent = Object.keys(t.attachment).length ? JSON.stringify(t.attachment, null, 2) : 'Viewer did not attach device diagnostics.';
  el('ticket-state').value = t.status;
  el('replies').replaceChildren(...t.replies.map(r => { const div = node('div', '', 'reply'); div.append(node('strong', r.author + ' · ' + date(r.created_at)), node('p', r.message, 'message')); return div; }));
  el('ticket-detail').scrollIntoView({ behavior: 'smooth' });
}
el('login-form').addEventListener('submit', async e => { e.preventDefault(); if (hosted && !apiOrigin) return; accessKey = el('token').value; el('token').value = ''; try { await refresh(); } catch (e) { accessKey = ''; error(e); } });
el('refresh').addEventListener('click', () => refresh().catch(error));
el('signout').addEventListener('click', () => { accessKey = ''; overview = undefined; ticketId = undefined; for (const id of ['devices','locations','cities','tickets']) el(id).replaceChildren(); el('ticket-detail').hidden = true; for (const id of ['ticket-message','attachment','ticket-title','ticket-id']) el(id).textContent = ''; el('replies').replaceChildren(); el('reply').value = ''; el('workspace').hidden = true; el('signout').hidden = true; el('login').hidden = false; el('status').textContent = 'Dashboard locked.'; });
el('reply-form').addEventListener('submit', async e => { e.preventDefault(); try { await api('/admin/tickets/' + ticketId, { method: 'POST', body: JSON.stringify({ status: el('ticket-state').value, message: el('reply').value }) }); el('reply').value = ''; await showTicket(ticketId); await refresh(); } catch (e) { error(e); } });
el('export').addEventListener('click', () => {
  if (!overview) return;
  // Prefix formula-like values: untrusted device strings must not execute in spreadsheet apps.
  const cell = v => '"' + (/^\s*[=+@\-]|^[\t\r]/.test(String(v)) ? "'" : '') + String(v ?? '').replaceAll('"', '""') + '"';
  const rows = [['installation','product','brand','model','android','app','country','lastSeen'], ...overview.devices.map(d => [d.id,d.profile.product,d.profile.brand,d.profile.model,d.profile.osVersion,d.profile.appVersion,d.country,date(d.last_seen)])];
  const url = URL.createObjectURL(new Blob([rows.map(r => r.map(cell).join(',')).join('\r\n')], { type: 'text/csv' }));
  const a = document.createElement('a'); a.href = url; a.download = 'streamverse-recent-devices.csv'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
el('export-locations').addEventListener('click', () => {
  if (!overview) return;
  const cell = v => '"' + (/^\s*[=+@\-]|^[\t\r]/.test(String(v)) ? "'" : '') + String(v ?? '').replaceAll('"', '""') + '"';
  const rows = [['installation','country','region','city','placeSource','placeMeasuredAt','latitude','longitude','accuracyMeters','precision','provider','isMock','coordinateMeasuredAt'], ...overview.devices.map(d => {
    const p=d.location?.position, place=d.location?.place;
    return [d.id,place?.country,place?.region,place?.city,place?.source,place ? new Date(place.measuredAt).toISOString() : '',p?.latitude,p?.longitude,p?.accuracyMeters,p?.precision,p?.provider,p?.isMock,p ? new Date(p.measuredAt).toISOString() : ''];
  })];
  const url = URL.createObjectURL(new Blob([rows.map(r=>r.map(cell).join(',')).join('\r\n')],{type:'text/csv'}));
  const a=document.createElement('a'); a.href=url; a.download='streamverse-recent-locations.csv'; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
});
