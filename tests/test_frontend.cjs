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
    URL,Blob,Intl,Date,console,
  });
  const script = fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8');
  vm.runInContext(script+'\nglobalThis.helpers={esc,normalize,csvValue,filteredWorkers,workersResults,workerTable,workerList,occupancy,isInside,state,currentRoute,needsReview,disciplineWorkers,ratingText,ageAt,matchesWorker,ocrResultsMarkup,resetWorkerFilters};',context);
  return {...context.helpers, location:context.location};
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
