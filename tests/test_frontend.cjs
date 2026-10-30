const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function fixture() {
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, {innerHTML:'',textContent:'',addEventListener(){},setAttribute(){},classList:{add(){},remove(){}}});
    return elements.get(id);
  };
  const context = vm.createContext({
    document:{getElementById:element,addEventListener(){}},
    window:{addEventListener(){}}, location:{hash:'#workers'},
    navigator:{serviceWorker:{register:() => Promise.resolve()}},
    fetch:() => new Promise(() => {}), setTimeout(){},clearTimeout(){},
    URL,Blob,Intl,Date,console,TextEncoder,
  });
  const script = fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8');
  const qrScript = fs.readFileSync(path.join(__dirname,'../static/qr.js'),'utf8');
  vm.runInContext(qrScript+'\n'+script+'\nglobalThis.helpers={esc,normalize,csvValue,filteredWorkers,workersResults,workerTable,workerList,occupancy,isInside,state,currentRoute,needsReview,disciplineWorkers,ratingText,ageAt,matchesWorker,ocrResultsMarkup,resetWorkerFilters,pendingTransfer,transferPanel,transferBadge,cardCode,qrPayload,kvCode,kvConfirmed,kvNumber,cardNumber,cardScope,inCardScope,cardWorkers,cards,idCardMarkup,visitorCode,visitorExpired,visitorPassMarkup,cardsResults,resetCardFilters,QRCode,parseScanCode,resolveScan,gateWorkerMarkup,gateVisitorMarkup,spotCheckMarkup,checkTable,insideRows,security,eventTable,durationText,methodLabel,spotChecks,scopedChecks,insideSince,GATE_OVERDUE_HOURS,hasBarcodeDetector,hasJsQr,qrPayloadFromImageData,qrPayloadFromSource,aiStatusPanelMarkup,aiReady,ocrStatusIssue,ocrAiIssueMarkup,ocrRequestText};',context);
  return {...context.helpers, location:context.location, window:context.window};
}

function person(overrides={}) {
  return {id:'one',person_id:'CN-0001',ten_that:'Đặng Hồ Sơ Mẫu',ten_ho_so:'Mẫu',unit_id:'DSX02',status:'active',loai:'Lao động',to:'Tổ 1',phong_o:'A01',cmnd:'',so_dt:'',...overrides};
}

test('Vietnamese search ignores accents and case',()=>{
  const h=fixture();assert.equal(h.normalize('ĐẶNG Thị Hồng'),'dang thi hong');
});
test('profile text is escaped for HTML and attributes',()=>{
  const h=fixture();assert.equal(h.esc('<img src=x onerror="alert(1)">'), '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;');
  assert.equal(h.esc("'&"),'&#39;&amp;');
  assert.doesNotMatch(h.workerTable([person({ten_that:'<img onerror=alert(1)>'})]),/<img onerror/);
});
test('CSV formulas cannot execute when opened by spreadsheets',()=>{
  const h=fixture();for(const value of ['=1+1',' +SUM(A1)','@SUM(A1)','-1+2','\t=1']) assert.ok(h.csvValue(value).startsWith('"\''));
  assert.equal(h.csvValue('Hồ sơ "mẫu"'),'"Hồ sơ ""mẫu"""');
});
test('filters combine scope, type, room, status and missing documents',()=>{
  const h=fixture();h.state.data={workers:[person(),person({id:'two',unit_id:'DSX03'}),person({id:'three',status:'archived'}),person({id:'four',loai:'Gia thuộc'})]};
  h.state.unit='DSX02';h.state.query='dang ho';h.state.missing=true;h.state.type='Lao động';h.state.room='A01';
  assert.equal(h.filteredWorkers().length,1);assert.equal(h.filteredWorkers()[0].id,'one');
  h.state.query='khong co ket qua';assert.equal(h.filteredWorkers().length,0);
});
test('archived workers do not occupy rooms and other units are excluded',()=>{
  const h=fixture();h.state.data={workers:[person(),person({id:'two',status:'archived'}),person({id:'three',unit_id:'DSX03'})]};
  assert.equal(h.occupancy({id:'A01',unit_id:'DSX02'}),1);
});
test('gate presence is based on latest event, not array order',()=>{
  const h=fixture();h.state.data={events:[{worker_id:'one',direction:'in',at:'2026-01-01T08:00:00Z'},{worker_id:'one',direction:'out',at:'2026-01-01T09:00:00Z'}]};
  assert.equal(h.isInside('one'),false);assert.equal(h.isInside('absent'),false);
});
test('pagination clamps after a filter leaves fewer results',()=>{
  const h=fixture();h.state.data={workers:[person()]};h.state.page=5;
  const html=h.workersResults();assert.equal(h.state.page,1);assert.match(html,/Trang 1 \/ 1/);
});

