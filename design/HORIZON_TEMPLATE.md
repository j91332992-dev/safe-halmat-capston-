# HANMIR 관리자 웹: Horizon UI 적용

- 선택한 Figma Community 템플릿: https://www.figma.com/community/file/1098131983383434513/horizon-ui-trendiest-open-source-admin-template-dashboard/
- Figma 공식 대시보드 템플릿 목록: https://www.figma.com/templates/dashboard-designs/
- 공식 React 원본: https://github.com/horizon-ui/horizon-tailwind-react
- 참조 커밋: 8f17779f2b45419112f32541bb555817dabc5b7c
- 라이선스: MIT, frontend/src/vendor/horizon/LICENSE.md

## 적용 범위
공식 Card/Widget 구조를 HorizonWidget.tsx로 옮기고 Tailwind 스타일을 기존 프로젝트 CSS로 변환했다. 흰색 사이드바, 우측 보라색 선택선, 연한 배경(#F4F7FE), 진한 본문(#1B254B), 보라색 주색(#4318FF), 20px 카드 모서리, 원형 아이콘, 알약 형태 헤더를 적용했다.
판매/매출 예제 데이터를 실제 작업자·위치·위험·배터리·팀 채팅 데이터로 교체했다. 위험·비상·오프라인은 안전 상태 색으로 표시한다. 글자 대비를 위해 원본의 연한 회색(#A3AED0)을 더 진한 #5E6B91로 조정했다. 한글은 기존 한글 글꼴을 사용한다.

기존 API, 로그인, SOS, 알림 처리, 위치, 카메라, 채팅, 교육 및 작업 허가 기능은 기존 컴포넌트를 사용한다. 데스크톱 관리자 스타일은 min-width:901px 및 hover:hover 범위에서 적용한다.
Figma MCP 사용량 제한 때문에 Figma 캔버스를 직접 가져오지는 못했다. 공식 공개 React 소스를 참조해 구현했으며, Figma 파일 생성 또는 수정 완료를 의미하지 않는다.
