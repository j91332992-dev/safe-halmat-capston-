// Editable Figma draft. All content below is fictional; no API or network access.
(async () => {
  const fonts = await figma.listAvailableFontsAsync();
  const family = fonts.some(f => f.fontName.family === 'Noto Sans KR') ? 'Noto Sans KR' : 'Inter';
  await Promise.all(['Regular', 'Bold'].map(style => figma.loadFontAsync({family, style})));
  const rgb = hex => ({r:parseInt(hex.slice(1,3),16)/255,g:parseInt(hex.slice(3,5),16)/255,b:parseInt(hex.slice(5,7),16)/255});
  const collection = figma.variables.createVariableCollection('HANMIR 웹 UI');
  const tokens = {};
  const colors = {nav:'#102b3a',surface:'#ffffff',canvas:'#f4f7fa',text:'#172f40',muted:'#607487',line:'#dbe4eb',accent:'#167557',soft:'#eaf5f2',danger:'#bc293b',dangerSoft:'#fffafa'};
  for (const [name, hex] of Object.entries(colors)) {
    const variable = figma.variables.createVariable(name, collection, 'COLOR');
    variable.scopes = ['FRAME_FILL','SHAPE_FILL','TEXT_FILL','STROKE_COLOR'];
    variable.setValueForMode(collection.defaultModeId, rgb(hex));
    variable.setVariableCodeSyntax('WEB', `var(--control-${name})`);
    tokens[name] = variable;
  }
  const spacing = {};
  for (const value of [8,12,16,20,22,28,32]) {
    const variable = figma.variables.createVariable(`space/${value}`, collection, 'FLOAT');
    variable.scopes = ['GAP','CORNER_RADIUS']; variable.setValueForMode(collection.defaultModeId,value);
    variable.setVariableCodeSyntax('WEB',`var(--control-space-${value})`); spacing[value] = variable;
  }
  function paint(name) {return figma.variables.setBoundVariableForPaint({type:'SOLID',color:rgb(colors[name])},'color',tokens[name]);}
  function box(parent,name,width,height,direction='VERTICAL',background='surface',pad=0,gap=12) {
    const f=figma.createFrame(); f.name=name; f.layoutMode=direction;
    f.primaryAxisSizingMode='FIXED'; f.counterAxisSizingMode='FIXED'; f.resize(width,height);
    f.fills=[paint(background)]; f.itemSpacing=gap;
    if(spacing[gap]) f.setBoundVariable('itemSpacing',spacing[gap]);
    f.paddingLeft=f.paddingRight=f.paddingTop=f.paddingBottom=pad;
    if(spacing[pad]) for(const prop of ['paddingLeft','paddingRight','paddingTop','paddingBottom']) f.setBoundVariable(prop,spacing[pad]);
    if(parent) parent.appendChild(f); return f;
  }
  function text(parent,value,size=14,color='text',bold=false,width) {
    const t=figma.createText(); t.fontName={family,style:bold?'Bold':'Regular'};
    t.fontSize=size; t.characters=value; t.fills=[paint(color)]; t.name=value;
    parent.appendChild(t);
    if(width) {t.textAutoResize='HEIGHT';t.resize(width, Math.max(20,t.height));}
    return t;
  }
  function outline(f) {f.strokes=[paint('line')]; f.strokeWeight=1; f.cornerRadius=14;}
  const page=figma.currentPage;
  const maxX=Math.max(0,...page.children.map(n=>n.x+n.width));
  const root=box(page,'HANMIR / 통합 대시보드 / 예시 데이터',1920,1080,'HORIZONTAL','canvas',0,0);
  root.x=maxX+100; root.y=100;
  const library=box(page,'Components / 편집 가능한 원본',1576,820,'VERTICAL','canvas',28,20);
  library.x=root.x;library.y=root.y+1200;
  text(library,'HANMIR · UI 컴포넌트 / 예시 데이터',24,'text',true);
  const sidebar=box(root,'Sidebar',280,1080,'VERTICAL','nav',28,20);
  text(sidebar,'H  HANMIR',28,'surface',true); text(sidebar,'SMART SAFETY',12,'surface');
  text(sidebar,'관제 메뉴',12,'surface');
  for(const [title,children] of [['통합 대시보드',[]],['위치 관제',['실시간 지도','위치 기록 재생','지도 설계','위험구역 관리']],['영상·AI 관제',['카메라 관제','음성·AI','이벤트 로그']],['안전 관리',['교육·작업 허가','작업자 관리','팀 채팅']],['장치·시스템',['장치 관리','하드웨어 진단','서버 설정']]]) {
    text(sidebar,title,16,'surface',true);
    if(children.length) text(sidebar,children.join('  ·  '),11,'surface',false,224);
  }
  text(sidebar,'● 예시 화면\n실제 장치와 연결되지 않습니다.',12,'surface',false,224);
  const main=box(root,'Main Content',1640,1080,'VERTICAL','canvas',32,20);
  const header=box(main,'Header',1576,70,'HORIZONTAL','canvas',0,20);
  const heading=box(header,'Title',810,70,'VERTICAL','canvas',0,8);
  text(heading,'ESP32 SMART HELMET · REALTIME CONTROL',11,'muted'); text(heading,'통합 대시보드',28,'text',true);
  text(header,'현재 시각  12:00     장치 연결  8/8     미처리 경보  1\n알림     서버 설정     로그아웃',14,'muted',false,720);
  const alert=box(main,'System Alert / 비상',1576,58,'HORIZONTAL','dangerSoft',16,16);outline(alert);
  text(alert,'! 비상 · 예시 작업자 C의 긴급 요청을 확인하세요.',16,'danger',true);
  const intro=box(main,'Overview Heading',1576,64,'VERTICAL','canvas',0,8);
  text(intro,'현장 상태를 한눈에',24,'text',true); text(intro,'예시 현장 · 모든 수치는 디자인 검토용 가상 데이터입니다.',13,'muted');
  const kpis=box(main,'Core KPIs / 5개',1576,180,'HORIZONTAL','canvas',0,16);
  const samples=[['실시간 작업자','4명','작업 중 3명 · 휴게 1명','surface','text'],['위치 신뢰도','99%','앵커 4/4 · 예시 값','surface','text'],['최고 위험도','비상','예시 작업자 C · 100점','dangerSoft','danger'],['안전모 배터리','62%','최저 45% · 4대 수신','surface','text'],['팀 채팅','현장과 연결','팀 대화 열기 →','soft','accent']];
  for(const [label,value,detail,bg,color] of samples) {
    const source=box(library,`KPI / ${label}`,302,180,'VERTICAL',bg,22,16);outline(source);
    text(source,label,14,'muted',true);text(source,value,36,color,true);text(source,detail,12,'muted');
    const component=figma.createComponentFromNode(source); component.description='HANMIR 핵심 상태 카드. 예시 값이며 실제 데이터와 연결되지 않음.';
    kpis.appendChild(component.createInstance());
  }
  const section=box(main,'Worker Section Heading',1576,40,'HORIZONTAL','canvas',0,20);
  text(section,'실시간 작업자',23,'text',true);text(section,'예시 작업자 C · 비상                    전체 관리 →',13,'muted');
  const bottom=box(main,'Worker & Events',1576,440,'HORIZONTAL','canvas',0,20);
  const worker=box(bottom,'Worker Card / 비상',750,440,'VERTICAL','surface',22,16);outline(worker);
  text(worker,'WORKER STATUS',11,'muted');text(worker,'예시 작업자 C                         ! 비상 · 100점',22,'danger',true);
  text(worker,'worker-demo-003 · helmet-demo-003\n작업 중 · 오늘 2시간 30분',13,'muted',false,706);
  text(worker,'현재 위치   X 3.6 · Y 6.2m                 위치 신뢰도   99%\n현재 구역   예시 안전구역                 보호구   안전모·조끼·장갑 착용',14,'text',false,706);
  const camera=box(worker,'Camera Frame / 수신 대기',706,128,'VERTICAL','canvas',20,8);
  text(camera,'No Frame',22,'muted',true);text(camera,'카메라 수신 대기 · 실제 영상은 포함하지 않았습니다.',12,'muted');
  text(worker,'☎ 음성 연결     카메라 보기     안전모 경고',14,'accent',true);
  const events=box(bottom,'Recent Events',806,440,'VERTICAL','surface',22,20);outline(events);
  text(events,'최근 이벤트                                      전체 보기 →',23,'text',true);
  text(events,'시간        상태         이벤트                       작업자          처리',13,'muted',true);
  for(const row of ['12:00     비상     WORKER_SOS          예시 작업자 C     대응 필요','11:58     주의     UWB_SIGNAL           예시 작업자 B     확인 완료','11:50     안내     SAFETY_CHECK         예시 작업자 A     처리 완료','11:45     안내     WORK_STARTED         예시 작업자 A     처리 완료','11:40     안내     DEVICE_CONNECTED     예시 작업자 B     처리 완료']) text(events,row,13,row.includes('비상')?'danger':'text',false,762);
  text(main,'관리자 빠른 제어       ☎ 통화 연결       스피커 경고       화재 수동발령',14,'text',true);
  figma.viewport.scrollAndZoomIntoView([root]); figma.currentPage.selection=[root];
  figma.closePlugin('HANMIR 편집 가능한 초안을 생성했습니다. 모든 데이터는 예시입니다.');
})().catch(error => figma.closePlugin(`생성 실패: ${error.message}`));