test('pending room transfer flags the worker and escapes notes',()=>{
  const h=fixture();
  h.state.data={workers:[person({phong_o:''})],transfers:[{id:'t1',worker_id:'one',from_unit:'DSX02',from_team:'Tổ 1',from_room:'A01',to_unit:'DSX03',to_room:'B02',note:'<img onerror=alert(1)>',status:'pending',created_at:'2026-10-29T03:00:00Z',decided_at:'',decision_note:''}]};
  h.state.unit='DSX02';
  const row=h.pendingTransfer('one'), html=h.transferPanel();
  assert.equal(row.to_room,'B02');assert.equal(h.pendingTransfer('absent'),undefined);
  assert.match(h.workerList([person({phong_o:''})]),/Chờ nhận phòng/);
  assert.match(html,/Chờ chấp nhận/);assert.match(html,/B02/);assert.match(html,/DSX03/);
  assert.doesNotMatch(html,/<img onerror/);
  assert.match(h.transferBadge('approved'),/Đã chấp nhận/);assert.match(h.transferBadge('rejected'),/Từ chối/);
});
test('transfer panel hides other units and separates decided transfers',()=>{
  const h=fixture();
  h.state.data={workers:[person({phong_o:''})],transfers:[
    {id:'t1',worker_id:'one',from_unit:'DSX02',from_team:'Tổ 1',from_room:'A01',to_unit:'DSX03',to_room:'B02',note:'',status:'pending',created_at:'2026-10-29T03:00:00Z',decided_at:'',decision_note:''},
    {id:'t2',worker_id:'one',from_unit:'NMCB',from_team:'Tổ 2',from_room:'C01',to_unit:'NMCB',to_room:'C02',note:'',status:'approved',created_at:'2026-10-28T03:00:00Z',decided_at:'2026-10-28T04:00:00Z',decision_note:'Mẫu'},
  ]};
  h.state.unit='DSX03';
  let html=h.transferPanel();
  assert.match(html,/1 yêu cầu/);assert.doesNotMatch(html,/C02/);
  h.state.unit='all';html=h.transferPanel();
  assert.match(html,/Đã xử lý gần đây/);assert.match(html,/C02/);
  assert.match(h.workerTable([person({phong_o:''})]),/Chờ nhận phòng/);
});

