'use strict';

const icons = {
  overview: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  people: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m20 0v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8"/><circle cx="9" cy="7" r="4"/>',
  home: '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1Z"/><path d="M9 21v-8h6v8"/>',
  shield: '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z"/><path d="m8 12 3 3 5-6"/>',
  visitors: '<rect x="3" y="6" width="18" height="15" rx="2"/><path d="M9 6V3h6v3m0 7h3m-3 4h3M6 17c0-3 6-3 6 0"/><circle cx="9" cy="11" r="2"/>',
  chart: '<path d="M4 3v18h17M8 16v-5m5 5V7m5 9V4"/>',
  link: '<rect x="3" y="8" width="6" height="8" rx="1.5"/><rect x="15" y="8" width="6" height="8" rx="1.5"/><path d="M9 12h6m-9 4v4m12-4v4M6 8V4m12 4V4"/>',
  map: '<rect x="8" y="3" width="8" height="5" rx="1"/><rect x="2" y="16" width="6" height="5" rx="1"/><rect x="16" y="16" width="6" height="5" rx="1"/><path d="M12 8v4M5 16v-4h14v4"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  chevron: '<path d="m9 5 7 7-7 7"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
  bell: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
  building: '<rect x="4" y="3" width="16" height="18" rx="1.5"/><path d="M8 7h1m6 0h1M8 11h1m6 0h1M9 21v-6h6v6"/>',
  leaf: '<path d="M20 3c-9-1-16 3-16 10 0 5 6 7 10 4 5-3 5-9 6-14ZM4 21 15 10"/>',
  warning: '<path d="m12 3 10 17H2Z"/><path d="M12 9v5m0 3h.01"/>',
  file: '<path d="M14 2H5v20h14V7l-5-5Zm0 0v5h5M8 12h8m-8 4h6"/>',
  gate: '<path d="M3 21V5h4v16m10 0V5h4v16M7 8h10m-10 5h10m-10 5h10M10 8v10m4-10v10"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  x: '<path d="m6 6 12 12M6 18 18 6"/>',
  edit: '<path d="m16 3 5 5L9 20l-6 1 1-6ZM13 6l5 5"/>',
  archive: '<rect x="3" y="3" width="18" height="5" rx="1"/><path d="M5 8v13h14V8m-9 4h4"/>',
  star: '<path d="m12 3 2.8 5.7 6.3.9-4.5 4.4 1.1 6.2-5.7-3-5.7 3 1.1-6.2L3.2 9.6l6.3-.9Z"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  refresh: '<path d="M20 10a8 8 0 0 0-14-5L3 8m0-5v5h5m-4 6a8 8 0 0 0 14 5l3-3m0 5v-5h-5"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/>',
  lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2"/>',
  camera: '<path d="M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1Z"/><circle cx="12" cy="13" r="3.5"/>',
  card: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M5.5 17c.6-1.9 1.9-2.8 3.5-2.8s2.9.9 3.5 2.8M15 9h4m-4 3h4"/>',
};
const icon = name => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${icons[name] || icons.file}</svg>`;
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const normalize = value => String(value ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase();
let units = {};
let teams = [];
const routes = [
  ['workers','Tra cứu công nhân','people'],['discipline','Đánh giá & Kỷ luật','star'],['rooms','Cư trú & Gia thuộc','home'],
  ['overview','Tổng quan công ty','overview'],['security','Kiểm soát an ninh','shield'],['visitors','Khách & Nhà thầu','visitors'],
  ['cards','Thẻ ID & QR','card'],
  ['reports','Báo cáo & Thống kê','chart'],['integration','Tích hợp App mẹ','link'],['roadmap','Sơ đồ & Lộ trình','map'],
];
const state = {data:null,unit:'all',query:'',type:'all',team:'all',status:'active',room:'',missing:false,blood:'all',quality:'all',page:1,disciplineQuery:'',disciplineStatus:'all',cardQuery:'',cardTeam:'all',cardKv:'all',cardType:'all',cardPhoto:'all',cardScopeOnly:true,cardPage:1,session:null};
const main = document.getElementById('main');
const dialog = document.getElementById('dialog');
const pageSize = 10;
let toastTimer;
let opener;
let ocrFile;
let ocrPreview;
let ocrResult;
let ocrController;
const currentRoute = () => routes.some(r => r[0] === location.hash.slice(1)) ? location.hash.slice(1) : 'workers';
const scoped = list => list.filter(item => state.unit === 'all' || item.unit_id === state.unit);
const activeWorkers = () => scoped(state.data.workers).filter(w => w.status === 'active');
const unitLabel = () => units[state.unit] || 'Toàn công ty';
const skillLabels = ['Chưa chấm','Cần đào tạo lại','Trung bình yếu','Đạt yêu cầu','Giỏi · Thao tác vững','Xuất sắc'];
const ethicsLabels = ['Chưa chấm','Cần chấn chỉnh','Vi phạm nhắc nhở','Đạt yêu cầu','Gương mẫu, trách nhiệm','Rất tốt'];
const disciplineStatuses = ['Cần chấn chỉnh','Đang theo dõi','Đang đào tạo lại','Đã có tiến bộ','Đã khắc phục xong (Đạt chuẩn)'];
const disciplineActions = ['Nhắc nhở','Khiển trách','Cảnh cáo','Đào tạo lại tay nghề','Đình chỉ tạm thời','Chuyển tổ kiểm điểm','Khác'];
const isBorrowedName = w => Boolean(w.ten_that && w.ten_ho_so && normalize(w.ten_that.trim()) !== normalize(w.ten_ho_so.trim()));
const hasImage = (w,kind) => Boolean(state.data?.images?.[w.id]?.[kind]);
function avatarMarkup(w,cls='avatar') {
  const initials=esc(w.person_id.slice(-2));
  if (!hasImage(w,'photo')) return `<span class="${cls}">${initials}</span>`;
  return `<span class="${cls} avatar-photo"><img class="avatar-img" src="/api/v1/workers/${encodeURIComponent(w.id)}/photo" alt="" loading="lazy" decoding="async" data-initials="${initials}"></span>`;
}
document.addEventListener('error', e => {
  const img=e.target;
  if (!(img instanceof HTMLImageElement)) return;
  if (img.classList.contains('id-photo-img')) {
    const button=img.closest('.id-photo');
    if (button) {
      button.disabled=true;
      button.classList.add('image-missing');
      img.replaceWith(Object.assign(document.createElement('span'),{className:'image-fallback',textContent:'Ảnh chưa tải được'}));
    }
    return;
  }
  if (!img.classList.contains('avatar-img')) return;
  const host=img.parentElement, span=document.createElement('span');
  span.className=host.className.replace(' avatar-photo','');
  span.textContent=img.dataset.initials||'';
  host.replaceWith(span);
}, true);
const needsReview = w => w.loai !== 'Gia thuộc' && Boolean((w._manuallyRated && ((w.danh_gia_ky_nang !== null && w.danh_gia_ky_nang <= 2) || (w.danh_gia_dao_duc !== null && w.danh_gia_dao_duc <= 2))) || w.ghi_chu_ky_luat || w.ngay_ky_luat || w.hinh_thuc_ky_luat || w.trang_thai_ky_luat);
function ageAt(birth,now=new Date()) {
  if (!birth) return '';
  const [year,month,day]=birth.split('-').map(Number);
  const age=now.getFullYear()-year-Number(now.getMonth()+1<month || (now.getMonth()+1===month && now.getDate()<day));
  return age>=0?String(age):'';
}
function matchesWorker(w,query) {
  const q=normalize(query.trim());
  if (!q) return true;
  const content=normalize([w.ten_that,w.ten_ho_so,w.person_id,cardCode(w),qrPayload(w),w.cmnd,w.so_dt,w.phong_o,w.to,w.unit_id,units[w.unit_id],w.nhom_mau,w.khu_vuc,w.phan_cay,w.dia_chi,w.chi_tiet_noi_o,w.so_bao_hiem,w.quan_he,w.noi_sinh,w.ghi_chu].join(' '));
  const digits=query.replace(/\D/g,'');
  return content.includes(q) || (/^[\d\s+().-]+$/.test(query.trim()) && digits.length>=3 && String(w.so_dt||'').replace(/\D/g,'').includes(digits));
}
const fmtDate = value => value ? new Intl.DateTimeFormat('vi-VN', {day:'2-digit',month:'2-digit',year:'numeric'}).format(new Date(value)) : 'Chưa cập nhật';
const fmtTime = value => new Intl.DateTimeFormat('vi-VN', {hour:'2-digit',minute:'2-digit'}).format(new Date(value));
const today = () => {const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;};
const button = (label,action,ico,style='primary',extra='') => `<button class="button ${style}" data-action="${action}" ${extra}>${ico ? icon(ico) : ''}${label}</button>`;
const badge = (text,color='') => `<span class="badge ${color}">${esc(text)}</span>`;
const empty = (title,description) => `<div class="empty-state">${icon('search')}<h3>${esc(title)}</h3><p>${esc(description)}</p></div>`;
const notice = (text,neutral=false) => `<div class="notice ${neutral?'neutral':''}">${icon('info')}<p>${text}</p></div>`;
function heading(title,description,actions='',eyebrow='KHÔNG GIAN ĐIỀU HÀNH') {
  return `<div class="page-heading"><div><div class="eyebrow">${eyebrow}</div><h1>${title}</h1><p>${description}</p></div><div class="heading-actions">${actions}</div></div>`;
}
function toast(message) {
  const el = document.getElementById('toast'); el.textContent = message; el.classList.add('show');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove('show'), 4200);
}
async function api(path,body) {
  const response = await fetch(`/api/v1/${path}`, body === undefined ? {cache:'no-store'} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if (response.status === 401) {
    location.href = `/login.html?next=${encodeURIComponent(location.pathname + location.search + location.hash)}`;
    throw new Error('Phiên đăng nhập đã hết hạn.');
  }
  let data;
  try { data = await response.json(); } catch { throw new Error('Máy chủ không trả về dữ liệu hợp lệ. Hãy thử tải lại.'); }
  if (!response.ok || data.ok === false) throw new Error(data.error || 'Không thể hoàn tất thao tác.');
  return data;
}
async function refresh() {
  state.data = await api('bootstrap');
  state.session = await api('session').catch(() => null);
  units = Object.fromEntries(state.data.directory.units.map(unit=>[unit.id,unit.name]));
  teams = state.data.directory.teams;
  document.getElementById('unit-select').innerHTML = selectOptions([['all','Toàn công ty'],...Object.entries(units)],state.unit);
  render();
  syncChrome();
}
function go(route) { if(currentRoute() === route) render(); else location.hash = route; }
function resetOcr() {
  ocrController?.abort();
  if (ocrPreview) URL.revokeObjectURL(ocrPreview);
  ocrFile=ocrPreview=ocrResult=ocrController=null;
}
function showModal(title,content,footer='') {
  resetOcr();
  if (!dialog.open) opener = document.activeElement;
  dialog.innerHTML = `<div class="dialog-head"><h2 id="dialog-title">${title}</h2><button class="icon-button" data-action="close" aria-label="Đóng hộp thoại">${icon('x')}</button></div>${content}${footer ? `<div class="dialog-footer">${footer}</div>` : ''}`;
  if (!dialog.open) dialog.showModal();
}
function closeModal() { dialog.close(); }
dialog.addEventListener('close', () => { resetOcr(); if (opener?.isConnected) opener.focus(); });
dialog.addEventListener('click', e => { if(e.target === dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom) closeModal();} });
function personCell(w) { return `<div class="person-cell">${avatarMarkup(w)}<button class="person-link" data-action="detail" data-id="${esc(w.id)}"><b>${esc(w.ten_that)}</b><small>${esc(w.person_id)} · ${esc(w.unit_id)}</small></button></div>`; }
function profileStatus(w) { return w.status === 'archived' ? badge('Đã lưu trữ','gray') : w.cmnd ? badge('Có thông tin giấy tờ') : badge('Thiếu giấy tờ','amber'); }
function typeBadge(type) { return badge(type,type === 'Gia thuộc' ? 'blue' : type === 'Khác' ? 'gray' : ''); }
function isInside(id) {
  const event = [...state.data.events].filter(e => e.worker_id === id).sort((a,b) => b.at.localeCompare(a.at))[0];
  return event?.direction === 'in';
}
function occupancy(room) { return state.data.workers.filter(w => w.status === 'active' && w.phong_o === room.id && w.unit_id === room.unit_id).length; }
const transfers = () => state.data?.transfers || [];
const pendingTransfer = id => transfers().find(t => t.worker_id === id && t.status === 'pending');
const inTransferScope = t => state.unit === 'all' || t.from_unit === state.unit || t.to_unit === state.unit;
const transferStatus = {pending:['Chờ chấp nhận','amber'],approved:['Đã chấp nhận',''],rejected:['Từ chối','gray']};
function transferBadge(status) { const [label,color]=transferStatus[status]||['Chưa rõ','gray']; return badge(label,color); }
const CARD_PREFIX = 'CRCK2';
const CARD_BATCH_LIMIT = 120;
const CARD_PER_SHEET = 4;
const cardDigits = value => { const digits=String(value ?? '').replace(/\D/g,''); return digits ? Number(digits) : 0; };
const cardNumber = w => cardDigits(w?.person_id);
const cardSerial = w => String(cardNumber(w)).padStart(3,'0');
const qrPayload = w => `C2-${String(cardNumber(w)).padStart(4,'0')}`;
function kvNumber(w) {
  const match=String(w?.khu_vuc ?? '').match(/\d+/);
  if (match) { const value=Number(match[0]); if (value>0&&value<100) return value; }
  const team=String(w?.to ?? '').match(/\d+/);
  const value=team?Number(team[0]):0;
  return value>0&&value<100?value:0;
}
const kvConfirmed = w => /\d/.test(String(w?.khu_vuc ?? ''));
const kvCode = w => `KV${kvNumber(w)}`;
const cardCode = w => `${CARD_PREFIX}-${w.unit_id}-${kvCode(w)}-${cardSerial(w)}`;
const cardScope = () => state.data?.meta?.card_scope || [];
const inCardScope = w => cardScope().includes(w.unit_id);
const localDay = value => {
  const date=new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const pad=number=>String(number).padStart(2,'0');
  return `${pad(date.getDate())}${pad(date.getMonth()+1)}${String(date.getFullYear()).slice(-2)}`;
};
const visitorDay = v => localDay(v?.created_at) || localDay(Date.now());
function visitorCode(v) {
  if (!v) return 'KH-000000-0000';
  const day=visitorDay(v);
  const same=(state.data?.visitors||[]).filter(item=>visitorDay(item)===day)
    .sort((a,b)=>String(a.created_at).localeCompare(String(b.created_at))||String(a.id).localeCompare(String(b.id)));
  const index=same.findIndex(item=>item.id===v.id);
  return `KH-${day}-${String(index<0?1:index+1).padStart(4,'0')}`;
}
const visitorExpired = v => Boolean(v?.expected) && v.expected < today();
function cardWorkers() {
  return activeWorkers()
    .filter(w=>!state.cardScopeOnly||inCardScope(w))
    .filter(w=>(state.cardType==='all'||w.loai===state.cardType)&&(state.cardTeam==='all'||w.to===state.cardTeam)&&(state.cardKv==='all'||kvCode(w)===state.cardKv)&&(state.cardPhoto==='all'||(state.cardPhoto==='yes'?hasImage(w,'photo'):!hasImage(w,'photo')))&&matchesWorker(w,state.cardQuery));
}
function cardKindLabel(w) { return w.loai==='Gia thuộc'?'THẺ GIA THUỘC':w.loai==='Khác'?'THẺ NỘI BỘ':'THẺ CÔNG NHÂN'; }
function idCardMarkup(w) {
  const issued=inCardScope(w);
  const photo=hasImage(w,'photo')
    ? `<img class="id-card-photo" src="/api/v1/workers/${encodeURIComponent(w.id)}/photo" alt="Ảnh ${esc(w.ten_that)}" loading="lazy" decoding="async">`
    : `<span class="id-card-photo card-initials">${esc(String(w.person_id ?? '').slice(-2))}</span>`;
  const rows=[['Đơn vị',units[w.unit_id]||w.unit_id],['Tổ',w.to||'Chưa cập nhật'],['Khu vực',kvConfirmed(w)?String(w.khu_vuc):`${kvCode(w)} (suy từ tổ)`],['Phòng',w.phong_o||'Chưa bố trí']];
  return `<article class="id-card${issued?'':' pending'}">
    <header class="id-card-head"><span class="id-card-brand"><img src="assets/mark.svg" alt="">C.R.C.K.2<small>APHIVATH</small></span><span class="id-card-kind">${cardKindLabel(w)}<small>${issued?'CÔNG TY · NỘI BỘ':'CHỜ THỐNG NHẤT'}</small></span></header>
    <div class="id-card-body"><div class="id-card-photo-wrap">${photo}</div><div class="id-card-info"><h3>${esc(w.ten_that)}</h3><p class="id-card-code">${esc(cardCode(w))}</p><dl>${rows.map(([term,value])=>`<div><dt>${esc(term)}</dt><dd>${esc(value)}</dd></div>`).join('')}</dl></div></div>
    <div class="id-card-foot">${QRCode.svg(qrPayload(w),{margin:1,label:`Mã QR ${qrPayload(w)}`})}<div class="id-card-qr-text"><b>${esc(qrPayload(w))}</b><small>Quét để mở hồ sơ trong App</small><small>Thẻ nội bộ · xuất trình khi ra/vào</small></div></div>
  </article>`;
}
function visitorPassMarkup(v) {
  const code=visitorCode(v), expired=visitorExpired(v)||v.status==='left';
  const rows=[['Công ty',v.company||'Chưa cập nhật'],['Đơn vị đến',units[v.unit_id]||v.unit_id||'—'],['Người đón',v.host||'—'],['Mục đích',v.purpose||'—']];
  return `<article class="id-card visitor${expired?' expired':''}">
    <header class="id-card-head"><span class="id-card-brand"><img src="assets/mark.svg" alt="">C.R.C.K.2<small>APHIVATH</small></span><span class="id-card-kind">THẺ KHÁCH<small>${expired?'HẾT HẠN':'CÓ HIỆU LỰC TRONG NGÀY'}</small></span></header>
    <div class="id-card-body"><div class="id-card-info"><h3>${esc(v.name)}</h3><p class="id-card-code">${esc(code)}</p><dl>${rows.map(([term,value])=>`<div><dt>${esc(term)}</dt><dd>${esc(value)}</dd></div>`).join('')}<div class="visitor-expiry"><dt>Hạn thẻ</dt><dd>Hết ngày ${esc(fmtDate(v.expected))}</dd></div></dl></div></div>
    <div class="id-card-foot">${QRCode.svg(code,{margin:1,label:`Mã QR ${code}`})}<div class="id-card-qr-text"><b>${esc(code)}</b><small>Chỉ dùng một lần tại cổng</small><small>Hết ngày ${esc(fmtDate(v.expected))}</small></div></div>
  </article>`;
}
function cardModal(id) {
  const w=state.data.workers.find(item=>item.id===id);
  if(!w) return toast('Không tìm thấy hồ sơ để xem thẻ.');
  showModal('Thẻ nhận diện',`<div class="dialog-body"><div class="card-viewer">${idCardMarkup(w)}</div><p class="form-note">Mã in ${esc(cardCode(w))}; QR chỉ chứa ${esc(qrPayload(w))} nên không lộ thông tin cá nhân.</p></div>`,`${inCardScope(w)?button('In thẻ','print-card','file','secondary',`data-id="${esc(w.id)}"`):''}${button('Quay lại hồ sơ','detail','arrow','secondary',`data-id="${esc(w.id)}"`)}${button('Đóng','close',null,'primary')}`);
}
function metric(title,value,suffix,foot,ico) { return `<article class="metric"><div class="metric-title">${title}<span class="metric-icon">${icon(ico)}</span></div><strong class="metric-value">${value}<small>${suffix}</small></strong><div class="metric-foot">${foot}</div></article>`; }
function metrics() {
  const list=activeWorkers(), rooms=scoped(state.data.rooms), employed=list.filter(w=>w.loai==='Lao động').length, family=list.filter(w=>w.loai==='Gia thuộc').length;
  return `<div class="metrics">${metric('Hồ sơ lao động',employed,'người','<b>Đang hoạt động</b> · '+unitLabel(),'people')}${metric('Gia thuộc',family,'người','Liên kết theo hồ sơ & phòng ở','visitors')}${metric('Phòng đang sử dụng',rooms.filter(r=>occupancy(r)>0).length,`/ ${rooms.length}`,'Quản lý sức chứa & cư trú','home')}${metric('Đang ở trong cổng',list.filter(w=>isInside(w.id)).length,'người','Theo nhật ký demo · không phải chấm công','shield')}</div>`;
}
function composition() {
  const list=activeWorkers(), total=list.length, employed=list.filter(w=>w.loai==='Lao động').length, family=list.filter(w=>w.loai==='Gia thuộc').length, other=total-employed-family;
  return `<section class="panel"><div class="panel-heading"><div><h2>Cơ cấu nhân sự</h2><p>Phân bố hồ sơ đang hoạt động</p></div>${badge(unitLabel(),'gray')}</div><div class="chart-layout"><div class="donut" style="--workers:${total ? employed/total*100 : 0}%;--family:${total ? (employed+family)/total*100 : 0}%" role="img" aria-label="${employed} lao động, ${family} gia thuộc, ${other} khác"><div class="donut-inner"><strong>${total}</strong><small>Tổng hồ sơ</small></div></div><div>${[['Lao động',employed,''],['Gia thuộc',family,'family'],['Khác',other,'other']].map(([name,count,cls])=>`<div class="legend-row"><span class="legend-label"><i class="legend-dot ${cls}"></i>${name}</span><span><b>${count}</b><small>${total?Math.round(count/total*100):0}%</small></span></div>`).join('')}</div></div><div class="panel-bottom">${icon('leaf')}Số liệu minh họa · cập nhật từ cơ sở dữ liệu cục bộ</div></section>`;
}
function attention() {
  const missing=activeWorkers().filter(w=>!w.cmnd).length, over=scoped(state.data.rooms).filter(r=>occupancy(r)>r.capacity).length;
  return `<section class="panel" id="attention"><div class="panel-heading"><h2>Việc cần chú ý</h2>${badge('Kiểm tra dữ liệu','amber')}</div><div class="attention-list">${[
    ['file',`${missing} hồ sơ thiếu giấy tờ`,'Bổ sung và đối chiếu trước khi xác thực','missing'],
    ['home',`${over} phòng vượt sức chứa`,'Kiểm tra nhân khẩu và bố trí nơi ở','rooms'],
    ['link','App mẹ chưa kết nối','Cần chốt API và phân quyền liên thông','integration'],
  ].map(([ico,title,desc,action])=>`<div class="attention-item"><span class="attention-symbol">${icon(ico)}</span><div><h3>${title}</h3><p>${desc}</p></div><button class="arrow" data-action="${action}" aria-label="${title}">${icon('chevron')}</button></div>`).join('')}</div></section>`;
}
function workerTable(list,compact=false) {
  if(!list.length) return empty('Chưa tìm thấy hồ sơ','Thử một tên khác hoặc bỏ bớt bộ lọc.');
  return `<div class="table-wrap"><table><thead><tr><th>HỒ SƠ CÔNG NHÂN</th><th>PHÂN LOẠI</th><th>TỔ / ĐƠN VỊ</th><th>PHÒNG Ở</th><th>TRẠNG THÁI HỒ SƠ</th>${compact?'':'<th><span class="visually-hidden">Thao tác</span></th>'}</tr></thead><tbody>${list.map(w=>`<tr><td>${personCell(w)}</td><td>${typeBadge(w.loai)}</td><td>${esc(w.to)}<br><span class="filter-meta">${esc(w.unit_id)}</span></td><td>${esc(w.phong_o || 'Chưa bố trí')}${pendingTransfer(w.id)?`<br>${badge('Chờ nhận phòng','amber')}`:''}</td><td>${profileStatus(w)}</td>${compact?'':`<td><button class="icon-button" data-action="detail" data-id="${esc(w.id)}" aria-label="Xem ${esc(w.ten_that)}">${icon('chevron')}</button></td>`}</tr>`).join('')}</tbody></table></div>`;
}
function overview() {
  const date = new Intl.DateTimeFormat('vi-VN',{weekday:'long',day:'numeric',month:'long',year:'numeric'}).format(new Date());
  return heading('Tổng quan vận hành',`Chào bạn, cùng nắm bắt tình hình đơn vị hôm nay.`,button('<span class="export-label">Xuất báo cáo</span>','export-workers','download','secondary')+button('Thêm hồ sơ','new-worker','plus'))+
  `<div class="hero-grid"><section class="hero"><div class="eyebrow">C.R.C.K.2 APHIVATH · NỀN TẢNG QUẢN LÝ CON NGƯỜI</div><h2>Hiểu con người.<br>An tâm vận hành.</h2><p>Một không gian cho công nhân, nơi ở và an ninh.<br>Một điểm tra cứu chung cho toàn công ty.</p><a class="hero-link" href="#roadmap">Khám phá lộ trình phát triển ${icon('arrow')}</a><span class="hero-stamp">BẢN THIẾT KẾ 01</span></section><section class="integration-card"><div class="integration-top">${icon('link')} HỆ SINH THÁI PHẦN MỀM</div><h3>Độc lập vận hành.<br>Thống nhất dữ liệu.</h3><p>Kết nối PM Quản trị hợp nhất<br>qua định danh và API dùng chung.</p><a class="button" href="#integration">Xem thiết kế kết nối ${icon('arrow')}</a></section></div>`+
  metrics()+`<div class="dashboard-grid">${composition()}${attention()}</div><section class="panel"><div class="panel-heading"><div><h2>Hồ sơ gần đây</h2><p>${esc(date)} · ${unitLabel()}</p></div><a class="button text-button" href="#workers">Xem tất cả ${icon('arrow')}</a></div>${workerTable([...activeWorkers()].sort((a,b)=>b.updated_at.localeCompare(a.updated_at)).slice(0,5),true)}<div class="table-footer"><span>Hiển thị ${Math.min(activeWorkers().length,5)} / ${activeWorkers().length} hồ sơ đang hoạt động</span><span>${esc(dataCaption())}</span></div></section>`;
}
function filteredWorkers() {
  return scoped(state.data.workers).filter(w => (state.status==='all'||w.status===state.status) && (state.type==='all'||w.loai===state.type) && (state.team==='all'||w.to===state.team) && (!state.room||w.phong_o===state.room) && (!state.missing||!w.cmnd) && (state.blood==='all'||(state.blood==='unknown'?!w.nhom_mau:w.nhom_mau===state.blood)) &&
    (state.quality==='all'||(state.quality==='borrowed'&&isBorrowedName(w))||(state.quality==='phone'&&Boolean(w.so_dt))||(state.quality==='unrated'&&w.loai!=='Gia thuộc'&&!w._manuallyRated)||(state.quality==='review'&&needsReview(w))) && matchesWorker(w,state.query));
}
function ratingText(w,field) {
  if (w.loai==='Gia thuộc') return 'Không áp dụng';
  if (!w._manuallyRated) return 'Chưa đánh giá';
  return w[field]===null||w[field]===undefined?'Chưa chấm':`${w[field]}/5`;
}
function workerList(list) {
  if (!list.length) return empty('Chưa tìm thấy hồ sơ','Thử tên không dấu, số giấy tờ hoặc bỏ bớt bộ lọc.');
  return `<ul class="worker-list">${list.map(w=>`<li class="worker-row">
    <div class="worker-identity">${avatarMarkup(w)}<div><button class="person-link" data-action="detail" data-id="${esc(w.id)}"><b>${esc(w.ten_that)}</b></button><small>${esc(w.person_id)} · ${esc(w.unit_id)}</small>${isBorrowedName(w)?`<small>Tên hồ sơ: ${esc(w.ten_ho_so)}</small>`:''}<div class="worker-tags">${typeBadge(w.loai)}${w.chu_phong?badge('Chủ phòng','blue'):''}${pendingTransfer(w.id)?badge('Chờ nhận phòng','amber'):''}${!w.cmnd?badge('Thiếu CMND','amber'):''}${w.status==='archived'?badge('Đã lưu trữ','gray'):''}</div></div></div>
    <div class="worker-location"><b>${esc(units[w.unit_id]||w.unit_id)}</b><small>${esc(w.to)} · ${pendingTransfer(w.id)?`Chờ nhận phòng ${esc(pendingTransfer(w.id).to_room)}`:(w.phong_o?`Phòng ${esc(w.phong_o)}`:'Chưa bố trí phòng')}</small><small>${w.phan_cay?`Phần cây ${esc(w.phan_cay)}`:w.khu_vuc?esc(w.khu_vuc):'Chưa cập nhật khu vực'}</small></div>
    <div class="worker-contact"><b>${esc(w.so_dt||'Chưa có điện thoại')}</b><small>Nhóm máu: ${esc(w.nhom_mau||'Chưa xác định')}</small></div>
    <div class="worker-ratings"><small>Kỹ năng <b>${ratingText(w,'danh_gia_ky_nang')}</b></small><small>Kỷ luật <b>${ratingText(w,'danh_gia_dao_duc')}</b></small>${needsReview(w)?badge('Có mục theo dõi','amber'):''}</div>
    <button class="icon-button worker-open" data-action="detail" data-id="${esc(w.id)}" aria-label="Xem ${esc(w.ten_that)}">${icon('chevron')}</button>
  </li>`).join('')}</ul>`;
}
function workersResults() {
  const list=filteredWorkers(), pages=Math.max(1,Math.ceil(list.length/pageSize)); state.page=Math.min(state.page,pages);
  return `<div class="list-heading"><span><b>${list.length}</b> hồ sơ${state.room?` · Phòng ${esc(state.room)}`:''}${state.missing?' · Thiếu CMND':''}</span><span>${esc(unitLabel())}</span></div>`+workerList(list.slice((state.page-1)*pageSize,state.page*pageSize))+`<div class="table-footer"><span>${list.length?'Hiển thị '+((state.page-1)*pageSize+1)+'–'+Math.min(state.page*pageSize,list.length):'0 kết quả'}</span><span class="pagination"><button class="icon-button" data-action="prev" aria-label="Trang trước" ${state.page<=1?'disabled':''}>←</button>Trang ${state.page} / ${pages}<button class="icon-button" data-action="next" aria-label="Trang sau" ${state.page>=pages?'disabled':''}>→</button></span></div>`;
}
function selectOptions(options,value) { return options.map(([v,t])=>`<option value="${esc(v)}" ${v===value?'selected':''}>${esc(t)}</option>`).join(''); }
function workers() {
  const active=activeWorkers(), bloodTypes=[...new Set(scoped(state.data.workers).map(w=>w.nhom_mau).filter(Boolean))].sort();
  return `<section class="directory-hero"><div class="eyebrow">PHÂN HỆ CÔNG NHÂN & AN NINH</div><h1>Tìm đúng người. Nắm đúng thông tin.</h1><p>Tra cứu xuyên suốt toàn công ty, đến từng đơn vị, tổ và phòng ở.</p>
    <label class="search-box directory-search">${icon('search')}<input id="worker-search" type="search" autocomplete="off" placeholder="Tìm tên thật, tên hồ sơ, CMND, điện thoại, phòng ở…" aria-label="Tìm hồ sơ" value="${esc(state.query)}"><span class="search-hint">Gõ để tìm</span></label>
    <div class="directory-actions">${button('Quét CMND','scan-worker','file','primary')}${button('Thêm hồ sơ','new-worker','plus','secondary')}${button('Xuất danh sách','export-workers','download','secondary')}</div>
  </section>
  <div class="directory-summary"><button data-action="quick-filter" data-filter="all"><b>${active.length}</b> Tổng hồ sơ</button><button data-action="quick-filter" data-filter="Lao động"><b>${active.filter(w=>w.loai==='Lao động').length}</b> Lao động</button><button data-action="quick-filter" data-filter="Gia thuộc"><b>${active.filter(w=>w.loai==='Gia thuộc').length}</b> Gia thuộc</button><button data-action="missing"><b>${active.filter(w=>!w.cmnd).length}</b> Thiếu CMND</button><button data-action="open-discipline"><b>${active.filter(needsReview).length}</b> Cần theo dõi</button></div>
  <section class="panel directory-panel"><div class="filters"><select id="type-filter" aria-label="Loại hồ sơ">${selectOptions([['all','Tất cả phân loại'],['Lao động','Lao động'],['Gia thuộc','Gia thuộc'],['Khác','Khác']],state.type)}</select><select id="team-filter" aria-label="Tổ lao động">${selectOptions([['all','Tất cả tổ'],...teams.map(t=>[t,t])],state.team)}</select><select id="blood-filter" aria-label="Nhóm máu">${selectOptions([['all','Nhóm máu: tất cả'],['unknown','Chưa rõ nhóm máu'],...bloodTypes.map(t=>[t,t])],state.blood)}</select><select id="quality-filter" aria-label="Thông tin cần lọc">${selectOptions([['all','Thông tin: tất cả'],['borrowed','Có tên hồ sơ khác'],['phone','Có điện thoại'],['unrated','Chưa đánh giá'],['review','Có mục theo dõi']],state.quality)}</select><select id="status-filter" aria-label="Trạng thái hồ sơ">${selectOptions([['active','Đang hoạt động'],['archived','Đã lưu trữ'],['all','Tất cả trạng thái']],state.status)}</select>${button('Bỏ lọc','reset-filters',null,'secondary')}</div><div id="workers-results" aria-live="polite">${workersResults()}</div></section>
  <p class="demo-caption">${isImported()?`${dataCaption()} · ${active.length} hồ sơ đang hoạt động.`:`Dữ liệu minh họa · ${Object.keys(units).length} đơn vị mẫu, không phải toàn bộ danh mục công ty · Không nhập thông tin cá nhân thật.`}</p>`;
}
function disciplineWorkers() {
  return activeWorkers().filter(w=>needsReview(w) && (state.disciplineStatus==='all'||w.trang_thai_ky_luat===state.disciplineStatus) && (matchesWorker(w,state.disciplineQuery)||normalize([w.ghi_chu_ky_luat,w.nguoi_lap_bien_ban,w.hinh_thuc_ky_luat].join(' ')).includes(normalize(state.disciplineQuery.trim()))));
}
function disciplineResults() {
  const list=disciplineWorkers();
  return `<div class="list-heading"><span><b>${list.length}</b> hồ sơ theo dõi</span><span>${esc(unitLabel())}</span></div>`+(list.length?`<div class="table-wrap"><table><thead><tr><th>HỒ SƠ</th><th>KỸ NĂNG / KỶ LUẬT</th><th>GHI NHẬN</th><th>TRẠNG THÁI</th><th>PHỤ TRÁCH</th><th>THAO TÁC</th></tr></thead><tbody>${list.map(w=>`<tr><td>${personCell(w)}</td><td>${ratingText(w,'danh_gia_ky_nang')} / ${ratingText(w,'danh_gia_dao_duc')}</td><td>${fmtDate(w.ngay_ky_luat)}<br><small>${esc(w.hinh_thuc_ky_luat||'Chưa ghi hình thức')}</small></td><td>${badge(w.trang_thai_ky_luat||'Cần xem xét','amber')}</td><td>${esc(w.nguoi_lap_bien_ban||'Chưa phân công')}</td><td>${button('Xem / cập nhật','edit-worker','edit','secondary',`data-id="${esc(w.id)}"`)}</td></tr>`).join('')}</tbody></table></div>`:empty('Chưa có hồ sơ phù hợp','Hồ sơ có điểm thấp hoặc ghi nhận theo dõi sẽ xuất hiện ở đây.'));
}
function discipline() {
  return heading('Đánh giá & Kỷ luật','Theo dõi kỹ năng, ý thức lao động và kế hoạch khắc phục theo đơn vị.',button('Xuất sổ theo dõi','export-discipline','download','secondary')+button('Chọn hồ sơ','choose-review-worker','plus'),'CHẤT LƯỢNG LAO ĐỘNG · TOÀN CÔNG TY')+
    notice('Điểm kỹ năng thấp chỉ là nhu cầu đào tạo, <b>không tự động kết luận vi phạm kỷ luật</b>. Người quản lý ghi nhận và xác nhận; gia thuộc không thuộc sổ này.',true)+
    `<section class="panel"><div class="filters"><label class="search-box">${icon('search')}<input id="discipline-search" type="search" placeholder="Tìm người, nội dung, cán bộ phụ trách…" aria-label="Tìm sổ theo dõi" value="${esc(state.disciplineQuery)}"></label><select id="discipline-status" aria-label="Trạng thái theo dõi">${selectOptions([['all','Mọi trạng thái'],...disciplineStatuses.map(s=>[s,s])],state.disciplineStatus)}</select></div><div id="discipline-results" aria-live="polite">${disciplineResults()}</div></section>`;
}
function rooms() {
  const rooms=scoped(state.data.rooms);
  return heading('Cư trú & Gia thuộc','Quản lý phòng ở, nhân khẩu và sức chứa theo từng đơn vị.',button('Xuất cư trú','export-rooms','download','secondary')+button('Chuyển phòng ở','new-transfer','home','primary'),'KHÔNG GIAN SỐNG')+
  `<div class="metrics">${metric('Phòng đang có người',rooms.filter(r=>occupancy(r)>0).length,`/ ${rooms.length}`,'Theo hồ sơ đang hoạt động','home')}${metric('Tổng người cư trú',activeWorkers().filter(w=>w.phong_o).length,'người','Bao gồm lao động & gia thuộc','people')}${metric('Phòng vượt sức chứa',rooms.filter(r=>occupancy(r)>r.capacity).length,'phòng','Cần kiểm tra và điều chỉnh','warning')}${metric('Chưa bố trí phòng',activeWorkers().filter(w=>!w.phong_o).length,'người','Theo trường thông tin phòng ở','file')}</div>`+
  notice(isImported()?'Sức chứa được suy ra từ dữ liệu nhập (tối thiểu 6 chỗ/phòng), không phải sức chứa thực tế. Số người cùng phòng không tự động đồng nghĩa với quan hệ gia đình.':'Sức chứa trong demo là cấu hình minh họa. Số người cùng phòng không tự động đồng nghĩa với quan hệ gia đình.',true)+
  `<section class="panel"><div class="panel-heading"><div><h2>Sơ đồ phòng ở</h2><p>Chọn một phòng để xem danh sách cư trú</p></div>${badge(`${rooms.length} phòng`,'gray')}</div><div class="room-grid">${rooms.map(r=>{const n=occupancy(r), over=n>r.capacity;return `<button class="room-card ${over?'over':''}" data-action="room-detail" data-id="${esc(r.id)}"><div class="room-card-head"><h3>${esc(r.id)}</h3>${icon('home')}</div><p>${esc(units[r.unit_id])}</p>${badge(over?'Vượt sức chứa':n===0?'Phòng trống':'Đang sử dụng',over?'amber':n===0?'gray':'')}<div class="occupancy-bar"><span style="width:${Math.min(100,n/r.capacity*100)}%"></span></div><small>${n} người / ${r.capacity} chỗ · Xem hồ sơ →</small></button>`;}).join('')}</div></section>`+
  transferPanel();
}
function transferPanel() {
  const pending=transfers().filter(t=>t.status==='pending'&&inTransferScope(t));
  const decided=transfers().filter(t=>t.status!=='pending'&&inTransferScope(t)).slice(0,5);
  const name=id=>state.data.workers.find(w=>w.id===id)?.ten_that||'Hồ sơ ngoài danh sách';
  const head='<thead><tr><th>HỒ SƠ</th><th>TỪ PHÒNG</th><th>PHÒNG ĐÍCH</th><th>GHI CHÚ</th><th>THỜI ĐIỂM</th><th>TRẠNG THÁI</th></tr></thead>';
  const row=t=>`<tr><td>${esc(name(t.worker_id))}<br><span class="filter-meta">${esc(t.from_unit)} · ${esc(t.from_team)}</span></td><td>${esc(t.from_room||'Chưa rõ')}</td><td>${esc(t.to_room)}<br><span class="filter-meta">${esc(units[t.to_unit]||t.to_unit)}</span></td><td>${esc(t.note||'—')}</td><td>${fmtDate(t.created_at)}<br><span class="filter-meta">${fmtTime(t.created_at)}</span></td><td>${transferBadge(t.status)}</td></tr>`;
  return `<section class="panel"><div class="panel-heading"><div><h2>Chờ chấp nhận chuyển phòng</h2><p>Hồ sơ đã rời phòng cũ và chờ phân quyền App mẹ xác nhận</p></div>${badge(`${pending.length} yêu cầu`,'amber')}</div>${pending.length?`<div class="table-wrap"><table>${head}<tbody>${pending.map(row).join('')}</tbody></table></div>`:'<p class="demo-caption" style="padding:0 21px 18px">Chưa có yêu cầu nào đang chờ. Dùng nút “Chuyển phòng ở” để tạo yêu cầu.</p>'}${decided.length?`<div class="panel-heading"><div><h2>Đã xử lý gần đây</h2><p>5 yêu cầu mới nhất trong phạm vi đang xem</p></div></div><div class="table-wrap"><table>${head}<tbody>${decided.map(row).join('')}</tbody></table></div>`:''}</section>`;
}
function eventTable(events) {
  if (!events.length) return empty('Chưa có nhật ký ra/vào','Ghi nhận một lượt vào hoặc ra để bắt đầu theo dõi.');
  return `<div class="table-wrap"><table><thead><tr><th>THỜI GIAN</th><th>NGƯỜI QUA CỔNG</th><th>ĐƠN VỊ</th><th>ĐIỂM KIỂM SOÁT</th><th>CHIỀU</th><th>PHƯƠNG THỨC</th></tr></thead><tbody>${events.map(e=>`<tr><td>${fmtTime(e.at)}<br><span class="filter-meta">${fmtDate(e.at)}</span></td><td><b>${esc(e.name)}</b><br><span class="filter-meta">${esc(e.person_id)}</span></td><td>${esc(e.unit_id)}</td><td>${esc(e.gate)}</td><td>${badge(e.direction==='in'?'Vào cổng':'Ra cổng',e.direction==='in'?'':'blue')}</td><td>${badge('Ghi nhận thủ công','gray')}</td></tr>`).join('')}</tbody></table></div>`;
}
function security() {
  const events=scoped(state.data.events), active=activeWorkers();
  return heading('Kiểm soát an ninh','Nắm bắt ra/vào, đối chiếu danh tính và lưu dấu thao tác.',button('Ghi nhận ra/vào','new-event','plus'),'AN NINH ĐƠN VỊ')+
  notice('<b>Chế độ thí điểm thủ công.</b> Chưa kết nối camera, Face ID, máy quét QR hoặc thanh chắn. Nhật ký này không được tự động dùng để tính công.')+
  `<div class="metrics">${metric('Đang ở trong cổng',active.filter(w=>isInside(w.id)).length,'người','Theo sự kiện gần nhất','people')}${metric('Lượt vào hôm nay',events.filter(e=>e.direction==='in'&&new Date(e.at).toDateString()===new Date().toDateString()).length,'lượt','Ghi nhận trên bản demo','gate')}${metric('Lượt ra hôm nay',events.filter(e=>e.direction==='out'&&new Date(e.at).toDateString()===new Date().toDateString()).length,'lượt','Ghi nhận trên bản demo','arrow')}${metric('Khách đang ở trong',scoped(state.data.visitors).filter(v=>v.status==='inside').length,'người','Theo sổ khách minh họa','visitors')}</div>`+
  `<div class="gate-grid">${['Cổng chính','Cổng khu ở'].map(g=>`<section class="gate-card"><span class="gate-symbol">${icon('gate')}</span><div><h3>${g}</h3><p>${events.filter(e=>e.gate===g).length} sự kiện trong nhật ký</p>${badge('Chưa kết nối thiết bị','amber')}</div>${button('Ghi nhận','new-event','plus','secondary',`data-gate="${g}"`)}</section>`).join('')}</div><section class="panel"><div class="panel-heading"><div><h2>Nhật ký ra/vào</h2><p>Không chỉnh sửa hoặc xóa sự kiện đã ghi nhận</p></div>${button('Xuất nhật ký','export-events','download','text-button')}</div>${eventTable(events)}</section>`;
}
const visitorStatus = {registered:'Đã đăng ký',inside:'Đang ở trong',left:'Đã rời đi'};
function visitors() {
  const list=scoped(state.data.visitors);
  return heading('Khách & Nhà thầu','Đăng ký trước, xác nhận người đón, kiểm soát thời điểm ra/vào.',button('Đăng ký khách','new-visitor','plus'),'AN NINH ĐƠN VỊ')+
  notice('Luồng demo: <b>Đã đăng ký → Đang ở trong → Đã rời đi</b>. Nhân viên bảo vệ đối chiếu giấy tờ thực tế trước khi xác nhận.',true)+
  `<section class="panel"><div class="panel-heading"><div><h2>Sổ khách đến đơn vị</h2><p>${list.length} lượt đăng ký · ${unitLabel()}</p></div><a class="button text-button" href="#cards">Thẻ khách & QR ${icon('arrow')}</a></div>${list.length?`<div class="table-wrap"><table><thead><tr><th>KHÁCH / ĐƠN VỊ</th><th>MÃ KHÁCH</th><th>MỤC ĐÍCH</th><th>NGƯỜI ĐÓN</th><th>NGÀY DỰ KIẾN</th><th>TRẠNG THÁI</th><th>THAO TÁC</th></tr></thead><tbody>${list.map(v=>`<tr><td><b>${esc(v.name)}</b><br><span class="filter-meta">${esc(v.company)} · ${esc(v.unit_id)}</span></td><td class="mono">${esc(visitorCode(v))}<br><span class="filter-meta">${visitorExpired(v)?'Đã hết hạn':'Còn hiệu lực'}</span></td><td>${esc(v.purpose)}</td><td>${esc(v.host)}</td><td>${fmtDate(v.expected)}</td><td>${badge(visitorStatus[v.status],v.status==='registered'?'amber':v.status==='left'?'gray':'')}</td><td><div class="row-actions">${button('In thẻ','print-visitor','card','secondary',`data-id="${esc(v.id)}"`)}${v.status==='left'?'<span class="filter-meta">Đã hoàn tất</span>':button(v.status==='registered'?'Xác nhận vào':'Xác nhận ra','visitor-confirm','check','secondary',`data-id="${esc(v.id)}"`)}</div></td></tr>`).join('')}</tbody></table></div>`:empty('Chưa có khách đăng ký','Thêm lượt đăng ký đầu tiên bằng nút “Đăng ký khách”.')}</section>`;
}
const cardPageSize = 12;
function cardKvOptions() {
  return [...new Set(activeWorkers().map(kvCode))].sort((a,b)=>Number(a.slice(2))-Number(b.slice(2))).map(value=>[value,value]);
}
function cardTile(w) {
  return `<div class="card-tile">${idCardMarkup(w)}<div class="card-tile-actions">${button('In thẻ','print-card','file','secondary',`data-id="${esc(w.id)}"`)}${button('Mở hồ sơ','detail','arrow','secondary',`data-id="${esc(w.id)}"`)}</div>${inCardScope(w)?'':`<p class="card-note">Chưa thống nhất phạm vi phát hành · chỉ xem trước</p>`}</div>`;
}
function cardsResults() {
  const list=cardWorkers(), pages=Math.max(1,Math.ceil(list.length/cardPageSize));
  state.cardPage=Math.min(state.cardPage,pages);
  const start=(state.cardPage-1)*cardPageSize;
  const body=list.length
    ? `<div class="card-grid">${list.slice(start,start+cardPageSize).map(cardTile).join('')}</div><div class="table-footer"><span>Hiển thị ${start+1}–${Math.min(start+cardPageSize,list.length)} / ${list.length} thẻ</span><span class="pagination"><button class="icon-button" data-action="cards-prev" aria-label="Trang trước" ${state.cardPage<=1?'disabled':''}>←</button>Trang ${state.cardPage} / ${pages}<button class="icon-button" data-action="cards-next" aria-label="Trang sau" ${state.cardPage>=pages?'disabled':''}>→</button></span></div>`
    : empty('Chưa có thẻ phù hợp','Đổi bộ lọc hoặc chọn “Tất cả đơn vị” để xem trước thẻ của Nhà máy và các Đội chưa thống nhất.');
  return `<div class="list-heading"><span><b>${list.length}</b> thẻ theo bộ lọc</span><span>${esc(unitLabel())}</span></div>${body}`;
}
function visitorPassPanel() {
  const list=scoped(state.data.visitors);
  const active=list.filter(v=>!visitorExpired(v)&&v.status!=='left').length;
  return `<section class="panel"><div class="panel-heading"><div><h2>Thẻ khách</h2><p>Mã cấp theo ngày đăng ký · hết hạn cuối ngày dự kiến</p></div>${button(`In ${active} thẻ còn hiệu lực`,'print-visitor-passes','visitors','secondary')}</div>${list.length?`<div class="table-wrap"><table><thead><tr><th>MÃ THẺ KHÁCH</th><th>KHÁCH</th><th>ĐƠN VỊ ĐẾN</th><th>NGƯỜI ĐÓN</th><th>HẠN THẺ</th><th>TRẠNG THÁI</th><th>THAO TÁC</th></tr></thead><tbody>${list.map(v=>{const expired=visitorExpired(v);return `<tr><td class="mono">${esc(visitorCode(v))}</td><td><b>${esc(v.name)}</b><br><span class="filter-meta">${esc(v.company)}</span></td><td>${esc(units[v.unit_id]||v.unit_id)}</td><td>${esc(v.host)}</td><td>${fmtDate(v.expected)}</td><td>${expired?badge('Hết hạn','gray'):badge(visitorStatus[v.status],v.status==='registered'?'amber':'')}</td><td>${button('In thẻ','print-visitor','card','secondary',`data-id="${esc(v.id)}"`)}</td></tr>`;}).join('')}</tbody></table></div>`:empty('Chưa có khách đăng ký','Đăng ký khách ở mục “Khách & Nhà thầu” để cấp thẻ có hạn ngày.')}</section>`;
}
function cards() {
  const inScope=activeWorkers().filter(inCardScope);
  const printable=cardWorkers().filter(inCardScope).length;
  const withoutPhoto=inScope.filter(w=>!hasImage(w,'photo')).length;
  const kvInferred=inScope.filter(w=>!kvConfirmed(w)).length;
  const visitors=scoped(state.data.visitors), visitorsToday=visitors.filter(v=>visitorDay(v)===localDay(Date.now()));
  return heading('Thẻ ID & QR','Mỗi công nhân, gia thuộc và khách có mã in riêng và mã QR mở đúng hồ sơ.',
    button(`In ${Math.min(printable,CARD_BATCH_LIMIT)} thẻ`,'print-cards','download','primary')+button('Xuất mã thẻ','export-cards','download','secondary'),'NHẬN DIỆN & RA/VÀO')+
  notice(`Mã thẻ: <b>CRCK2-[đơn vị]-[khu vực]-[3 số]</b>. QR chỉ chứa mã cố định <b>C2-xxxx</b>, không có tên, CMND hay điện thoại. Phạm vi đã thống nhất: <b>${cardScope().join(', ')||'chưa cấu hình'}</b>; Nhà máy và các Đội còn lại sẽ chốt sau. Mỗi tờ A4 in ${CARD_PER_SHEET} thẻ A7 (74×105 mm) kèm đường cắt.`)+
  `<div class="metrics">${metric('Thẻ đủ điều kiện',inScope.length,'thẻ',`4 Đội đã thống nhất · ${unitLabel()}`,'card')}${metric('Thiếu ảnh chân dung',withoutPhoto,'hồ sơ','Thẻ vẫn in được với chữ viết tắt','camera')}${metric('Khu vực suy từ tổ',kvInferred,'hồ sơ','Cần xác nhận lại khu vực thực tế','map')}${metric('Thẻ khách cấp hôm nay',visitorsToday.length,'thẻ','Hết hạn cuối ngày dự kiến','visitors')}</div>`+
  `<section class="panel"><div class="panel-heading"><div><h2>Xem trước thẻ A7</h2><p>Chọn tổ, khu vực và phân loại để lọc trước khi in</p></div>${badge(`${CARD_PREFIX} · C2`, 'gray')}</div><div class="filters card-filters"><label class="search-box">${icon('search')}<input id="card-search" type="search" autocomplete="off" placeholder="Tìm tên, C2-0001, KV2-001…" aria-label="Tìm thẻ" value="${esc(state.cardQuery)}"></label><select id="card-team-filter" aria-label="Tổ">${selectOptions([['all','Tất cả tổ'],...teams.map(t=>[t,t])],state.cardTeam)}</select><select id="card-kv-filter" aria-label="Khu vực">${selectOptions([['all','Tất cả khu vực'],...cardKvOptions()],state.cardKv)}</select><select id="card-type-filter" aria-label="Phân loại">${selectOptions([['all','Tất cả phân loại'],['Lao động','Lao động'],['Gia thuộc','Gia thuộc'],['Khác','Khác']],state.cardType)}</select><select id="card-photo-filter" aria-label="Ảnh chân dung">${selectOptions([['all','Ảnh: tất cả'],['yes','Có ảnh chân dung'],['no','Chưa có ảnh']],state.cardPhoto)}</select><select id="card-scope-filter" aria-label="Phạm vi phát hành">${selectOptions([['yes','Đã thống nhất (4 Đội)'],['all','Tất cả đơn vị']],state.cardScopeOnly?'yes':'all')}</select>${button('Bỏ lọc','reset-card-filters',null,'secondary')}</div><div id="cards-results" aria-live="polite">${cardsResults()}</div></section>`+
  visitorPassPanel()+
  `<p class="demo-caption">QR đọc được bằng camera điện thoại; bản này chưa nối máy quét tại cổng. Không in thẻ cho hồ sơ đã lưu trữ.</p>`;
}
function reports() {
  const list=activeWorkers();
  return heading('Báo cáo & Thống kê','Một nguồn số liệu, từ hồ sơ đến vận hành đơn vị.',button('In báo cáo','print','file','secondary'),'THÔNG TIN ĐIỀU HÀNH')+metrics()+
  `<div class="report-grid">${[['people','Danh sách hồ sơ','Hồ sơ theo bộ lọc đơn vị, gồm mã định danh, phân loại, tổ và phòng ở.','export-workers'],['home','Tình hình cư trú','Sức chứa, số người hiện tại và trạng thái từng phòng ở.','export-rooms'],['shield','Nhật ký an ninh','Thời gian, điểm kiểm soát, người qua cổng và chiều ra/vào.','export-events']].map(([ico,title,desc,action])=>`<section class="panel report-card">${icon(ico)}<h2>${title}</h2><p>${desc}</p>${button('Tải CSV · mở bằng Excel',action,'download','secondary')}</section>`).join('')}</div><div class="dashboard-grid">${composition()}<section class="panel"><div class="panel-heading"><div><h2>Độ đầy đủ dữ liệu</h2><p>Có thông tin không đồng nghĩa đã xác thực</p></div></div>${[['Giấy tờ','cmnd'],['Ngày sinh','ngay_sinh'],['Phòng ở','phong_o'],['Liên hệ','so_dt']].map(([label,key])=>{const n=list.filter(w=>w[key]).length,p=list.length?Math.round(n/list.length*100):0;return `<div class="progress-row"><span>${label}</span><div class="progress-track"><span style="width:${p}%"></span></div><b>${p}%</b></div>`;}).join('')}</section></div>`;
}
function integration() {
  const outbox=scoped(state.data.outbox), pending=outbox.filter(e=>e.status==='pending');
  return heading('Một menu trong PM Quản trị hợp nhất','Phạm vi toàn công ty. Nghiệp vụ độc lập, trải nghiệm nằm trong App mẹ.',button('Tải hợp đồng API','export-contract','download','secondary'),'THIẾT KẾ TÍCH HỢP · CHƯA LIÊN THÔNG')+
  notice('<b>Khung menu hiện tại là bản mô phỏng để duyệt.</b> Chưa có mã nguồn App mẹ, đăng nhập dùng chung hoặc API liên thông. Bộ lọc đơn vị không phải cơ chế phân quyền.')+
  `<section class="panel parent-contract"><div class="panel-heading"><h2>App mẹ → Công nhân & An ninh → Tra cứu toàn công ty</h2>${badge('Một điểm truy cập','gray')}</div><div class="checklist"><p>${icon('people')}Mở menu là thấy ô tìm kiếm và danh sách; Mỗi đội sản xuất là một đơn vị trong công ty.</p><p>${icon('lock')}Khi tích hợp thật, App mẹ cấp phiên đăng nhập; máy chủ kiểm tra quyền theo đơn vị cho mọi thao tác.</p><p>${icon('link')}Dùng chung danh mục Công ty → Đơn vị → Tổ; giữ định danh hồ sơ khi điều chuyển.</p><p>${icon('map')}Giữ tra cứu và nghiệp vụ cũ trước; triển khai an ninh, thiết bị sau khi nghiệm thu.</p></div></section><div class="connection-flow"><section class="system-card primary-system"><div class="eyebrow">PHÂN HỆ NGHIỆP VỤ</div><h2>CN Workforce</h2><p>Quản lý hồ sơ, cư trú, ra/vào và khách.</p><div class="system-entities"><span>person_id</span><span>unit_id</span><span>entity_version</span></div></section><div class="flow-arrow">${icon('link')}<small>API v1<br>Chưa nối</small></div><section class="system-card"><div class="eyebrow">NỀN TẢNG ĐIỀU HÀNH</div><h2>PM Quản trị hợp nhất</h2><p>Danh mục tổ chức, danh tính liên thông, báo cáo tổng hợp.</p><div class="system-entities"><span>Tổ chức</span><span>SSO / Phân quyền</span><span>Lương – Công</span></div></section></div>
  <div class="dashboard-grid"><section class="panel"><div class="panel-heading"><div><h2>Quy tắc trao đổi dữ liệu</h2><p>Hợp đồng đề xuất · cần thống nhất cùng App mẹ</p></div>${badge('Bản nháp','amber')}</div><div class="checklist">${['Một person_id xuyên suốt, không lấy số CMND làm khóa.','Danh mục đơn vị do App mẹ quản lý; dữ liệu nghiệp vụ do phân hệ sở hữu.','Mỗi sự kiện có event_id riêng để chống tiếp nhận trùng.','Dùng phiên bản bản ghi để phát hiện xung đột trước khi ghi đè.','Không mặc định gửi ảnh giấy tờ, sinh trắc học hay thông tin gia thuộc.'].map(t=>`<p>${icon('check')}<span>${t}</span></p>`).join('')}</div></section><section class="panel"><div class="panel-heading"><div><h2>Trạng thái kết nối</h2><p>Không phát sinh yêu cầu ra hệ thống ngoài</p></div></div><div class="checklist"><p>${icon('lock')}SSO & phân quyền: chưa triển khai</p><p>${icon('link')}API App mẹ: chưa cấu hình</p><p>${icon('clock')}${pending.length} sự kiện chờ · chỉ lưu cục bộ</p><p>${icon('shield')}TLS, chữ ký webhook, quyền dữ liệu: cần chốt</p></div></section></div>
  <section class="panel"><div class="panel-heading"><div><h2>Hàng đợi sự kiện cục bộ</h2><p>Tạo cùng giao dịch lưu hồ sơ · chưa gửi đến App mẹ</p></div>${badge(`${outbox.length} sự kiện`,'gray')}</div>${outbox.length?`<div class="table-wrap"><table><thead><tr><th>LOẠI SỰ KIỆN</th><th>ĐỊNH DANH</th><th>ĐƠN VỊ</th><th>THỜI ĐIỂM</th><th>TRẠNG THÁI</th></tr></thead><tbody>${outbox.slice(0,20).map(e=>`<tr><td>${esc(e.event_type)}</td><td>${esc(e.person_id||String(e.entity_id).slice(0,8))}</td><td>${esc(e.unit_id)}</td><td>${fmtTime(e.occurred_at)} · ${fmtDate(e.occurred_at)}</td><td>${badge('Chờ kết nối','amber')}</td></tr>`).join('')}</tbody></table></div>`:empty('Chưa có thay đổi cần gửi','Thử thêm hoặc cập nhật một hồ sơ để xem sự kiện được ghi nhận.')}</section>`;
}
const branches = [
  {title:'Hồ sơ & Vòng đời',icon:'people',sub:'Vòng đời hồ sơ · Giai đoạn 1',items:['Tra cứu toàn công ty; giữ tên thật, tên hồ sơ, nhóm máu, cư trú, kỹ năng và kỷ luật 1–5 sao.','Định danh person_id ổn định; lưu trữ thay vì xóa hồ sơ.','Tiếp theo: nhập dữ liệu gốc có đối chiếu, lịch sử điều chuyển, hợp đồng.'],route:'workers'},
  {title:'Cư trú & Gia đình',icon:'home',sub:'Nhân khẩu · Sức chứa · Giai đoạn 1',items:['Liên kết hồ sơ với phòng và đơn vị; theo dõi vượt sức chứa.','Xác minh chủ hộ và quan hệ, không tự suy diễn từ việc cùng phòng.','Tiếp theo: tạm trú, bàn giao, điện nước và tài sản.'],route:'rooms'},
  {title:'An ninh & Ra/vào',icon:'shield',sub:'Thủ công trước · Thiết bị sau',items:['Thí điểm sổ cổng và sổ khách, người vận hành xác nhận.','Sau khảo sát: QR có hạn sử dụng, phân quyền cổng và khung giờ.','Nhận diện khuôn mặt cần cơ sở pháp lý, kiểm tra thủ công và thử nghiệm sai số. Không tự kỷ luật từ AI.'],route:'security'},
  {title:'Chất lượng & AI',icon:'file',sub:'OCR Khmer · Có người xác nhận',items:['Làm sạch và đối chiếu 567 hồ sơ của bản đóng gói; không công khai dữ liệu thật.','OCR Latin/Việt/Khmer chạy trong trình duyệt, xác nhận trước khi điền; dịch Khmer–Việt bằng AI chưa triển khai.','Ảnh giấy tờ lưu tách mã nguồn, chỉ cấp quyền cần thiết; có chính sách lưu và xóa.'],route:'reports'},
  {title:'App mẹ & Định danh',icon:'link',sub:'API · SSO · Dữ liệu dùng chung',items:['Thống nhất Công ty → Đơn vị → Tổ và mã người dùng chung.','Phân hệ sở hữu hồ sơ/cư trú/an ninh; App mẹ quản danh mục và tổng hợp.','Chống đồng bộ trùng, xử lý xung đột, ký sự kiện và nhật ký trao đổi.'],route:'integration'},
  {title:'Công – Lương – Sản lượng',icon:'chart',sub:'Kết nối · Không làm trùng phân hệ',items:['Chia sẻ định danh với Trợ lý Lương CS và Lương Khai thác.','Nhật ký vào cổng không tương đương ngày công hoặc sản lượng.','Tổ trưởng → Đơn vị → Kế toán → Ban TGĐ duyệt theo nghiệp vụ App mẹ.'],route:'integration'},
  {title:'Bảo mật & Vận hành',icon:'lock',sub:'Phân quyền · Sao lưu · Kiểm toán',items:['Bắt buộc đăng nhập và phân quyền trước khi chạy dữ liệu thật trên mạng.','Bảo vệ chỉ xem thông tin tối thiểu để xác minh; hạn chế giấy tờ, sức khỏe, gia thuộc.','Kiểm thử mất mạng, khôi phục sao lưu, đồng thời, lưu trữ và thu hồi quyền.'],route:'integration'},
  {title:'Nhân rộng & Điều hành',icon:'map',sub:'Đội / Nhà máy → Công ty',items:['Chuẩn hóa dữ liệu → pilot một Đội và một nhà máy → nhân rộng có nghiệm thu.','Đo thời gian tra cứu, độ đầy đủ dữ liệu, số ngoại lệ và khả năng khôi phục.','Các mốc 2027–2028 trong video là định hướng, không phải cam kết đã duyệt.'],route:'reports'},
];
function roadmap() {
  const node=(b,i)=>`<button class="map-node" data-action="branch" data-id="${i}">${icon(b.icon)}<span><b>${b.title}</b><small>${b.sub}</small></span></button>`;
  return heading('Một nền tảng. Một lộ trình rõ ràng.','Mở rộng toàn công ty, giữ trọng tâm con người và kết nối hệ sinh thái.',button('In sơ đồ','print','file','secondary'),'SƠ ĐỒ TƯ DUY MỞ RỘNG')+
  `<section class="panel"><div class="panel-heading"><div><h2>CN Workforce trong PM Quản trị hợp nhất</h2><p>Chọn một nhánh để xem phạm vi và bước tiếp theo</p></div>${badge('8 nhánh phát triển','gray')}</div><div class="roadmap-map"><div class="map-column">${branches.slice(0,4).map((b,i)=>node(b,i)).join('')}</div><div class="map-center"><img src="assets/mark.svg" alt=""><h2>Công nhân<br>& An ninh</h2><p>Một menu trong App mẹ<br>Bao quát toàn công ty</p>${badge('TOÀN CÔNG TY')}</div><div class="map-column">${branches.slice(4).map((b,i)=>node(b,i+4)).join('')}</div></div></section>
  <div class="dashboard-grid" style="margin-top:22px"><section class="panel"><div class="panel-heading"><h2>Lộ trình đề xuất & điểm nghiệm thu</h2></div>${[
  ['01','Duyệt trải nghiệm & Chuẩn hóa','Demo hiện tại · chốt UI và dữ liệu','Đang thiết kế'],['02','Vận hành thí điểm an toàn','Đăng nhập, nhập dữ liệu, sao lưu, sổ cổng','Chưa triển khai'],['03','Kết nối & Nhân rộng','API App mẹ · pilot một Đội + một nhà máy','Chưa triển khai'],['04','Tích hợp thiết bị & AI','QR / Camera sau khảo sát và đánh giá riêng tư','Chưa triển khai']
  ].map(([n,t,d,s])=>`<div class="roadmap-stage"><span class="stage-number">${n}</span><span><b>${t}</b><small>${d}</small></span>${badge(s,n==='01'?'':'gray')}</div>`).join('')}</section><section class="panel"><div class="panel-heading"><h2>Nguyên tắc triển khai</h2></div><div class="checklist"><p>${icon('check')}Giữ xanh ngọc, tìm nhanh và thao tác rõ ràng.</p><p>${icon('check')}Không sửa hoặc công khai bản dữ liệu gốc.</p><p>${icon('check')}Đánh giá mặc định không phải đánh giá thực tế.</p><p>${icon('check')}Duyệt demo rồi mới tạo repo GitHub mới; không ghi đè repo có sẵn.</p><p>${icon('check')}Không gắn nhãn “đã kết nối” cho tính năng dự kiến.</p></div></section></div>`;
}
function render() {
  if(!state.data) return;
  const route=currentRoute();
  document.getElementById('breadcrumb').textContent=routes.find(r=>r[0]===route)[1];
  document.title=`${routes.find(r=>r[0]===route)[1]} · CN Workforce`;
  document.getElementById('primary-nav').innerHTML=routes.map(([key,label,ico],i)=>`${key==='integration'?'<div class="nav-separator">HỆ THỐNG & PHÁT TRIỂN</div>':''}<a class="nav-item ${key===route?'active':''}" href="#${key}" ${key===route?'aria-current="page"':''}>${icon(ico)}<span>${label}</span>${key==='workers'?`<span class="nav-count">${activeWorkers().length}</span>`:''}</a>`).join('');
  const tabs=[['workers','Tra cứu','people'],['overview','Tổng quan','overview'],['rooms','Cư trú','home'],['cards','Thẻ ID','card'],['security','An ninh','shield']];
  document.getElementById('mobile-tabs').innerHTML=tabs.map(([key,label,ico])=>`<a href="#${key}" class="${key===route?'active':''}" ${key===route?'aria-current="page"':''}>${icon(ico)}<span>${label}</span></a>`).join('');
  main.innerHTML=({overview,workers,discipline,rooms,security,visitors,cards,reports,integration,roadmap}[route])();
}
function syncChrome() {
  const cloud=Boolean(state.session?.cloud);
  const footer=document.getElementById('footer-status');
  if(footer) footer.innerHTML=`<i class="status-dot ${cloud?'':'amber'}"></i>${cloud?'Máy chủ công ty · dữ liệu thật':'Bản cục bộ · chưa kết nối App mẹ'}`;
  const label=document.getElementById('session-label');
  if(label) label.innerHTML=cloud?'Phiên công ty<small>Đã đăng nhập · xem toàn công ty</small>':'Quản trị demo<small>Phiên cục bộ · chưa phân quyền</small>';
  const logout=document.getElementById('logout-button');
  if(logout) logout.hidden=!state.session?.required;
}
function field(label,name,value='',type='text',required=false,full=false,attrs='',maximum=200) {
  return `<label class="form-field ${full?'full':''}">${label}${required?' *':''}<input type="${type}" name="${name}" value="${esc(value)}" ${required?'required':''} maxlength="${maximum}" ${attrs}></label>`;
}
function selectField(label,name,options,value,full=false) { return `<label class="form-field ${full?'full':''}">${label}<select name="${name}">${selectOptions(options,value)}</select></label>`; }
const relationships = ['Chủ hộ','Vợ','Chồng','Vợ/chồng','Con','Bố','Mẹ','Cha','Anh','Chị','Em','Cháu','Bạn','Con dâu','Anh rể','Anh vợ','Dì','Bà ngoại','1 mình','Khác'];
function relationshipOptions(value) { return (value && !relationships.includes(value) ? [value,...relationships] : relationships).map(v=>[v,v]); }
function isImported() { return Boolean(state.data && state.data.mode === 'imported'); }
function dataCaption() {
  if (state.session?.cloud) return 'Dữ liệu công ty trên máy chủ nội bộ · chỉ chia sẻ trong công ty';
  return isImported() ? 'Dữ liệu công ty đã nhập · lưu cục bộ trên máy này' : 'Dữ liệu minh họa, không phải hồ sơ thật';
}
function roomOptions(unit) { return [['','Chưa bố trí'],...state.data.rooms.filter(r=>r.unit_id===unit).map(r=>[r.id,`${r.id} · ${occupancy(r)}/${r.capacity} người`])]; }
function ratingGroup(label,name,value,labels) {
  return `<fieldset class="rating-group"><legend>${label}</legend><div class="rating-choices">${['',1,2,3,4,5].map(n=>`<label title="${esc(labels[Number(n)])}"><input type="radio" name="${name}" value="${n}" ${(value??'')===n?'checked':''}><span>${n===''?'Chưa chấm':`${n}${icon('star')}`}</span></label>`).join('')}</div><small>1 · ${labels[1]} / 3 · Đạt yêu cầu / 5 · ${labels[5]}</small></fieldset>`;
}
function workerForm(id,scan=false) {
  const w=state.data.workers.find(w=>w.id===id) || {loai:'Lao động',unit_id:state.unit==='all'?'':state.unit,to:teams[0],quan_he:'Khác',gioi_tinh:'',phong_o:'',danh_gia_ky_nang:3,danh_gia_dao_duc:3,_manuallyRated:false};
  showModal(id?'Chỉnh sửa hồ sơ công nhân':'Thêm hồ sơ công nhân',`<form id="worker-form" data-id="${esc(id||'')}" data-version="${w.version||''}"><div class="dialog-body">
    <p class="form-note">Phạm vi toàn công ty · Chọn đúng đơn vị quản lý. ${isImported()?'Dữ liệu công ty đã nhập.':'Chỉ sử dụng thông tin và ảnh minh họa.'}</p>
    <details class="ocr-panel" id="ocr-panel" ${scan?'open':''}><summary>${icon('file')}Quét CMND / CCCD · Điền nhanh hồ sơ<span>Trên máy</span></summary><div class="ocr-body"><p>Ảnh chỉ được đọc trong trình duyệt, không gửi lên máy chủ hay AI bên ngoài. Kết quả cần kiểm tra; không tự xác thực danh tính.</p><div class="ocr-toolbar"><div class="ocr-sources"><label class="button primary ocr-camera">${icon('camera')}Chụp ảnh<input id="ocr-camera" type="file" accept="image/*" capture="environment" hidden></label><label class="button secondary ocr-upload">${icon('file')}Chọn ảnh có sẵn<input id="ocr-file" type="file" accept="image/*" hidden></label></div><label class="form-field">Ngôn ngữ đọc<select id="ocr-language"><option value="vie+eng">Tiếng Việt + Latin (khuyến nghị)</option><option value="eng">Chỉ chữ Latin / MRZ</option><option value="khm+eng">Tiếng Khmer + Latin</option></select></label></div><p class="form-note">Chụp thẳng mặt trước, đủ sáng, không lóa là đọc tốt nhất. PNG, JPEG, WebP · tối đa 10 MB. Bộ đọc chạy trên máy, không dịch và không gửi ảnh đi đâu; ảnh không lưu kèm hồ sơ.</p><div class="ocr-controls">${button('Đọc ảnh trên máy','ocr-read','file','primary','type="button" disabled')}${button('Dừng đọc','ocr-cancel',null,'secondary','type="button" hidden')}<a href="assets/ocr-sample.png" download="anh-mau-quyet-cmnd.png" class="button secondary">Tải ảnh mẫu</a></div><img id="ocr-preview" alt="Ảnh minh họa đang đối chiếu" hidden><p id="ocr-status" role="status" aria-live="polite">Chọn hoặc chụp ảnh để bắt đầu.</p><div id="ocr-results"></div></div></details>
    <h3 class="form-section-title">01 · Danh tính & liên hệ</h3><div class="form-grid">${field('Tên thật / tên hiển thị','ten_that',w.ten_that,'text',true)}${field('Tên trên hồ sơ','ten_ho_so',w.ten_ho_so)}${field('Số CMND / CCCD','cmnd',w.cmnd)}${field('Điện thoại / liên hệ','so_dt',w.so_dt,'tel')}${field('Ngày sinh','ngay_sinh',w.ngay_sinh,'date',false,false,`max="${today()}"`)}${selectField('Giới tính','gioi_tinh',[['','Chưa cập nhật'],['M','Nam'],['F','Nữ']],w.gioi_tinh)}${field('Nơi sinh','noi_sinh',w.noi_sinh,'text',false,false,'',500)}<label class="form-field">Tuổi (tính theo ngày sinh)<input id="worker-age" readonly value="${ageAt(w.ngay_sinh)}" placeholder="Chưa có ngày sinh"></label>${field('Địa chỉ thường trú','dia_chi',w.dia_chi,'text',false,true,'',500)}</div>
    <h3 class="form-section-title">02 · Đơn vị, lao động & cư trú</h3><div class="form-grid">${selectField('Đơn vị quản lý *','unit_id',[['','Chọn đơn vị'],...Object.entries(units)],w.unit_id)}${selectField('Phân loại','loai',[['Lao động','Lao động'],['Gia thuộc','Gia thuộc'],['Khác','Khác']],w.loai)}${selectField('Tổ','to',teams.map(t=>[t,t]),w.to)}${field('Khu vực','khu_vuc',w.khu_vuc)}${field('Phần cây hiện tại','phan_cay',w.phan_cay)}${field('Số bảo hiểm','so_bao_hiem',w.so_bao_hiem)}${selectField('Phòng ở','phong_o',roomOptions(w.unit_id),w.phong_o)}${selectField('Quan hệ cư trú','quan_he',relationshipOptions(w.quan_he),w.quan_he)}${field('Chi tiết nơi ở','chi_tiet_noi_o',w.chi_tiet_noi_o,'text',false,true,'',500)}<label class="check-field full"><input type="checkbox" name="chu_phong" ${w.chu_phong?'checked':''}> Là chủ phòng / đầu mối phòng ở</label></div>
    <h3 class="form-section-title">03 · Nhóm máu</h3><div class="form-grid"><label class="form-field">Nhóm máu<input name="nhom_mau" list="blood-types" value="${esc(w.nhom_mau)}" maxlength="8" placeholder="Chưa xác định"><datalist id="blood-types">${['O','A','B','AB','O+','O-','A+','A-','B+','B-','AB+','AB-','RH-'].map(v=>`<option value="${v}">`).join('')}</datalist></label><p class="form-note">Chỉ ghi theo thông tin đã đối chiếu. Không suy ra từ CMND; không dùng trường này thay cho xét nghiệm y tế.</p></div>
    <h3 class="form-section-title">04 · Kỹ năng & Đạo đức – Kỷ luật</h3>${selectField('Trạng thái đánh giá','_manuallyRated',[['false','Chưa đánh giá · mức mặc định 3/5'],['true','Đã có đánh giá của người quản lý']],String(Boolean(w._manuallyRated)))}<p id="dependent-note" class="form-note" ${w.loai==='Gia thuộc'?'':'hidden'}>Gia thuộc không chấm sao hoặc ghi nhận kỷ luật.</p><fieldset id="evaluation-fields" class="plain-fieldset">${ratingGroup('Kỹ năng lao động','danh_gia_ky_nang',w.danh_gia_ky_nang,skillLabels)}${ratingGroup('Đạo đức & Kỷ luật','danh_gia_dao_duc',w.danh_gia_dao_duc,ethicsLabels)}</fieldset>
    <fieldset id="discipline-fields" class="plain-fieldset"><legend>Ghi nhận theo dõi / đào tạo / kỷ luật</legend><div class="form-grid">${field('Ngày ghi nhận','ngay_ky_luat',w.ngay_ky_luat,'date',false,false,`max="${today()}"`)}${selectField('Hình thức xử lý','hinh_thuc_ky_luat',[['','Chưa chọn'],...disciplineActions.map(s=>[s,s])],w.hinh_thuc_ky_luat||'')}${selectField('Trạng thái theo dõi','trang_thai_ky_luat',[['','Chưa ghi nhận'],...disciplineStatuses.map(s=>[s,s])],w.trang_thai_ky_luat||'')}${field('Cán bộ / quản lý phụ trách','nguoi_lap_bien_ban',w.nguoi_lap_bien_ban)}<label class="form-field full">Nội dung ghi nhận / kế hoạch đào tạo<textarea name="ghi_chu_ky_luat" maxlength="2000">${esc(w.ghi_chu_ky_luat)}</textarea></label></div></fieldset>
    <h3 class="form-section-title">05 · Ghi chú</h3><label class="form-field">Thông tin bổ sung<textarea name="ghi_chu" maxlength="2000">${esc(w.ghi_chu)}</textarea></label><div class="form-error" role="alert"></div></div><div class="dialog-footer">${button('Hủy','close',null,'secondary','type="button"')}<button class="button primary" type="submit">${icon('check')}Lưu hồ sơ</button></div></form>`);
  dialog.querySelector('[name="unit_id"]').required=true;
  syncWorkerControls();
}
function syncWorkerControls() {
  const form=document.getElementById('worker-form');
  if (!form) return;
  const dependent=form.elements.loai.value==='Gia thuộc';
  form.elements._manuallyRated.disabled=dependent;
  document.getElementById('evaluation-fields').disabled=dependent||form.elements._manuallyRated.value!=='true';
  document.getElementById('discipline-fields').disabled=dependent;
  document.getElementById('dependent-note').hidden=!dependent;
  form.elements.chu_phong.disabled=dependent||!form.elements.phong_o.value;
  if (form.elements.chu_phong.disabled) form.elements.chu_phong.checked=false;
}
function idPhotos(w) {
  const items=[];
  if(hasImage(w,'photo')) items.push(`<button class="id-photo" data-action="open-image" data-id="${esc(w.id)}" data-kind="photo"><img class="id-photo-img" src="/api/v1/workers/${encodeURIComponent(w.id)}/photo" alt="Chân dung ${esc(w.ten_that)}" loading="lazy" decoding="async"><span>${icon('people')}Chân dung</span></button>`);
  if(hasImage(w,'cmnd')) items.push(`<button class="id-photo" data-action="open-image" data-id="${esc(w.id)}" data-kind="cmnd"><img class="id-photo-img" src="/api/v1/workers/${encodeURIComponent(w.id)}/cmnd" alt="Ảnh giấy tờ của ${esc(w.ten_that)}" loading="lazy" decoding="async"><span>${icon('file')}Ảnh giấy tờ</span></button>`);
  if(!items.length) return '';
  return `<section class="id-photos"><div class="id-photo-grid">${items.join('')}</div><p class="form-note">Ảnh từ kho Drive nội bộ · hiển thị để đối chiếu thủ công, không nhận diện khuôn mặt.</p></section>`;
}
function imageViewer(id,kind) {
  const w=state.data.workers.find(item=>item.id===id); if(!w) return;
  const label=kind==='photo'?'Chân dung':'Ảnh giấy tờ';
  showModal(`${label} · ${esc(w.ten_that)}`,`<div class="dialog-body"><div class="image-viewer"><img src="/api/v1/workers/${encodeURIComponent(w.id)}/${kind==='cmnd'?'cmnd':'photo'}" alt="${label} của ${esc(w.ten_that)}"></div>${notice('Đối chiếu thủ công với người thực tế. Hệ thống không chấm điểm khuôn mặt và không tự xác thực danh tính.',true)}</div>`,button('Quay lại hồ sơ','detail',null,'secondary',`data-id="${esc(w.id)}"`)+button('Đóng','close',null,'primary'));
}
function detail(id) {
  const w=state.data.workers.find(w=>w.id===id); if(!w) return;
  const rating=(key,labels)=>w.loai==='Gia thuộc'?'Không áp dụng':!w._manuallyRated?'Mặc định 3/5 · Chưa đánh giá':w[key]===null?'Chưa chấm':`<span class="stars" aria-label="${w[key]} trên 5 sao">${Array.from({length:w[key]},()=>icon('star')).join('')}</span><br>${esc(labels[w[key]])}`;
  const fields=[['Mã liên thông',w.person_id],['Mã thẻ in',cardCode(w)],['Mã QR (cố định)',qrPayload(w)],['Đơn vị',units[w.unit_id]],['Phân loại',w.loai],['Tổ',w.to],['Tên trên hồ sơ',w.ten_ho_so],['CMND / CCCD',w.cmnd],['Ngày sinh',fmtDate(w.ngay_sinh)],['Tuổi',ageAt(w.ngay_sinh)],['Giới tính',w.gioi_tinh==='M'?'Nam':w.gioi_tinh==='F'?'Nữ':''],['Nơi sinh',w.noi_sinh],['Điện thoại',w.so_dt],['Nhóm máu',w.nhom_mau||'Chưa xác định'],['Khu vực',w.khu_vuc],['Phần cây',w.phan_cay],['Số bảo hiểm',w.so_bao_hiem],['Phòng ở',w.phong_o],['Vai trò phòng ở',w.chu_phong?'Chủ phòng':'Thành viên'],['Quan hệ cư trú',w.quan_he],['Chi tiết nơi ở',w.chi_tiet_noi_o],['Địa chỉ thường trú',w.dia_chi]];
  showModal('Hồ sơ công nhân',`<div class="dialog-body"><div class="profile-top">${avatarMarkup(w,'avatar profile-avatar')}<div><h3>${esc(w.ten_that)}</h3>${profileStatus(w)}<p>${esc(w.person_id)} · Phiên bản ${w.version}</p></div></div>${pendingTransfer(w.id)?`<section class="profile-review"><h3>Chờ nhận phòng ${esc(pendingTransfer(w.id).to_room)}</h3><p>Từ phòng ${esc(pendingTransfer(w.id).from_room||'chưa xác định')} · Đơn vị đích ${esc(units[pendingTransfer(w.id).to_unit]||pendingTransfer(w.id).to_unit)}</p><p>Hồ sơ đã rời phòng cũ và đang chờ phân quyền App mẹ xác nhận.</p>${pendingTransfer(w.id).note?`<p class="preserve-lines">${esc(pendingTransfer(w.id).note)}</p>`:''}</section>`:''}<section class="profile-card"><div class="profile-card-head"><h3>Thẻ nhận diện</h3>${inCardScope(w)?badge('Trong phạm vi phát hành'):badge('Chờ thống nhất phạm vi','amber')}</div><div class="profile-card-row"><p class="mono profile-card-code">${esc(cardCode(w))}</p>${button('Xem thẻ','view-card','card','secondary',`data-id="${esc(w.id)}"`)}</div><p class="form-note">QR chỉ chứa ${esc(qrPayload(w))}; mở thẻ để xem hoặc in.</p></section>${idPhotos(w)}<dl class="profile-grid">${fields.map(([t,v])=>`<div><dt>${t}</dt><dd>${esc(v||'Chưa cập nhật')}</dd></div>`).join('')}<div><dt>Kỹ năng lao động</dt><dd>${rating('danh_gia_ky_nang',skillLabels)}</dd></div><div><dt>Đạo đức & Kỷ luật</dt><dd>${rating('danh_gia_dao_duc',ethicsLabels)}</dd></div><div><dt>Trạng thái cổng</dt><dd>${isInside(w.id)?'Đang ở trong':'Không có lượt vào đang mở'}</dd></div></dl>${needsReview(w)?`<section class="profile-review"><h3>Theo dõi & khắc phục</h3><p>${esc(w.trang_thai_ky_luat||'Cần xem xét')} · ${fmtDate(w.ngay_ky_luat)}</p><p>${esc(w.hinh_thuc_ky_luat||'Chưa ghi hình thức')} · ${esc(w.nguoi_lap_bien_ban||'Chưa phân công')}</p><p class="preserve-lines">${esc(w.ghi_chu_ky_luat||'Chưa ghi nội dung')}</p></section>`:''}${w.ghi_chu?`<p class="preserve-lines">${esc(w.ghi_chu)}</p>`:''}${notice('Ảnh quét không lưu kèm hồ sơ. Có số giấy tờ hoặc kết quả OCR không đồng nghĩa đã xác minh danh tính.',true)}</div>`,`${w.status==='active'?button('Lưu trữ','archive-confirm','archive','danger',`data-id="${esc(id)}"`):''}${w.status==='active'?button('In thẻ','print-card','card','secondary',`data-id="${esc(id)}"`):''}${button('Đóng','close',null,'secondary')}${w.status==='active'?button('Chỉnh sửa','edit-worker','edit','primary',`data-id="${esc(id)}"`):''}`);
}
const ocrFields = {ten_that:'Tên thật',cmnd:'Số CMND / CCCD',ngay_sinh:'Ngày sinh',gioi_tinh:'Giới tính',noi_sinh:'Nơi sinh',dia_chi:'Địa chỉ thường trú'};
function ocrResultsMarkup(result,existing) {
  const entries=Object.entries(result.fields).filter(([key,value])=>Object.hasOwn(ocrFields,key)&&value);
  return `<h4>Kết quả đọc · Chưa điền / chưa lưu</h4><p>Đối chiếu và sửa từng giá trị. Trường đang có dữ liệu mặc định không được chọn để tránh ghi đè.</p>${entries.length?`<label class="check-field"><input id="ocr-select-all" type="checkbox">Chọn tất cả trường đọc được</label>`:''}${entries.map(([key,value])=>`<label class="ocr-result-row"><input type="checkbox" data-ocr-field="${key}" ${existing[key]?'':'checked'}><span>${ocrFields[key]}<small>Hiện tại: ${esc(existing[key]||'Trống')}</small></span><input data-ocr-value="${key}" aria-label="Kết quả OCR ${ocrFields[key]}" value="${esc(value)}" maxlength="${key==='dia_chi'||key==='noi_sinh'?500:200}"></label>`).join('')}${entries.length?'':'<p>Chưa tách được trường đáng tin cậy. Chụp lại thẳng và đủ sáng, chọn ngôn ngữ “Tiếng Việt + Latin”, rồi xem văn bản bên dưới để nhập tay.</p>'}<details><summary>Văn bản nhận diện</summary><pre class="ocr-raw">${esc(result.text)}</pre></details><label class="check-field" id="ocr-confirm-row"><input id="ocr-confirm" type="checkbox">Tôi đã đối chiếu các trường được chọn với ảnh.</label>${button('Điền các trường đã chọn','ocr-apply','check','primary',`type="button" ${entries.length?'':'disabled'}`)}`;
}
const ocrStages = [
  ['loading tesseract core','Đang tải bộ đọc (lần đầu vài MB)…'],
  ['initializing tesseract','Đang khởi động bộ đọc…'],
  ['initialized tesseract','Đã khởi động bộ đọc…'],
  ['loading language traineddata','Đang tải dữ liệu ngôn ngữ (lần đầu vài MB)…'],
  ['loaded language traineddata','Đã tải dữ liệu ngôn ngữ…'],
  ['initializing api','Đang chuẩn bị nhận dạng…'],
  ['initialized api','Đang nhận dạng…'],
  ['recognizing text','Đang đọc chữ…'],
];
function ocrProgressText(progress) {
  if (typeof progress==='string') return progress;
  const status=String(progress?.status||''),stage=ocrStages.find(([key])=>status.startsWith(key));
  const percent=Math.round((Number(progress?.progress)||0)*100);
  return `${stage?stage[1]:'Đang xử lý ảnh…'}${percent>0&&percent<100?` ${percent}%`:''}`;
}
function setOcrInputs(disabled) {
  for(const id of ['ocr-file','ocr-camera']){const input=document.getElementById(id);if(input) input.disabled=disabled;}
}
async function readDocument() {
  if (!ocrFile||ocrController) return;
  const form=document.getElementById('worker-form'),status=document.getElementById('ocr-status');
  const controller=new AbortController();ocrController=controller;ocrResult=null;
  document.getElementById('ocr-results').innerHTML='';
  form.querySelector('[data-action="ocr-read"]').disabled=true;
  form.querySelector('[data-action="ocr-cancel"]').hidden=false;
  setOcrInputs(true);
  document.getElementById('ocr-language').disabled=true;
  status.textContent='Đang chuẩn bị công cụ đọc trên máy…';
  try {
    const result=await window.DocumentOCR.recognize(ocrFile,document.getElementById('ocr-language').value,progress=>{
      if (form.isConnected&&!controller.signal.aborted) status.textContent=ocrProgressText(progress);
    },controller.signal);
    if (!form.isConnected||controller.signal.aborted) return;
    ocrResult=result;
    status.textContent='Đã đọc ảnh. Kiểm tra kết quả trước khi điền vào hồ sơ.';
    const existing=Object.fromEntries(Object.keys(ocrFields).map(key=>[key,form.elements[key].value]));
    document.getElementById('ocr-results').innerHTML=ocrResultsMarkup(result,existing);
  } catch(error) {
    if (form.isConnected) status.textContent=controller.signal.aborted?'Đã dừng đọc; chưa thay đổi hồ sơ.':`Không đọc được ảnh: ${error.message}`;
  } finally {
    if (form.isConnected) {
      form.querySelector('[data-action="ocr-read"]').disabled=false;
      form.querySelector('[data-action="ocr-cancel"]').hidden=true;
      setOcrInputs(false);
      document.getElementById('ocr-language').disabled=false;
    }
    if (ocrController===controller) ocrController=null;
  }
}
function applyDocument() {
  const form=document.getElementById('worker-form');
  if (!ocrResult||!form) return;
  const status=document.getElementById('ocr-status');
  if (!document.getElementById('ocr-confirm').checked) {
    const row=document.getElementById('ocr-confirm-row');
    row.classList.add('needs-check');
    row.scrollIntoView({block:'center'});
    document.getElementById('ocr-confirm').focus();
    status.textContent='Hãy tích “Tôi đã đối chiếu…” rồi bấm lại để điền.';
    return;
  }
  const changes=[];
  for (const check of form.querySelectorAll('[data-ocr-field]:checked')) {
    const key=check.dataset.ocrField,value=form.querySelector(`[data-ocr-value="${key}"]`).value.trim();
    const input=form.elements[key],old=input.value;
    input.value=value;
    const valid=input.value===value&&input.checkValidity();
    input.value=old;
    if (!valid) {status.textContent=`${ocrFields[key]} chưa hợp lệ. Sửa kết quả rồi thử lại; chưa điền trường nào.`;return;}
    changes.push([input,value]);
  }
  for (const [input,value] of changes) input.value=value;
  document.getElementById('worker-age').value=ageAt(form.elements.ngay_sinh.value);
  if (changes.length) {
    status.textContent=`Đã điền ${changes.length} trường vào bản nháp. Kiểm tra rồi bấm “Lưu hồ sơ”.`;
    changes[0][0].scrollIntoView({block:'center'});
  } else status.textContent='Chưa chọn trường nào để điền. Tích ô bên cạnh từng trường cần điền.';
}
function eventForm(gate='Cổng chính') {
  const list=activeWorkers();
  showModal('Ghi nhận ra/vào thủ công',`<form id="event-form"><div class="dialog-body">${notice('Người vận hành cần đối chiếu danh tính. Thao tác này chỉ ghi nhật ký demo, không điều khiển thiết bị.')}<div class="form-grid">${selectField('Chọn hồ sơ','worker_id',list.map(w=>[w.id,`${w.person_id} · ${w.ten_that} · ${isInside(w.id)?'Đang trong':'Đang ngoài'}`]),list[0]?.id,true)}${selectField('Chiều qua cổng','direction',[['in','Vào cổng'],['out','Ra cổng']],'in')}${selectField('Điểm kiểm soát','gate',[['Cổng chính','Cổng chính'],['Cổng khu ở','Cổng khu ở']],gate)}</div><div class="form-error" role="alert"></div></div><div class="dialog-footer">${button('Hủy','close',null,'secondary','type="button"')}<button class="button primary" type="submit" ${list.length?'':'disabled'}>${icon('check')}Xác nhận ghi nhận</button></div></form>`);
}
function visitorForm() {
  showModal('Đăng ký khách đến đơn vị',`<form id="visitor-form"><div class="dialog-body"><div class="form-grid">${field('Họ tên khách minh họa','name','','text',true)}${field('Công ty / đơn vị','company','','text',true)}${selectField('Đơn vị đến','unit_id',Object.entries(units),state.unit==='all'?'DSX02':state.unit)}${field('Người đón','host','','text',true)}${field('Ngày dự kiến','expected',today(),'date',true)}${field('Mục đích đến','purpose','','text',true,true)}</div><p class="form-note">Chỉ đăng ký thông tin minh họa. Nhân viên bảo vệ xác nhận riêng khi khách thực sự vào hoặc ra.</p><div class="form-error" role="alert"></div></div><div class="dialog-footer">${button('Hủy','close',null,'secondary','type="button"')}<button class="button primary" type="submit">${icon('check')}Lưu đăng ký</button></div></form>`);
}
function transferForm() {
  const list=activeWorkers().filter(w=>w.phong_o);
  if(!list.length) return toast('Chưa có hồ sơ nào đang có phòng ở để chuyển.');
  const first=list[0], unit=state.unit==='all'?first.unit_id:state.unit;
  const roomList=state.data.rooms.filter(r=>r.unit_id===unit&&r.id!==first.phong_o);
  showModal('Chuyển phòng ở',`<form id="transfer-form"><div class="dialog-body">
    ${notice('Gửi yêu cầu là hồ sơ <b>rời phòng hiện tại ngay</b> và vào danh sách chờ chấp nhận. Chỉ khi phân quyền App mẹ xác nhận, hồ sơ mới được xếp vào phòng đích.')}
    <div class="form-grid">${selectField('Hồ sơ cần chuyển','worker_id',list.map(w=>[w.id,`${w.person_id} · ${w.ten_that} · Phòng ${w.phong_o}`]),first.id,true)}${selectField('Đơn vị đích','to_unit',Object.entries(units),unit)}${selectField('Phòng đích','to_room',roomList.map(r=>[r.id,`${r.id} · ${occupancy(r)}/${r.capacity} người`]),roomList[0]?.id)}${field('Lý do / ghi chú','note','','text',false,true,'',500)}</div>
    <p class="form-note">Có thể chọn phòng ở Đội khác hoặc Nhà máy chế biến. Hồ sơ đang ở trong cổng phải được ghi nhận ra cổng trước khi chuyển sang đơn vị khác.</p>
    <div class="form-error" role="alert"></div></div><div class="dialog-footer">${button('Hủy','close',null,'secondary','type="button"')}<button class="button primary" type="submit">${icon('check')}Gửi yêu cầu</button></div></form>`);
  const room= dialog.querySelector('[name="to_room"]');
  if(room.options.length) room.required=true;
}
function printSheets(cards) {
  if (!cards.length) return toast('Chưa có thẻ nào để in.');
  const area=document.getElementById('print-area');
  const sheets=[];
  for (let index=0;index<cards.length;index+=CARD_PER_SHEET) sheets.push(cards.slice(index,index+CARD_PER_SHEET));
  area.innerHTML=sheets.map(group=>`<section class="sheet">${group.join('')}</section>`).join('');
  document.body.classList.add('printing');
  window.print();
}
function resetCardFilters(values={}) {
  Object.assign(state,{cardQuery:'',cardTeam:'all',cardKv:'all',cardType:'all',cardPhoto:'all',cardScopeOnly:true,cardPage:1},values);
}
function download(name,content,type) { const url=URL.createObjectURL(new Blob([content],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000); }
function csvValue(value) { let text=String(value??'');if(/^[\s]*[=+@\-\t\r]/.test(text)) text="'"+text;return '"'+text.replace(/"/g,'""')+'"'; }
function csv(name,headers,rows) { download(`${name}-${today()}.csv`,'\uFEFF'+[headers,...rows].map(r=>r.map(csvValue).join(',')).join('\r\n'),'text/csv;charset=utf-8');toast('Đã tạo CSV minh họa theo bộ lọc hiện tại.'); }
function resetWorkerFilters(values={}) {
  Object.assign(state,{query:'',type:'all',team:'all',status:'active',room:'',missing:false,blood:'all',quality:'all',page:1},values);
}
async function action(el) {
  const type=el.dataset.action,id=el.dataset.id;
  if(type==='close') return closeModal();
  if(type==='new-worker') return workerForm();
  if(type==='scan-worker') return workerForm(undefined,true);
  if(type==='ocr-read') return readDocument();
  if(type==='ocr-cancel') return ocrController?.abort();
  if(type==='ocr-apply') return applyDocument();
  if(type==='edit-worker') return workerForm(id);
  if(type==='detail') return detail(id);
  if(type==='open-image') return imageViewer(id,el.dataset.kind);
  if(type==='view-card') return cardModal(id);
  if(type==='logout'){
    await fetch('/api/v1/session',{method:'DELETE'});
    location.href='/login.html';
    return;
  }
  if(type==='new-event') return eventForm(el.dataset.gate);
  if(type==='new-transfer') return transferForm();
  if(type==='new-visitor') return visitorForm();
  if(type==='print-card'){
    const w=state.data.workers.find(item=>item.id===id);
    if(!w) return toast('Không tìm thấy hồ sơ để in thẻ.');
    if(!inCardScope(w)) return toast('Nhà máy và các Đội này chưa thống nhất phạm vi phát hành thẻ.');
    if(dialog.open) closeModal();
    return printSheets([idCardMarkup(w)]);
  }
  if(type==='print-cards'){
    const list=cardWorkers().filter(inCardScope);
    if(!list.length) return toast('Chưa có thẻ trong phạm vi đã thống nhất để in.');
    if(list.length>CARD_BATCH_LIMIT) return toast(`Đang có ${list.length} thẻ. Lọc theo tổ hoặc khu vực để in tối đa ${CARD_BATCH_LIMIT} thẻ mỗi lần.`);
    return printSheets(list.map(idCardMarkup));
  }
  if(type==='print-visitor'){
    const v=state.data.visitors.find(item=>item.id===id);
    if(!v) return toast('Không tìm thấy khách để in thẻ.');
    return printSheets([visitorPassMarkup(v)]);
  }
  if(type==='print-visitor-passes'){
    const list=scoped(state.data.visitors).filter(v=>!visitorExpired(v)&&v.status!=='left');
    if(!list.length) return toast('Không có thẻ khách còn hiệu lực để in.');
    if(list.length>CARD_BATCH_LIMIT) return toast(`Đang có ${list.length} thẻ khách. Lọc theo đơn vị để in tối đa ${CARD_BATCH_LIMIT} thẻ mỗi lần.`);
    return printSheets(list.map(visitorPassMarkup));
  }
  if(type==='cards-prev'||type==='cards-next'){state.cardPage+=type==='cards-next'?1:-1;document.getElementById('cards-results').innerHTML=cardsResults();return;}
  if(type==='reset-card-filters'){resetCardFilters();render();return;}
  if(type==='export-cards') return csv('ma-the-nhan-dien',['Mã thẻ in','Mã QR','Họ tên','Phân loại','Đơn vị','Tổ','Khu vực gốc','KV in trên thẻ','Phòng','Có ảnh chân dung','Phạm vi phát hành'],cardWorkers().map(w=>[cardCode(w),qrPayload(w),w.ten_that,w.loai,w.unit_id,w.to,w.khu_vuc,kvCode(w),w.phong_o,hasImage(w,'photo')?'Có':'Không',inCardScope(w)?'Đã thống nhất':'Chờ thống nhất']));
  if(type==='open-discipline') return go('discipline');
  if(type==='choose-review-worker'){resetWorkerFilters({type:'Lao động'});go('workers');return;}
  if(type==='quick-filter'){resetWorkerFilters({type:el.dataset.filter});render();return;}
  if(type==='prev'||type==='next'){state.page+=type==='next'?1:-1;document.getElementById('workers-results').innerHTML=workersResults();return;}
  if(type==='reset-filters'){resetWorkerFilters();render();return;}
  if(type==='missing'){resetWorkerFilters({missing:true});go('workers');return;}
  if(type==='room-detail'){const room=state.data.rooms.find(r=>r.id===id);resetWorkerFilters({unit:room.unit_id,room:id});document.getElementById('unit-select').value=state.unit;go('workers');return;}
  if(type==='rooms'||type==='integration') return go(type);
  if(type==='print') return window.print();
  if(type==='retry') return refresh();
  if(type==='export-workers'){
    const rows=currentRoute()==='workers'?filteredWorkers():activeWorkers();
    return csv(isImported()?'ho-so-cong-ty':'ho-so-minh-hoa',['Mã hồ sơ','Tên thật','Tên hồ sơ','Đơn vị','Phân loại','Tổ','CMND / CCCD','Ngày sinh','Giới tính','Nơi sinh','Điện thoại','Nhóm máu','Khu vực','Phần cây','Số bảo hiểm','Phòng','Chủ phòng','Quan hệ','Chi tiết nơi ở','Địa chỉ','Kỹ năng','Đạo đức & Kỷ luật','Đã đánh giá','Ngày kỷ luật','Hình thức','Trạng thái theo dõi','Phụ trách','Nội dung theo dõi','Ghi chú','Trạng thái hồ sơ'],rows.map(w=>[w.person_id,w.ten_that,w.ten_ho_so,w.unit_id,w.loai,w.to,w.cmnd,w.ngay_sinh,w.gioi_tinh,w.noi_sinh,w.so_dt,w.nhom_mau,w.khu_vuc,w.phan_cay,w.so_bao_hiem,w.phong_o,w.chu_phong?'Có':'Không',w.quan_he,w.chi_tiet_noi_o,w.dia_chi,ratingText(w,'danh_gia_ky_nang'),ratingText(w,'danh_gia_dao_duc'),w._manuallyRated?'Có':'Không',w.ngay_ky_luat,w.hinh_thuc_ky_luat,w.trang_thai_ky_luat,w.nguoi_lap_bien_ban,w.ghi_chu_ky_luat,w.ghi_chu,w.status]));
  }
  if(type==='export-discipline') return csv('theo-doi-lao-dong',['Mã hồ sơ','Họ tên','Đơn vị','Tổ','Kỹ năng','Đạo đức & Kỷ luật','Ngày ghi nhận','Hình thức','Trạng thái','Phụ trách','Nội dung'],disciplineWorkers().map(w=>[w.person_id,w.ten_that,w.unit_id,w.to,ratingText(w,'danh_gia_ky_nang'),ratingText(w,'danh_gia_dao_duc'),w.ngay_ky_luat,w.hinh_thuc_ky_luat,w.trang_thai_ky_luat,w.nguoi_lap_bien_ban,w.ghi_chu_ky_luat]));
  if(type==='export-rooms') return csv(isImported()?'cu-tru-cong-ty':'cu-tru-minh-hoa',['Phòng','Đơn vị','Sức chứa','Số người','Vượt sức chứa'],scoped(state.data.rooms).map(r=>[r.id,r.unit_id,r.capacity,occupancy(r),occupancy(r)>r.capacity?'Có':'Không']));
  if(type==='export-events') return csv(isImported()?'nhat-ky-cong-ty':'nhat-ky-minh-hoa',['Thời gian','Mã hồ sơ','Tên','Đơn vị','Cổng','Chiều','Phương thức'],scoped(state.data.events).map(e=>[e.at,e.person_id,e.name,e.unit_id,e.gate,e.direction,'Thủ công']));
  if(type==='export-contract'){const contract=await api('contract');download('cn-workforce-api-draft.json',JSON.stringify(contract,null,2),'application/json');toast('Đã tải hợp đồng đề xuất, chưa có kết nối thật.');return;}
  if(type==='branch'){const b=branches[Number(id)];showModal(esc(b.title),`<div class="dialog-body">${badge(b.sub,'gray')}<ul class="detail-list">${b.items.map(t=>`<li>${esc(t)}</li>`).join('')}</ul></div>`,button('Đóng','close',null,'secondary')+button('Xem phân hệ','branch-go','arrow','primary',`data-route="${b.route}"`));return;}
  if(type==='branch-go'){closeModal();return go(el.dataset.route);}
  if(type==='archive-confirm'){
    const w=state.data.workers.find(w=>w.id===id);
    showModal('Lưu trữ hồ sơ',`<form id="archive-form" data-id="${esc(id)}" data-version="${w.version}"><div class="dialog-body"><p>Bạn muốn lưu trữ <b>${esc(w.ten_that)}</b> (${esc(w.person_id)})?</p><p>Hồ sơ không bị xóa, sẽ rời danh sách đang hoạt động và được giải phóng phòng ở. Nếu còn lượt vào đang mở, cần ghi nhận ra cổng trước.</p><div class="form-error" role="alert"></div></div><div class="dialog-footer">${button('Giữ hồ sơ','close',null,'secondary','type="button"')}<button class="button danger" type="submit">Xác nhận lưu trữ</button></div></form>`);return;
  }
  if(type==='visitor-confirm'){
    const v=state.data.visitors.find(v=>v.id===id), next=v.status==='registered'?'inside':'left';
    showModal(next==='inside'?'Xác nhận khách vào':'Xác nhận khách rời đi',`<form id="visitor-transition-form" data-id="${esc(id)}" data-version="${v.version}" data-status="${next}"><div class="dialog-body"><p>Xác nhận <b>${esc(v.name)}</b> ${next==='inside'?'đã được đối chiếu và vào đơn vị':'đã rời khỏi đơn vị'}?</p><p>Trạng thái sau xác nhận: ${visitorStatus[next]}.</p><div class="form-error" role="alert"></div></div><div class="dialog-footer">${button('Hủy','close',null,'secondary','type="button"')}<button class="button primary" type="submit">Xác nhận</button></div></form>`);return;
  }
}
document.addEventListener('click', async e => {
  const el=e.target.closest('[data-action]'); if(!el || el.disabled) return;
  try {await action(el);} catch(error){toast(error.message);}
});
document.addEventListener('submit', async e => {
  const form=e.target;
  if(!['worker-form','event-form','visitor-form','archive-form','visitor-transition-form','transfer-form'].includes(form.id)) return;
  e.preventDefault();const submit=form.querySelector('[type="submit"]'),errorEl=form.querySelector('.form-error');submit.disabled=true;errorEl.textContent='';
  try {
    let body=Object.fromEntries(new FormData(form)), path, message;
    if(form.id==='worker-form'){
      path='workers';
      body._manuallyRated=body._manuallyRated==='true'&&body.loai!=='Gia thuộc';
      body.chu_phong=form.elements.chu_phong.checked&&!form.elements.chu_phong.disabled;
      for (const key of ['danh_gia_ky_nang','danh_gia_dao_duc']) body[key]=body[key]===undefined||body[key]===''?null:Number(body[key]);
      if(form.dataset.id){body.id=form.dataset.id;body.version=Number(form.dataset.version);}
      message='Đã lưu hồ sơ vào cơ sở dữ liệu cục bộ.';
    }
    if(form.id==='event-form'){path='events';message='Đã ghi nhận nhật ký ra/vào thủ công.';}
    if(form.id==='visitor-form'){path='visitors';message='Đã đăng ký khách. Chưa xác nhận vào cổng.';}
    if(form.id==='archive-form'){path='workers/archive';body={id:form.dataset.id,version:Number(form.dataset.version)};message='Đã lưu trữ hồ sơ và giải phóng phòng ở.';}
    if(form.id==='visitor-transition-form'){path='visitors/transition';body={id:form.dataset.id,version:Number(form.dataset.version),status:form.dataset.status};message='Đã cập nhật trạng thái khách.';}
    if(form.id==='transfer-form'){
      const worker=state.data.workers.find(w=>w.id===body.worker_id);
      if(!worker) throw new Error('Chọn hồ sơ cần chuyển phòng.');
      path='transfers';body={worker_id:worker.id,version:worker.version,to_room:body.to_room,note:body.note};
      message='Đã gửi yêu cầu chuyển phòng. Hồ sơ đã rời phòng cũ và đang chờ chấp nhận.';
    }
    await api(path,body);closeModal();
    try {await refresh();toast(message);} catch {toast('Đã lưu nhưng chưa tải được danh sách mới. Hãy tải lại trang.');}
  } catch(error) {errorEl.textContent=error.message;submit.disabled=false;}
});
document.addEventListener('input',e=>{
  if(e.target.id==='worker-search'){state.query=e.target.value;state.page=1;document.getElementById('workers-results').innerHTML=workersResults();}
  if(e.target.id==='discipline-search'){state.disciplineQuery=e.target.value;document.getElementById('discipline-results').innerHTML=disciplineResults();}
  if(e.target.id==='card-search'){state.cardQuery=e.target.value;state.cardPage=1;document.getElementById('cards-results').innerHTML=cardsResults();}
  if(e.target.name==='ngay_sinh'&&e.target.closest('#worker-form')) document.getElementById('worker-age').value=ageAt(e.target.value);
});
document.addEventListener('change',e=>{
  const filter={'type-filter':'type','team-filter':'team','status-filter':'status','blood-filter':'blood','quality-filter':'quality'}[e.target.id];
  if(filter){state[filter]=e.target.value;state.page=1;document.getElementById('workers-results').innerHTML=workersResults();}
  const cardFilter={'card-team-filter':'cardTeam','card-kv-filter':'cardKv','card-type-filter':'cardType','card-photo-filter':'cardPhoto'}[e.target.id];
  if(cardFilter){state[cardFilter]=e.target.value;state.cardPage=1;document.getElementById('cards-results').innerHTML=cardsResults();}
  if(e.target.id==='card-scope-filter'){state.cardScopeOnly=e.target.value==='yes';state.cardPage=1;document.getElementById('cards-results').innerHTML=cardsResults();}
  if(e.target.id==='discipline-status'){state.disciplineStatus=e.target.value;document.getElementById('discipline-results').innerHTML=disciplineResults();}
  if(e.target.closest('#worker-form')) {
    if(e.target.name==='unit_id'){const room=dialog.querySelector('[name="phong_o"]');room.innerHTML=selectOptions(roomOptions(e.target.value),'');}
    if(['unit_id','phong_o'].includes(e.target.name)) dialog.querySelector('[name="chu_phong"]').checked=false;
    if(['unit_id','phong_o','loai','_manuallyRated'].includes(e.target.name)) syncWorkerControls();
  }
  if(e.target.closest('#transfer-form') && ['worker_id','to_unit'].includes(e.target.name)) {
    const form=e.target.closest('#transfer-form'), worker=state.data.workers.find(w=>w.id===form.elements.worker_id.value);
    const unit=e.target.name==='to_unit'?e.target.value:(state.unit==='all'?worker?.unit_id:state.unit);
    form.elements.to_unit.value=unit;
    const rooms=state.data.rooms.filter(r=>r.unit_id===unit&&r.id!==worker?.phong_o);
    form.elements.to_room.innerHTML=selectOptions(rooms.map(r=>[r.id,`${r.id} · ${occupancy(r)}/${r.capacity} người`]),'');
  }
  if(e.target.id==='ocr-select-all'){for(const box of document.querySelectorAll('[data-ocr-field]')) box.checked=e.target.checked;}
  if(e.target.id==='ocr-confirm') document.getElementById('ocr-confirm-row')?.classList.remove('needs-check');
  if(e.target.id==='ocr-file'||e.target.id==='ocr-camera') {
    resetOcr();
    document.getElementById('ocr-results').innerHTML='';
    const preview=document.getElementById('ocr-preview'),read=dialog.querySelector('[data-action="ocr-read"]');
    preview.hidden=true;preview.removeAttribute('src');read.disabled=true;
    const other=document.getElementById(e.target.id==='ocr-file'?'ocr-camera':'ocr-file');
    if(other) other.value='';
    const file=e.target.files[0];
    if(!file){document.getElementById('ocr-status').textContent='Chọn hoặc chụp ảnh để bắt đầu.';return;}
    if(['image/heic','image/heif'].includes(file.type)){document.getElementById('ocr-status').textContent='Ảnh HEIC từ iPhone chưa đọc được. Dùng nút “Chụp ảnh” hoặc chọn ảnh JPEG/PNG.';e.target.value='';return;}
    if(!['image/png','image/jpeg','image/webp'].includes(file.type)){document.getElementById('ocr-status').textContent='Chọn ảnh PNG, JPEG hoặc WebP; ảnh chụp trực tiếp từ camera điện thoại là tốt nhất.';e.target.value='';return;}
    if(file.size>10*1024*1024){document.getElementById('ocr-status').textContent='Ảnh lớn hơn 10 MB. Chụp lại ở độ phân giải thấp hơn hoặc chọn ảnh nhỏ hơn.';e.target.value='';return;}
    ocrFile=file;ocrPreview=URL.createObjectURL(file);preview.src=ocrPreview;preview.hidden=false;read.disabled=false;
    document.getElementById('ocr-status').textContent='Ảnh chỉ ở trên máy. Bấm “Đọc ảnh trên máy” để nhận diện.';
  }
});
document.getElementById('unit-select').addEventListener('change',e=>{state.unit=e.target.value;state.room='';state.page=1;state.blood='all';render();});
document.getElementById('menu-toggle').innerHTML=icon('menu');
document.getElementById('unit-icon').innerHTML=icon('building');
document.getElementById('notification-button').innerHTML=icon('bell');
document.getElementById('menu-toggle').addEventListener('click',()=>{const open=document.getElementById('sidebar').classList.toggle('open');document.getElementById('menu-toggle').setAttribute('aria-expanded',String(open));});
document.getElementById('notification-button').addEventListener('click',()=>{go('overview');requestAnimationFrame(()=>document.getElementById('attention')?.scrollIntoView({behavior:'auto',block:'center'}));});
window.addEventListener('hashchange',()=>{document.getElementById('sidebar').classList.remove('open');document.getElementById('menu-toggle').setAttribute('aria-expanded','false');render();window.scrollTo(0,0);});
window.addEventListener('afterprint',()=>{document.body.classList.remove('printing');document.getElementById('print-area').innerHTML='';});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){document.getElementById('sidebar').classList.remove('open');document.getElementById('menu-toggle').setAttribute('aria-expanded','false');}});
if ('serviceWorker' in navigator && (location.protocol==='https:' || ['localhost','127.0.0.1'].includes(location.hostname))) {
  navigator.serviceWorker.register('/sw.js').catch(()=>{});
}
refresh().catch(error=>{main.innerHTML=`<div class="error-state"><h1>Chưa kết nối được máy chủ</h1><p>${esc(error.message)}</p><p>Kiểm tra kết nối mạng hoặc liên hệ quản trị viên. Không mở trực tiếp tệp HTML.</p>${button('Thử lại','retry','refresh')}</div>`;});
