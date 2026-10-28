const state = { ads: [], query: '', category: 'all', page: 1, pages: 1, total: 0 };
const $ = (selector) => document.querySelector(selector);
let selectedAd = null;

function formatPrice(value) { return new Intl.NumberFormat('ru-RU').format(value) + ' ₽'; }
function renderAds() {
  const maxPrice = Number($('#priceFilter').value || Infinity);
  const filtered = state.ads.filter(ad => Number(ad.price) <= maxPrice);
  $('#adCount').textContent = state.total;
  $('#resultHint').textContent = `${state.total} найдено`;
  $('#adsGrid').innerHTML = filtered.map(ad => `
    <article class="ad-card"><div class="ad-photo">▧</div><div class="ad-body">
      <button class="ad-title ad-title-button" data-detail-id="${ad.id}" title="Открыть объявление">${escapeHtml(ad.title)}</button>
      <p class="ad-description">${escapeHtml(ad.text)}</p>
      <div class="ad-bottom"><div><div class="price">${formatPrice(ad.price)}</div><span class="date">Продавец: ${escapeHtml(ad.seller_name)}</span></div><span class="status">${ad.status === 'sold' ? 'Продано' : escapeHtml(ad.status)}</span></div>
      <button class="details-btn" data-detail-id="${ad.id}" type="button">Подробнее</button>
      <button class="buy-btn" data-buy-id="${ad.id}" ${ad.status !== 'active' && ad.status !== 'активно' ? 'disabled' : ''}>${ad.status === 'sold' ? 'Продано' : 'Купить'}</button>
    </div></article>`).join('');
  $('#emptyState').classList.toggle('hidden', filtered.length > 0);
  $('#pagination').innerHTML = state.pages > 1 ? `<button class="page-btn" ${state.page === 1 ? 'disabled' : ''} data-page="${state.page - 1}">‹</button><span class="page-info">Страница ${state.page} из ${state.pages}</span><button class="page-btn" ${state.page === state.pages ? 'disabled' : ''} data-page="${state.page + 1}">›</button>` : '';
  document.querySelectorAll('.page-btn[data-page]').forEach(button => button.addEventListener('click', () => loadAds(Number(button.dataset.page))));
  document.querySelectorAll('.buy-btn:not(:disabled)').forEach(button => button.addEventListener('click', () => buyAd(Number(button.dataset.buyId))));
  document.querySelectorAll('[data-detail-id]').forEach(button => button.addEventListener('click', () => openAdDetails(Number(button.dataset.detailId))));
}
function escapeHtml(value) { return String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#039;','"':'&quot;'}[c])); }
async function loadAds(page = 1) {
  try {
    state.page = page;
    const params = new URLSearchParams({ page, limit: 6 });
    if (state.query) params.set('search', state.query);
    if ($('#statusFilter').value) params.set('status', $('#statusFilter').value);
    const response = await fetch(`/api/ads?${params}`); if (!response.ok) throw new Error('Не удалось загрузить объявления');
    const data = await response.json(); state.ads = data.items; state.pages = data.pages; state.total = data.total; renderAds();
  }
  catch (error) { $('#resultHint').textContent = error.message; $('#emptyState').classList.remove('hidden'); }
}
async function loadBalance() {
  const userId = localStorage.getItem('avitoUserId');
  if ($('#currentUserId').value !== (userId || '')) $('#currentUserId').value = userId || '';
  if (!userId) {
    $('#balanceValue').textContent = 'Выбери пользователя';
    $('#transactionsList').innerHTML = '<p class="muted">Выбери пользователя, чтобы увидеть операции.</p>';
    return;
  }
  const response = await fetch(`/api/users/${userId}`); const user = await response.json();
  if (!response.ok) { $('#balanceValue').textContent = 'Пользователь не найден'; return; }
  $('#balanceValue').textContent = formatPrice(user.balance);
  await loadTransactions(userId);
}
async function loadUsers() {
  const response = await fetch('/api/users'); const users = await response.json();
  $('#currentUserId').innerHTML = '<option value="">Выбери пользователя</option>' + users.map(user => `<option value="${user.id}">${escapeHtml(user.name)} · #${user.id}</option>`).join('');
  const saved = localStorage.getItem('avitoUserId');
  if (saved && users.some(user => String(user.id) === saved)) $('#currentUserId').value = saved;
}
async function loadTransactions(userId) {
  const box = $('#transactionsList');
  const response = await fetch(`/api/transactions?user_id=${userId}`); const rows = await response.json();
  if (!response.ok || rows.length === 0) { box.innerHTML = '<p class="muted">Операций пока нет.</p>'; return; }
  box.innerHTML = rows.map(tx => {
    const isPurchase = Number(tx.buyer_id) === Number(userId);
    const otherPerson = isPurchase ? tx.seller_name : tx.buyer_name;
    return `<article class="transaction-row"><div class="transaction-icon ${isPurchase ? 'purchase' : 'sale'}">${isPurchase ? '−' : '+'}</div><div class="transaction-info"><strong>${escapeHtml(tx.advertisement_title)}</strong><span>${isPurchase ? 'Куплено у' : 'Продано пользователю'}: ${escapeHtml(otherPerson)}</span><small>${new Date(tx.created_at).toLocaleString('ru-RU')}</small></div><b class="transaction-amount ${isPurchase ? 'spent' : 'received'}">${isPurchase ? '−' : '+'}${formatPrice(tx.amount)}</b></article>`;
  }).join('');
}
function openAdDetails(adId) {
  selectedAd = state.ads.find(ad => Number(ad.id) === adId);
  if (!selectedAd) return;
  $('#detailTitle').textContent = selectedAd.title;
  $('#detailText').textContent = selectedAd.text;
  $('#detailSeller').textContent = `Продавец: ${selectedAd.seller_name}`;
  $('#detailPrice').textContent = formatPrice(selectedAd.price);
  $('#detailBuy').disabled = selectedAd.status !== 'active' && selectedAd.status !== 'активно';
  $('#detailBuy').textContent = selectedAd.status === 'sold' ? 'Уже продано' : 'Купить';
  $('#adModal').classList.remove('hidden');
}
async function buyAd(adId) {
  const ad = selectedAd || state.ads.find(item => Number(item.id) === adId);
  const buyerId = localStorage.getItem('avitoUserId');
  if (!buyerId) { $('#walletModal').classList.remove('hidden'); $('#walletMessage').textContent = 'Сначала выбери пользователя в кошельке.'; return; }
  const response = await fetch(`/api/purchases?advertisement_id=${adId}&buyer_id=${buyerId}`, { method: 'POST' });
  const data = await response.json();
  if (!response.ok) { $('#walletModal').classList.remove('hidden'); $('#walletMessage').textContent = data.detail || 'Покупка не выполнена'; return; }
  $('#adModal').classList.add('hidden');
  $('#walletModal').classList.remove('hidden');
  $('#walletMessage').textContent = `Покупка оформлена: ${ad?.title || 'объявление'}, продавец ${ad?.seller_name || 'продавец'}, ${formatPrice(data.amount)}.`;
  await loadAds(state.page); await loadBalance();
}
$('#searchBtn').addEventListener('click', () => { state.query = $('#searchInput').value.trim(); loadAds(1); });
$('#searchInput').addEventListener('keydown', event => { if (event.key === 'Enter') { state.query = event.target.value.trim(); loadAds(1); } });
$('#statusFilter').addEventListener('change', () => loadAds(1)); $('#priceFilter').addEventListener('input', renderAds);
$('#resetBtn').addEventListener('click', () => { $('#statusFilter').value = ''; $('#priceFilter').value = ''; $('#searchInput').value = ''; state.query = ''; loadAds(1); });
document.querySelectorAll('.category').forEach(button => button.addEventListener('click', () => { document.querySelector('.category.active').classList.remove('active'); button.classList.add('active'); state.category = button.dataset.category; }));
$('#openCreate').addEventListener('click', () => $('#createModal').classList.remove('hidden')); $('#closeCreate').addEventListener('click', () => $('#createModal').classList.add('hidden'));
$('#createModal').addEventListener('click', event => { if (event.target.id === 'createModal') $('#createModal').classList.add('hidden'); });
$('#profileBtn').addEventListener('click', async () => { $('#walletModal').classList.remove('hidden'); await loadUsers(); await loadBalance(); });
$('#closeWallet').addEventListener('click', () => $('#walletModal').classList.add('hidden'));
$('#walletModal').addEventListener('click', event => { if (event.target.id === 'walletModal') $('#walletModal').classList.add('hidden'); });
$('#currentUserId').addEventListener('change', event => { if (event.target.value) localStorage.setItem('avitoUserId', event.target.value); else localStorage.removeItem('avitoUserId'); loadBalance(); });
$('#topupBtn').addEventListener('click', async () => {
  const userId = $('#currentUserId').value; const amount = $('#topupAmount').value;
  if (!userId || !amount) { $('#walletMessage').textContent = 'Укажи ID пользователя и сумму.'; return; }
  const response = await fetch(`/api/users/${userId}/balance?amount=${amount}`, { method: 'POST' }); const data = await response.json();
  if (!response.ok) { $('#walletMessage').textContent = data.detail || 'Не удалось пополнить баланс'; return; }
  localStorage.setItem('avitoUserId', userId); $('#topupAmount').value = ''; $('#walletMessage').textContent = 'Баланс пополнен.'; await loadBalance();
});
$('#refreshHistory').addEventListener('click', loadBalance);
$('#closeAd').addEventListener('click', () => $('#adModal').classList.add('hidden'));
$('#adModal').addEventListener('click', event => { if (event.target.id === 'adModal') $('#adModal').classList.add('hidden'); });
$('#detailBuy').addEventListener('click', () => { if (selectedAd) buyAd(Number(selectedAd.id)); });
$('#createForm').addEventListener('submit', async event => {
  event.preventDefault();
  const form = new FormData(event.target);
  const payload = {
    owner_id: Number(form.get('owner_id')),
    title: form.get('title'),
    text: form.get('text_content'),
    price: Number(form.get('price')),
    status: 'активно',
  };
  try { const response = await fetch('/api/ads', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload) }); const data = await response.json(); if (!response.ok) throw new Error(data.detail || 'Ошибка публикации'); $('#createModal').classList.add('hidden'); event.target.reset(); await loadAds(1); }
  catch (error) { $('#formError').textContent = error.message; }
});
loadAds();