test('landing page is worker search with company scope',()=>{
  const h=fixture();h.location.hash='';assert.equal(h.currentRoute(),'workers');
  h.location.hash='#unknown';assert.equal(h.currentRoute(),'workers');assert.equal(h.state.unit,'all');
});
test('search covers legacy fields and punctuation-free phone numbers',()=>{
  const h=fixture();
  assert.equal(h.matchesWorker(person({so_dt:'012 345-6789'}),'0123456789'),true);
  for(const [key,value] of Object.entries({nhom_mau:'AB+',khu_vuc:'Khu phía Đông',phan_cay:'PC-567',so_bao_hiem:'BH-789',dia_chi:'Đường Cây Xanh',noi_sinh:'Tỉnh Mẫu'})) {
    assert.equal(h.matchesWorker(person({[key]:value}),h.normalize(value)),true,key);
  }
  assert.equal(h.matchesWorker(person({so_dt:'012 345-6789'}),'letters 0123456789'),false);
});
test('blood and legacy filters compose with company scope',()=>{
  const h=fixture();h.state.data={workers:[person({nhom_mau:'AB+',ten_ho_so:'Tên khác'}),person({id:'two',nhom_mau:'AB+',unit_id:'NMCB'}),person({id:'three',nhom_mau:'O'})]};
  h.state.unit='DSX02';h.state.blood='AB+';h.state.quality='borrowed';
  assert.equal(h.filteredWorkers().length,1);assert.equal(h.filteredWorkers()[0].id,'one');
  h.resetWorkerFilters();assert.equal(h.state.unit,'DSX02');assert.equal(h.state.blood,'all');assert.equal(h.state.quality,'all');
});
test('ratings distinguish unassessed from assessed five stars',()=>{
  const h=fixture();
  assert.equal(h.ratingText(person({_manuallyRated:false,danh_gia_ky_nang:3}),'danh_gia_ky_nang'),'Chưa đánh giá');
  assert.equal(h.ratingText(person({_manuallyRated:true,danh_gia_ky_nang:5}),'danh_gia_ky_nang'),'5/5');
  assert.equal(h.ratingText(person({_manuallyRated:true,danh_gia_ky_nang:null}),'danh_gia_ky_nang'),'Chưa chấm');
  assert.equal(h.ratingText(person({loai:'Gia thuộc',_manuallyRated:true,danh_gia_ky_nang:5}),'danh_gia_ky_nang'),'Không áp dụng');
});
test('review excludes dependents and unassessed defaults',()=>{
  const h=fixture();
  assert.equal(h.needsReview(person({_manuallyRated:false,danh_gia_ky_nang:3})),false);
  assert.equal(h.needsReview(person({_manuallyRated:true,danh_gia_ky_nang:2})),true);
  assert.equal(h.needsReview(person({loai:'Gia thuộc',ghi_chu_ky_luat:'Không được theo dõi'})),false);
  assert.equal(h.needsReview(person({ghi_chu_ky_luat:'Kế hoạch đào tạo'})),true);
});
test('discipline register obeys unit, status and text filters',()=>{
  const h=fixture();h.state.data={workers:[person({ghi_chu_ky_luat:'Đào tạo lại',trang_thai_ky_luat:'Đang theo dõi'}),person({id:'two',unit_id:'NMCB',ghi_chu_ky_luat:'Đào tạo lại'}),person({id:'three',status:'archived',ghi_chu_ky_luat:'Đào tạo lại'})]};
  h.state.unit='DSX02';h.state.disciplineQuery='dao tao';h.state.disciplineStatus='Đang theo dõi';
  assert.equal(h.disciplineWorkers().length,1);
});
test('age is birthday-aware and does not infer missing dates',()=>{
  const h=fixture();assert.equal(h.ageAt('1990-11-02',new Date(2026,9,29)),'35');
  assert.equal(h.ageAt('1990-10-29',new Date(2026,9,29)),'36');
  assert.equal(h.ageAt('',new Date(2026,9,29)),'');assert.equal(h.ageAt('2030-01-01',new Date(2026,9,29)),'');
});
test('worker list renders escaped legacy fields without raw HTML',()=>{
  const h=fixture(),html=h.workerList([person({nhom_mau:'<svg onload=x>',phan_cay:'<img src=x>',ten_ho_so:'<b>Khác</b>'})]);
  assert.doesNotMatch(html,/<svg onload|<img src=x>|<b>Khác/);assert.match(html,/&lt;b&gt;Khác/);
});
test('OCR review escapes content and never preselects existing fields',()=>{
  const h=fixture(),html=h.ocrResultsMarkup({fields:{ten_that:'<b>Mẫu</b>',cmnd:'DEMO-OCR',nhom_mau:'O'},text:'<script>bad</script>'},{ten_that:'Đã nhập'});
  assert.match(html,/data-ocr-field="ten_that" >/);assert.match(html,/data-ocr-field="cmnd" checked/);
  assert.doesNotMatch(html,/data-ocr-field="nhom_mau"|<script>bad|<b>Mẫu/);
  assert.match(html,/id="ocr-confirm"/);
});
test('AI request template asks for a working API and a fallback list',()=>{
  const h=fixture();
  const request={text:'Cần API hiện có để kích hoạt và danh sách API dự phòng khi hết hạn mức',sample:{providers:[{id:'api-phu',kind:'generic',endpoint:'https://api.example.com/ocr',key_env:'OCR_KEY'}]}};
  const text=h.ocrRequestText(request);
  assert.match(text,/dự phòng/);assert.match(text,/CN_OCR_PROVIDERS/);assert.match(text,/api-phu/);
  const issued=h.ocrAiIssueMarkup({error:'no_provider',message:'<b>mất kết nối</b>',request});
  assert.match(issued,/Yêu cầu lập trình viên/);assert.match(issued,/data-ocr-request-text/);assert.match(issued,/ocr-copy-request/);
  assert.doesNotMatch(issued,/<b>mất kết nối<\/b>/);
  const quota=h.ocrAiIssueMarkup({error:'quota_exhausted',message:'Hết hạn mức',request});
  assert.match(quota,/hết hạn mức/);assert.match(quota,/Bộ đọc trên máy/);
});
test('AI status panel separates ready, cooling and missing key providers',()=>{
  const h=fixture();
  const request={text:'Yêu cầu API',sample:{providers:[]}};
  const html=h.aiStatusPanelMarkup({configured:true,providers:[
    {id:'api-chinh',kind:'gemini',state:'ready',calls:3,errors:0,quota_hits:0,quota_per_day:200,target:'generativelanguage.googleapis.com',last_error:''},
    {id:'<img onerror=x>',kind:'generic',state:'cooling',calls:1,errors:1,quota_hits:1,quota_per_day:50,target:'api.example.com',last_error:'<script>bad</script>'},
    {id:'chua-khoa',kind:'generic',state:'missing_key',calls:0,errors:0,quota_hits:0,quota_per_day:null,target:'api.example.com',last_error:''},
  ],errors:['<b>sai cấu hình</b>'],request});
  assert.match(html,/Sẵn sàng/);assert.match(html,/Tạm nghỉ · hạn mức/);assert.match(html,/Thiếu khoá/);
  assert.match(html,/3 lượt/);assert.match(html,/ocr-copy-request/);
  assert.doesNotMatch(html,/<img onerror|<script>bad|<b>sai cấu hình/);
  const off=h.aiStatusPanelMarkup({configured:false,providers:[],errors:[],request});
  assert.match(off,/Chưa kích hoạt/);assert.match(off,/dự phòng/);
  assert.equal(h.aiReady(null),false);
  assert.equal(h.aiReady({configured:true,providers:[{state:'ready'}]}),true);
  assert.equal(h.aiReady({configured:true,providers:[{state:'cooling'}]}),false);
  assert.equal(h.ocrStatusIssue({configured:false,providers:[]}).error,'no_provider');
  assert.equal(h.ocrStatusIssue({configured:true,providers:[{state:'cooling'}]}).error,'quota_exhausted');
  assert.equal(h.ocrStatusIssue({configured:true,providers:[{state:'ready'}]}),null);
});

