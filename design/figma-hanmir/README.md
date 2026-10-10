# HANMIR 웹 대시보드 Figma 초안

현재 Figma Starter MCP 호출 한도로 캔버스 편집이 불가능해, 동일한 초안을 생성하는 개발용 플러그인을 준비했습니다. 생성된 온라인 파일은 아직 빈 파일입니다.

## 실행

1. Figma 데스크톱 앱에서 디자인 파일을 엽니다.
2. 메뉴의 Plugins → Development → Import plugin from manifest에서 이 폴더의 `manifest.json`을 선택합니다.
3. Plugins → Development → HANMIR 웹 대시보드 초안을 실행합니다.

1920×1080 편집 가능한 프레임, 색상·간격 변수, 재사용 가능한 KPI 컴포넌트와 인스턴스를 생성합니다. 실행마다 새 초안을 추가합니다. 기존 레이어를 삭제하지 않습니다.

모든 작업자 이름·위치·배터리·SOS는 가상 예시입니다. 네트워크에 접속하지 않고 실제 서버 데이터와 카메라 이미지를 읽지 않습니다.

웹 구현은 `frontend/src/components/ControlRoomSummary.tsx`와 `frontend/src/control-room.css`에 있습니다. 실제 화면은 서버의 현재 데이터를 사용하며, Figma 예시 숫자와 다를 수 있습니다.

기준 대화: https://chatgpt.com/share/6ac9b407-f434-83ee-a271-93cef6164059
Figma 파일: https://www.figma.com/design/mAjAWbP1ThavvYXLdZPl8X