function companyData(workers=[person()],extra={}) {
  return {workers,rooms:[],events:[],visitors:[],transfers:[],audit:[],outbox:[],images:{},spot_checks:[],meta:{card_scope:['DSX01','DSX02','DSX03','DSX06']},...extra};
}
test('printed card code follows company, unit, area and serial',()=>{
  const h=fixture();
  const w=person({khu_vuc:'KV2'});
  assert.equal(h.cardCode(w),'CRCK2-DSX02-KV2-001');
  assert.equal(h.qrPayload(w),'C2-0001');
  assert.equal(h.qrPayload(person({person_id:'CN-1234'})),'C2-1234');
  assert.equal(h.kvConfirmed(w),true);
});
test('dirty area values normalize and fall back to the team',()=>{
  const h=fixture();
  for(const [value,expected,confirmed] of [['KV08','KV8',true],['KVK1','KV1',true],['5','KV5',true],['Khu vực 3','KV3',true],['','KV2',false],['Chưa rõ','KV2',false]]) {
    const w=person({khu_vuc:value,to:'Tổ 2'});
    assert.equal(h.kvCode(w),expected,value);
    assert.equal(h.kvConfirmed(w),confirmed,value);
  }
});
test('card scope comes from server meta and other units stay preview only',()=>{
  const h=fixture(), inside=person(), outside=person({id:'two',unit_id:'NMCB'});
  h.state.data=companyData([inside,outside]);h.state.unit='all';
  assert.equal(h.inCardScope(inside),true);assert.equal(h.inCardScope(outside),false);
  assert.equal(h.cardWorkers().length,1);
  h.state.cardScopeOnly=false;assert.equal(h.cardWorkers().length,2);
  h.state.data.meta={};assert.equal(h.inCardScope(inside),false);
});
test('card filters combine area, team, type, photo and code search',()=>{
  const h=fixture();
  h.state.data=companyData([person({khu_vuc:'KV2'}),person({id:'two',khu_vuc:'KV3'}),person({id:'three',loai:'Gia thuộc',khu_vuc:'KV2'}),person({id:'four',person_id:'CN-0004',khu_vuc:'KV2',to:'Tổ 3'})],{images:{one:{photo:true}}});
  h.state.unit='all';h.state.cardKv='KV2';h.state.cardPhoto='yes';
  assert.equal(h.cardWorkers().length,1);assert.equal(h.cardWorkers()[0].id,'one');
  h.state.cardPhoto='no';h.state.cardType='Gia thuộc';
  assert.equal(h.cardWorkers().length,1);assert.equal(h.cardWorkers()[0].id,'three');
  h.state.cardType='all';h.state.cardTeam='Tổ 3';h.state.cardQuery='crck2-dsx02-kv2-004';
  assert.equal(h.cardWorkers().length,1);assert.equal(h.cardWorkers()[0].id,'four');
});
test('search finds a worker by QR payload and printed code',()=>{
  const h=fixture();h.state.data=companyData([person({khu_vuc:'KV2'})]);h.state.unit='all';
  assert.equal(h.matchesWorker(person({khu_vuc:'KV2'}),'C2-0001'),true);
  assert.equal(h.matchesWorker(person({khu_vuc:'KV2'}),'KV2-001'),true);
  assert.equal(h.matchesWorker(person({khu_vuc:'KV2'}),'C2-0002'),false);
});
test('card markup escapes text and embeds a self-contained QR',()=>{
  const h=fixture();h.state.data=companyData();
  const html=h.idCardMarkup(person({ten_that:'<img onerror=alert(1)>',khu_vuc:'<b>KV2</b>',phong_o:'<script>x</script>'}));
  assert.doesNotMatch(html,/<img onerror|<b>KV2|<script>x/);
  assert.match(html,/class="id-card"/);assert.match(html,/<svg class="qr"/);
  assert.match(html,/C2-0001/);assert.match(html,/CRCK2-DSX02-KV2-001/);
  assert.match(h.idCardMarkup(person({unit_id:'NMCB'})),/id-card pending/);
});
test('visitor passes get a per-day code, expiry and QR',()=>{
  const h=fixture();
  const at=hour=>new Date(2026,9,29,hour).toISOString();
  const pad=n=>String(n).padStart(2,'0'), ymd=d=>`${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
  const day={id:'v1',name:'Khách A',company:'Nhà cung cấp',unit_id:'DSX02',host:'Anh B',purpose:'Giao hàng',expected:ymd(new Date()),created_at:at(8),status:'registered'};
  const late={id:'v2',name:'Khách B',company:'Đối tác',unit_id:'DSX02',host:'Chị C',purpose:'Họp',expected:ymd(new Date()),created_at:at(10),status:'registered'};
  h.state.data=companyData([person()],{visitors:[late,day]});
  assert.equal(h.visitorCode(day),'KH-291026-0001');
  assert.equal(h.visitorCode(late),'KH-291026-0002');
  assert.equal(h.visitorExpired({expected:ymd(new Date(Date.now()+864e5))}),false);
  assert.equal(h.visitorExpired({expected:ymd(new Date(Date.now()-864e5))}),true);
  assert.equal(h.visitorExpired({expected:''}),false);
  const html=h.visitorPassMarkup({...day,name:'<b>Khách A</b>'});
  assert.match(html,/id-card visitor/);assert.match(html,/KH-291026-0001/);assert.match(html,/<svg class="qr"/);
  assert.doesNotMatch(html,/<b>Khách A/);
  assert.match(h.visitorPassMarkup({...day,expected:'2000-01-01'}),/id-card visitor expired/);
});
test('cards page lists tiles, clamps pages and escapes the visitor panel',()=>{
  const h=fixture();
  const workers=Array.from({length:13},(_,i)=>person({id:`w${i}`,person_id:`CN-${String(i+1).padStart(4,'0')}`,khu_vuc:'KV2'}));
  h.state.data=companyData(workers,{visitors:[{id:'v1',name:'<img onerror=x>',company:'C',unit_id:'DSX02',host:'H',purpose:'P',expected:'2999-01-01',created_at:new Date(2026,9,29,9).toISOString(),status:'registered'}]});
  h.state.unit='all';h.state.cardPage=5;
  const html=h.cards();
  assert.match(html,/Thẻ ID & QR/);assert.equal(h.state.cardPage,2);
  assert.match(html,/Trang 2 \/ 2/);assert.match(html,/Thẻ khách/);
  assert.doesNotMatch(html,/<img onerror/);
});
test('scan codes normalize to person ids and reject visitor or malformed codes',()=>{
  const h=fixture();
  assert.equal(h.parseScanCode('c2-0001'),'CN-0001');
  assert.equal(h.parseScanCode(' C2-17 '),'CN-0017');
  assert.equal(h.parseScanCode('CN-4'),'CN-0004');
  assert.equal(h.parseScanCode('17'),'CN-0017');
  assert.equal(h.parseScanCode('C2-00001'),'');
  assert.equal(h.parseScanCode('KH-291026-0001'),'');
  assert.equal(h.parseScanCode('C2-ABCD'),'');
});
test('scan resolution distinguishes workers, cards, visitors, archived records and strangers',()=>{
  const h=fixture();
  const pad=n=>String(n).padStart(2,'0'), ymd=d=>`${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
  const visitor={id:'v1',name:'Khách A',company:'C',purpose:'P',host:'H',unit_id:'DSX02',expected:ymd(new Date()),created_at:new Date(2026,9,29,9).toISOString(),status:'registered',version:1};
  h.state.data=companyData([person(),person({id:'two',person_id:'CN-0002',status:'archived'})],{visitors:[visitor]});
  h.state.unit='all';
  assert.equal(h.resolveScan('C2-0001').kind,'worker');
  assert.equal(h.resolveScan('c2-0001').worker.id,'one');
  assert.equal(h.resolveScan('CRCK2-DSX02-KV1-001').worker.id,'one');
  assert.equal(h.resolveScan('C2-0002').kind,'archived');
  assert.equal(h.resolveScan('C2-9999').kind,'unknown');
  const scanned=h.resolveScan(h.visitorCode(visitor));
  assert.equal(scanned.kind,'visitor');assert.equal(scanned.expired,false);
  assert.equal(h.resolveScan('').kind,'empty');
});
test('gate worker card suggests the next direction, escapes names and keeps the scan method',()=>{
  const h=fixture();
  h.state.data=companyData([person({ten_that:'<img onerror=alert(1)>'})],{events:[{id:'e1',worker_id:'one',person_id:'CN-0001',name:'Mẫu',unit_id:'DSX02',gate:'Cổng chính',direction:'in',method:'qr',at:new Date().toISOString()}]});
  h.state.unit='all';
  const html=h.gateWorkerMarkup({kind:'worker',code:'C2-0001',worker:h.state.data.workers[0]},'qr');
  assert.doesNotMatch(html,/<img onerror/);
  assert.match(html,/data-method="qr"/);
  assert.match(html,/<option value="out" selected>/);
  assert.match(html,/Đang trong/);
  assert.match(html,/Xác nhận ghi nhận/);
});
test('visitor gate card blocks expired passes but allows leaving',()=>{
  const h=fixture();
  h.state.data=companyData([person()],{visitors:[]});
  h.state.unit='all';
  const base={id:'v1',name:'Khách A',company:'C',purpose:'P',host:'H',unit_id:'DSX02',expected:'2000-01-01',created_at:new Date(2026,9,29,9).toISOString(),status:'registered',version:1};
  const blocked=h.gateVisitorMarkup({kind:'visitor',code:'KH-291026-0001',visitor:base,expired:true},'qr');
  assert.match(blocked,/hết hạn/);assert.doesNotMatch(blocked,/gate-visitor-form/);
  const leaving=h.gateVisitorMarkup({kind:'visitor',code:'KH-291026-0001',visitor:{...base,status:'inside'},expired:true},'qr');
  assert.match(leaving,/data-status="left"/);assert.match(leaving,/Xác nhận khách ra/);
});
test('spot check markup forces unknown codes and preselects mismatch for archived records',()=>{
  const h=fixture();h.state.data=companyData();h.state.unit='all';
  const unknown=h.spotCheckMarkup({kind:'unknown',code:'C2-9999'},'qr');
  assert.match(unknown,/Không nhận diện/);assert.match(unknown,/name="result" value="unknown"/);
  assert.match(unknown,/data-code="C2-9999"/);assert.match(unknown,/data-method="qr"/);
  const archived=h.spotCheckMarkup({kind:'archived',code:'C2-0002',worker:person({id:'two',person_id:'CN-0002',status:'archived'})},'manual');
  assert.match(archived,/<option value="mismatch" selected>/);
  assert.match(archived,/data-method="manual"/);assert.match(archived,/Khu vực kiểm tra/);
});
test('security console renders gate stations, inside list and spot check register',()=>{
  const h=fixture();
  const at=new Date().toISOString();
  h.state.data=companyData([person()],{
    events:[{id:'e1',worker_id:'one',person_id:'CN-0001',name:'Hồ sơ mẫu',unit_id:'DSX02',gate:'Cổng chính',direction:'in',method:'qr',at}],
    spot_checks:[{id:'c1',worker_id:'',person_id:'',name:'',unit_id:'',code:'C2-9999',area:'Khu khai thác',result:'unknown',note:'<b>ghi chú</b>',method:'manual',at}],
  });
  h.state.unit='all';
  let html=h.security();
  assert.match(html,/Trạm kiểm soát QR/);assert.match(html,/Đang trong cổng/);
  assert.match(html,/Quét QR/);assert.match(html,/Kiểm tra đột xuất/);
  assert.match(html,/Không nhận diện/);assert.match(html,/1 người/);
  assert.doesNotMatch(html,/<b>ghi chú<\/b>/);
  h.state.unit='DSX02';html=h.security();
  assert.match(html,/Không nhận diện/);
  assert.match(html,/Ghi ra/);
});
test('event table labels scanned and manual records and escapes gate text',()=>{
  const h=fixture();
  const at=new Date().toISOString();
  const html=h.eventTable([
    {id:'e1',person_id:'CN-0001',name:'A',unit_id:'DSX02',gate:'<img onerror=x>',direction:'in',method:'qr',at},
    {id:'e2',person_id:'CN-0002',name:'B',unit_id:'DSX02',gate:'Cổng khu ở',direction:'out',method:'manual',at},
  ]);
  assert.match(html,/Quét QR/);assert.match(html,/Thủ công/);
  assert.doesNotMatch(html,/<img onerror/);
});
test('camera scan falls back to the bundled decoder when BarcodeDetector is missing',()=>{
  const h=fixture();
  assert.equal(h.hasBarcodeDetector(),false);assert.equal(h.hasJsQr(),false);
  const frame={data:new Uint8ClampedArray(4),width:2,height:2};
  assert.equal(h.qrPayloadFromImageData(frame),'');
  h.window.jsQR=(data,width,height)=>width===2&&height===2?{data:'C2-0001'}:null;
  assert.equal(h.hasJsQr(),true);
  assert.equal(h.qrPayloadFromImageData(frame),'C2-0001');
  assert.equal(h.qrPayloadFromImageData(null),'');
  h.window.jsQR=()=>{throw new Error('decoder crashed');};
  assert.equal(h.qrPayloadFromImageData(frame),'');
  assert.equal(h.qrPayloadFromSource({videoWidth:0,videoHeight:0}),'');
});
