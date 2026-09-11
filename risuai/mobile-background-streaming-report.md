# RisuAI 모바일 백그라운드 생성 보존 보고서

기준일: 2026-09-07

## 결론

운영 중인 이전 패치의 Android 동결 해제 순서 결함을 수정했고, 수정 이미지의 격리 환경에서 실제 Galaxy의 두 재현 시나리오를 통과했다. 전송 직후 화면 잠금과 추론 출력 도중 화면 잠금 모두 약 65초 백그라운드 및 실제 `freeze` 이후, 같은 서버 작업의 완료 응답을 누락·중복 없이 받았다. 정상 응답 세 회차는 서버·휴대폰 스트림 SHA-256 일치, 생성 POST 1회, DELETE 0회, 정상 종료와 본문 표시까지 확인했다.

수정 이미지는 2026-09-08 운영 RisuAI에 배포했다. 아래에 이전 실패 기록, 수정 후 격리 검증과 운영 적용 상태를 구분한다. 또한 실기기 시험 중 상류가 `finish_reason=error`, 본문 0자로 종료한 두 회차를 별도로 발견했다. 이 회차들도 전송 무결성은 통과했지만 정상 답변 완료 통과로 세지 않았다.

RisuAI 포크, 새 프록시, 라이브러리나 영속 저장소 없이 기존 `mobile-background-stream.patch` 안의 lifecycle 처리만 보완했다. CPM이 동일 출처 `/api-proxy`로 시작한 POST는 기존 서버측 stream job을 사용하고, 브라우저는 동결 해제 후 같은 작업에 재부착한다. CPM 소스, API proxy 소스, 모델·effort 설정은 변경하지 않았다.

## 확인한 실제 구성

초기 운영 구성 점검은 민감한 값, 대화 내용, 실제 모델 이름과 외부 provider 주소를 기록하지 않는 범위에서 수행했다. 아래 추가 실기기 시험에서는 사용자 지시에 따라 캐릭터의 새 대화 내용을 읽고 자연스러운 대화를 전송했으며, 대화 원문과 인증값은 이 보고서에 포함하지 않았다.

- RisuAI와 `risuai-api-proxy` 컨테이너가 분리되어 있고 Caddy가 동일 출처 `/api-proxy`를 API proxy로 전달한다.
- 운영 RisuAI는 저장소 Dockerfile의 고정 커밋 `3d3dd1a0efbd32c30797ae3802a4dc080d638123`(표시 버전 `2026.6.214`)에서 빌드된다.
- 운영 provider는 RisuAI 내장 모델 경로가 아니라 CPM 플러그인 v1.53.10의 API v3 provider다.
- CPM은 `nativeFetch`로 동일 출처 API proxy에 스트리밍 POST를 보내며 모델과 reasoning 옵션도 CPM이 소유한다.
- 최근 7일 API proxy 로그의 민감하지 않은 집계에서는 비-GET 145건 중 143건이 streaming이고 모두 2xx였다. 평상시 네트워크 오류를 위한 별도 제품 기능을 추가할 근거는 발견하지 못했다.

## 재현

격리된 `/tmp/risuai-mobile-bg.hNIjn4`에 Caddy, 고정 버전 RisuAI, 공식 CPM v1.58.0, API proxy, OpenAI-compatible 가짜 LLM을 구성했다. 가짜 LLM은 정해진 순서의 SSE 청크를 내보내고 요청 수, 완료 수, 상류 client disconnect 수를 기록한다.

Linux Chromium의 단순 tab hidden 및 CDP freeze는 네트워크 서비스가 응답을 버퍼링해서 모바일의 연결 실패를 만들지 못했다. 따라서 제품 코드와 분리된 QA 훅으로 `visibilityState === "hidden"`이 되는 순간 페이지 소유 `/api-proxy` 응답 스트림만 종료했다. 이 훅은 일반 offline이나 임의 네트워크 장애를 만들지 않는다.

베이스라인은 두 번 모두 RisuAI 오류 모달 `QA: page-owned response stream closed while hidden`으로 끝났고, 가짜 LLM의 disconnect가 매번 1씩 증가했다.

## 구현

### 요청 경로

Node self-host 환경에서 동일 출처 `/api-proxy` POST를 발견하면 브라우저가 API proxy를 직접 호출하지 않고 RisuAI의 `/proxy-stream-jobs`를 호출한다. RisuAI 서버가 명시적으로 허용된 `risuai-api-proxy:8787`에 내부 요청을 실행한다. CPM 소스와 API proxy 소스는 변경하지 않는다.

### lifecycle 처리

- foreground에서는 기존처럼 WebSocket으로 청크를 즉시 표시한다.
- `visibilitychange`가 hidden을 알리면 page lifecycle freeze 전에 WebSocket만 닫는다.
- 서버 작업과 LLM 요청은 계속 실행되고 최대 2 MiB 또는 16,384개 이벤트를 메모리에 보존한다.
- hidden 또는 `freeze`에서는 연결과 예약된 연결 작업만 정리한다. 서버 생성은 취소하지 않는다.
- visible과 `resume`에서는 연결을 예약하고, 동결 해제 뒤 실행되는 다음 timer task에서 실제 연결을 만든다. Android가 visible을 resume보다 먼저 알리는 경우에도 동결 중 연결을 만들지 않는다.
- 마지막으로 처리한 sequence 이후 이벤트만 같은 job에서 다시 받는다. 예약 작업은 합쳐서 중복 연결을 방지한다.
- 연결 실패 자체로 서버 job을 DELETE하지 않는다. 일반 연결 오류의 자동 재시도는 추가하지 않았으며, 남은 서버 작업에는 기존 timeout과 GC 제한이 적용된다.
- 사용자의 명시적 abort 또는 응답 스트림 cancel은 해당 job을 DELETE해서 상류 요청을 즉시 중단한다.
- 완료 job은 해당 요청 timeout만큼만 메모리에 유지되고 기존 GC가 제거한다. 기본값은 10분이며 서버 재시작과 페이지 reload를 넘는 영속성은 제공하지 않는다.

순번은 hidden 전환 경계에서 이미 서버가 보냈지만 브라우저가 처리하지 못한 청크 한 개가 유실되는 것을 실제 첫 시험에서 발견한 뒤 추가했다. 이것은 새 LLM 호출이나 끊어진 답변의 재생성이 아니라 같은 in-memory transport buffer의 중복 없는 재부착이다.

## 이전 패치 QA 결과와 실패 기록

| 시험 | 결과 |
| --- | --- |
| 베이스라인 hidden 실패 재현 2회 | 2회 모두 UI 오류, 가짜 LLM disconnect 증가 |
| 수정 후 foreground 120청크 | 요청 1, 완료 1, 120/120, 누락 0, 중복 0 |
| 수정 후 hidden 120청크 | 요청 1, 완료 1, disconnect 0, 120/120, 누락 0, 중복 0 |
| 첫 WebSocket 연결 전 hidden 경계 | job 생성 응답을 1.5초 지연한 동안 hidden 전환, 요청 1, 완료 1, disconnect 0, 120/120 |
| 수정 후 hidden 800청크 2회 | 두 번 모두 800/800, 누락 0, 중복 0, disconnect 0 |
| visible WebSocket 강제 실패 | 패치 내부 fallback 없음, 각 기존 상위 시도마다 POST 뒤 DELETE, 미완료 상류 요청 즉시 abort |
| RisuAI 전체 unit test | 22 files, 228 passed, 3 skipped |
| Svelte/TypeScript check | 오류 0, 경고 0 |
| patch stack 신규 적용 및 재적용 | 성공 |
| 저장소 Dockerfile source/full image build | 성공 |
| Compose render 및 repository composelint | 성공 |
| 초기 Android Chrome 단기·장기 복귀 시험 | 일부 완료 관찰만으로 전체 해결을 판정했으므로 인수 검증으로 인정하지 않음 |
| 실제 캐릭터 새 대화, 전송 직후 HOME 및 약 1분 후 복귀 | 실패: 서버 완료 후에도 복귀해서 약 54초를 더 기다림 |
| 실제 캐릭터 새 대화, 추론 출력 시작 후 HOME 및 1분 후 복귀 | 해당 회차 통과: 동일 job 재부착 및 완료 응답 표시 |
| 실제 캐릭터 새 대화, 전송 직후 HOME·화면 잠금 및 1분 후 복귀 | 실패: 동결 해제 전 연결 생성이 거부되고 완료 job DELETE 및 새로운 job POST 발생 |
| 실제 캐릭터 새 대화, 추론 출력 후 HOME·화면 잠금 및 1분 후 복귀 | 실패: 서버는 추론·본문 모두 완료했지만 복귀 때 job DELETE, 화면에는 짧은 미완성 응답만 남고 완료 처리 |

브라우저 HAR와 스크린샷은 `/tmp/risuai-mobile-bg.hNIjn4`에 남겨 두었다. 핵심 HAR는 `baseline-deterministic-hidden-1.har`, `baseline-deterministic-hidden-2.har`, `final-patch-hidden-120.har`, `final-initial-hidden-race.har`, `patched-hidden-800-chunks.har`, `final-visible-fail.har`다. 이 자료에는 QA 전용 값만 사용했다.

### 실제 Android 검증

Galaxy S25 계열 실제 기기의 Android 16 / Chrome 152에서 시험했다. 사용자가 기존 대화 수정을 금지한 이후에는 직접 만든 마리골드 산나비의 새 대화방만 사용했으며, 전송 직전에 예상한 방 이름과 현재 선택된 방 이름의 일치를 검사했다. 줄 수나 시험 표식을 요구하지 않고 캐릭터 도입부와 이어지는 대화에 맞는 메시지를 보냈다.

전송 직후 HOME 시험의 기록은 `/tmp/risuai-new18-immediate-20260907/result-immediate.json`에 있다. 다음 시간은 시험 도구 시작 기준이다.

- 1.050초 전송 클릭, 1.105초 HOME, 1.974초 문서 hidden.
- 별도 서버 작업 관측 연결에서 53.812초에 본문 3,485자, `finish_reason=stop`, `[DONE]`, job `done`을 확인했다.
- 62.251초 Chrome 복귀. 직후 `freeze`, visible, 연결 생성, `resume`, 연결 실패 순서의 이벤트가 관찰됐다. 동결 이벤트의 호스트 수신 시각은 브라우저에서 실제 발생한 시각과 다를 수 있다.
- 62.436초에 또 다른 연결이 만들어졌고, 상류 헤더는 72.732초, job 완료는 116.462초에 도착했다. 완료 답변을 즉시 표시해야 한다는 기대에 실패했다.
- 이 회차는 재연결별 job 식별자를 보존하지 않아 새 LLM 요청 여부까지 단정하지 않는다. 다만 현재 패치의 `failVisibleSocket()`이 502를 반환하고 job을 DELETE하는 경로와 부합하며, 후속 시험에서 식별자·POST·DELETE를 기록하도록 보강했다.

추론 출력 도중 HOME 시험의 기록은 `/tmp/risuai-new19-midstream-20260907/result-midstream.json`에 있다.

- 15.143초 새 응답이 화면에서 출력 중임을 확인하고 15.213초 HOME으로 전환했다.
- 서버 작업 관측 결과 41.209초에 추론 297자와 본문 2,508자, `finish_reason=stop`, `[DONE]`, job `done`을 확인했다.
- 75.828초 복귀 후 같은 job에 연결했고 약 0.1초 안에 저장된 이벤트와 종료 신호를 받았다. 복귀 3초 후 화면 검사에서도 답변 완료를 확인했다.
- 이 회차에서는 동결 이벤트가 관찰되지 않았다. 한 회차의 통과로 사용자가 보고한 추론 중단 문제가 해결됐다고 판정하지 않는다.

화면 잠금을 포함한 전송 직후 시험에서는 원래 작업의 삭제와 새 작업 생성을 직접 확인했다. 기록은 `/tmp/risuai-new20-immediate-screenoff-20260907/result-immediate.json`에 있다.

- 46.955초에 서버는 추론 2,231자와 본문 2,600자 및 정상 종료를 완료했다.
- 62.092초에 hidden 상태의 `freeze`, 63.325초에 visible 전환을 관측했다.
- 같은 job의 WebSocket을 만들던 시점에 Chrome은 `WebSocket connection to '' failed: Page entered Back-Forward Cache.`를 보고했다. 이 오류 문자열만으로 실제 뒤로 가기 탐색이 있었다고 해석하지 않는다.
- 해당 연결의 생성은 문서 `resume` 이벤트보다 앞섰다. 연결 실패 직후 63.352초에 DELETE, 63.518초에 POST가 발생했고, WebSocket 경로에서 계산한 식별 해시도 원래 job과 달라졌다.
- 새 작업은 105.493초에 종료했다. 복귀 이후 약 42초의 대기는 원래 응답 재표시가 아니라 새로운 서버 작업을 기다린 시간이었다.

이 경로의 직접적인 결함은 `visibilitychange`의 visible만 보고 동결 해제가 끝나기 전에 `connectSocket()`을 실행하는 것이다. 이어지는 이전 패치의 `failVisibleSocket()`은 502를 반환하고 원래 작업을 삭제하며, 상위 요청 경로는 새 작업을 만든다. 실제 기기 이벤트와 당시 코드의 처리 경로가 일치한다. 동결 상태를 기록하고 `resume` 이후에 같은 job에 연결하도록 순서를 보장하는 수정으로 대응했다. 일반 네트워크 재시도나 새 LLM 호출 기능은 필요하지 않다. Chrome도 [Page Lifecycle 문서](https://developer.chrome.com/docs/web-platform/page-lifecycle-api)에서 동결 시 연결을 정리하고 재개 시 복원하도록 설명한다.

추론 출력 이후 화면 잠금 시험도 같은 결함으로 실패했다. 기록은 `/tmp/risuai-new21-midstream-screenoff-20260907/result-midstream.json`에 있다.

- 15.198초에 새 응답 출력 중임을 확인하고 15.257초 HOME, 16.507초 화면 잠금으로 전환했다.
- 서버는 51.081초에 추론 3,053자와 본문 3,057자 및 정상 종료를 완료했다.
- 76.157초에 동결을 관측했고, 77.109초 복귀 직후 재개 전 연결 생성과 동일한 Chrome 오류, 원래 job의 DELETE를 확인했다.
- 이번에는 새 POST가 발생하지 않았다. 복귀 3초 후 화면은 완료 상태였지만 응답 컨테이너는 380자에 불과했다. 해당 새 대화방의 응답 DOM을 추가로 검사했을 때 추론 영역을 제외한 본문은 0자였다.

두 증상의 차이는 응답 헤더 전달 여부로 설명된다. 헤더 전달 전 실패하면 502 응답을 받은 상위 경로가 새 요청을 시작한다. 이미 스트림 응답을 전달한 뒤에는 지역 변수 `status`를 502로 바꿔도 전달된 `Response`의 상태 코드는 바뀌지 않는다. 현재 패치는 오류 문자열을 스트림에 넣고 닫기 때문에 본문 없이 기존 추론만 남는 결과가 발생한다. 이는 해당 재현과 코드 경로를 함께 확인한 판정이며, 사용자의 모든 과거 응답이 같은 원인이었다는 의미는 아니다.

관측에는 CDP와 같은 server job을 읽는 별도 WebSocket을 사용했으므로 완전히 비계측 상태와 동등하지는 않다. 상세 `Network.enable`을 사용한 중간 시험들은 관측 연결이 끊겨 백그라운드 전환을 검증하지 못했고, 통과·실패 집계에서 제외했다. 상세 네트워크 관측을 제거한 뒤 위의 스트리밍 도중 시험을 완료했다.

판정에는 상류 응답 헤더의 2xx와 실제 응답 완료를 구분해야 한다. 전송 버튼이 돌아온 사실만으로 원래 응답이 보존됐다고 볼 수도 없다. 거부 응답이나 추론만 있는 응답은 상류 본문과 종료 메타데이터를 확인해야 하며, 현재 증거만으로 사용자의 모든 중단 사례를 provider의 거부로 설명할 수 없다.

## 수정 후 검증: 실제 Galaxy와 격리된 운영 복사본

### 시험 환경과 판정 기준

- 수정 이미지: `risuai-resume-fix:qa-20260907`, ID `sha256:edf2e6da4309331dd05de590b3ed823086fc12679d5c6af96671814e55588a2f`.
- 독립 스택: `/tmp/risuai-resume-stage.VmHF3F`. 운영 save의 로컬 복사본을 사용하고 인증 파일은 제외해 별도 테스트 비밀번호를 설정했다. 운영 save는 마운트하지 않았다.
- 운영과 같은 고정 RisuAI 소스, 기존 3개 패치, 운영 복사본의 CPM과 provider 설정, 기존 API proxy를 사용했다. 테스트 Caddy와 RisuAI만 별도 컨테이너다.
- Galaxy SM-S936N, Android 16, Chrome 152. ADB reverse를 통한 `http://localhost:19876/`에서 시험했다. 운영의 HTTPS·외부 접속 경로 전체를 재검증한 것은 아니지만, 실제 Android 브라우저의 hidden/freeze/resume과 동일한 제품 코드를 검증했다.
- 테스트는 마리골드 산나비의 복사본에서 만든 New Chat 22–28에만 전송했다. 기존 운영 대화에는 쓰지 않았다. 캐릭터 도입부에 이어지는 자연스러운 한국어 대화였으며 QA 표식이나 답변 길이를 강제하지 않았다.
- HOME 후 화면을 끄고 약 65초 기다렸다. 모든 유효 회차에서 실제 `freeze`, visible, `resume`, 이후 WebSocket 생성 순서를 관측했다. 페이지 재로드와 discard는 없었다.
- 별도 서버 관측 연결은 화면을 끈 뒤 55초 지연해 열었다. 그 이전에는 브라우저와 관측자 모두 구독하지 않은 구간이 있었다. 이 연결로 복귀 전 서버가 보관한 종료 이벤트를 확인했다. 기록의 observer 완료 시각은 늦게 연결해서 관측한 시각이지 실제 LLM 완료 시각이 아니다.
- 서버 버퍼 전체와 휴대폰 수신 청크의 SHA-256, 이벤트 순번, job 식별 해시, POST/DELETE 횟수, 정상 종료 메타데이터, 추론을 제외한 본문 DOM을 함께 검사했다. 전송 버튼 복귀만으로 통과시키지 않았다.

### 실제 기기 결과

| 새 대화 | 백그라운드 전환 | 상류 종료 / 본문 | 순번 누락·중복 | 서버·휴대폰 해시 | 복귀 요청 → 종료 이벤트 수신 | 판정 |
| --- | --- | --- | --- | --- | --- | --- |
| 23 | 전송 클릭 약 60 ms 뒤 HOME, 이후 화면 잠금 | `stop`, 2,824자 | 128/128, 없음 | 일치 | 114 ms | 정상 완료 통과 |
| 24 | 추론 표시 도중 HOME·화면 잠금 | `error`, 0자 | 106/106, 없음 | 일치 | 72 ms | 전송 보존 통과, 상류 오류 |
| 25 | 추론 표시 도중 HOME·화면 잠금 | `error`, 0자 | 84/84, 없음 | 일치 | 73 ms | 전송 보존 통과, 상류 오류 |
| 26 | 추론 표시 도중 HOME·화면 잠금 | `stop`, 3,315자 | 137/137, 없음 | 일치 | 63 ms | 정상 완료 통과 |
| 28 | 수신 추론 245자·본문 0자일 때 HOME·화면 잠금 | `stop`, 2,875자 | 182/182, 없음 | 일치 | 96 ms | 정상 완료 통과 |

다섯 회차 모두 job 식별 해시 1개, 생성 POST 1회, DELETE 0회였다. 수정 전의 동결 중 연결 거부 오류는 발생하지 않았다. New Chat 23은 서버 추론 2,035자, 최종 본문 DOM 2,668자였으며 New Chat 26은 추론 1,935자, 최종 본문 DOM 3,162자였다. New Chat 28은 추론 2,676자, 최종 본문 DOM 2,705자였다. DOM 글자 수는 이미지·마크다운 렌더링 때문에 원본 본문 글자 수와 다르다. 세 정상 회차 모두 복귀 3초 후 첫 화면 검사에서 완료 상태와 본문을 확인했고 스크린샷도 직접 확인했다. 표의 ms 값은 전송 완료 관측값이며 화면 렌더링 시간으로 해석하지 않는다.

New Chat 22는 새 주소에서 CPM 최초 provider 권한 확인창이 떠 LLM 요청이 시작되지 않았으므로 모바일 시험 판정에서 제외했다. 권한 확인 후 해당 요청이 foreground에서 완료된 다음 새 방을 만들어 다시 시험했다.

New Chat 27은 추론 중임을 `details` DOM 유무로 확인하려던 추가 검사에서 백그라운드 전환 전에 중단됐고, 답변은 foreground에서 완료됐다. 스트리밍 중의 추론은 아직 `details`로 렌더링되지 않을 수 있으므로 이 회차도 모바일 판정에서 제외했다. New Chat 28에서는 실제 SSE의 reasoning/content 누적 글자 수로 조건을 확인했다. HOME 직전 추론 245자·본문 0자를 확인했고, freeze 후 복귀하여 본문 2,875자까지 받았다.

New Chat 24·25의 본문 없음은 서버가 받은 SSE 자체가 본문 0자와 `finish_reason=error`였고, 동일 바이트가 휴대폰에 모두 도착한 경우다. 모바일 복귀 때 정상 본문이 유실된 이전 New Chat 21과 구별된다. 이 증거만으로 상류 오류의 세부 원인을 안전 필터, 용량 부족 또는 특정 provider 버그로 단정하지 않는다. 상류 오류를 UI가 미완성 추론처럼 보여 주는 문제는 이번 lifecycle 수정의 범위 밖이다.

증거 파일은 각각 `/tmp/risuai-fixed-new23-immediate-20260907/result-immediate.json`, `/tmp/risuai-fixed-new24-midstream-20260907/result-midstream.json`, `/tmp/risuai-fixed-new25-midstream-20260907/result-midstream.json`, `/tmp/risuai-fixed-new26-midstream-20260907/result-midstream.json`, `/tmp/risuai-fixed-new28-midstream-20260907/result-midstream.json`이다. 각 디렉터리에는 순서별 이벤트 메타데이터와 `screenshots/step-2-returned.png`도 있다. JSON에는 대화 원문·토큰·실제 job URL을 저장하지 않았지만 스크린샷에는 테스트 대화가 표시되므로 공개 자료로 취급하지 않는다. 관측 도구는 `/tmp/risuai-mobile-lifecycle-driver.mjs`에 있다.

### 자동 검증과 빌드

실제 패치된 `fetchViaProxyJobWs` 함수를 읽어 실행하는 `tests/mobile-background-stream.test.mjs`를 추가했다. 별도 제품 구현을 복제한 mock이 아니라 문서 lifecycle, 소켓과 서버 경계만 대체한다. 수정 전 소스에서는 모바일 경계 네 검사와 연결 오류 시 job 보존 검사, 총 다섯 검사가 실패했다. 수정 후 여덟 검사 모두 통과했다. 명시적 abort와 stream cancel의 서버 취소 동작도 유지됐다.

```bash
RISUAI_SOURCE_DIR=/tmp/risuai-resume-fix.KWGcZt node --test --test-timeout=3000 risuai/tests/mobile-background-stream.test.mjs
docker run --rm risuai-resume-fix-builder:qa-20260907 pnpm check
docker run --rm -e NODE_OPTIONS=--no-experimental-webstorage risuai-resume-fix-builder:qa-20260907 pnpm test
pnpm lint:compose
```

- 회귀 검사 8/8, 기존 unit test 22 files / 228 passed / 3 skipped.
- Svelte/TypeScript 오류 0, 경고 0.
- Node 26의 실험적 native localStorage가 happy-dom과 충돌하는 시험 환경 문제는 위 `NODE_OPTIONS`로 피했다. 관련 제품 코드는 변경하지 않았다.
- 저장소 Dockerfile 전체 이미지와 builder 빌드 성공. 회귀 검사 소스와 실제 builder의 `globalApi.svelte.ts` SHA-256도 일치했다.
- 3개 patch stack 신규 적용 및 재적용 성공. 패치 재적용은 이미 적용됐음을 확인하는 reverse check 경로로 성공했다.
- 임시 Compose 설정 검사, 저장소 Compose lint, 관련 diff 공백 검사 통과.

이 검증은 재현한 두 Android background/freeze 시나리오의 수정 근거다. 모든 OS·브라우저, 프로세스 종료, 상류 서비스의 정상 응답까지 보증한다는 의미는 아니다.

검증 후 임시 RisuAI·Caddy 컨테이너를 중지하고, 직접 연 테스트 탭과 staging용 ADB reverse만 정리했다. 이미지, 로컬 데이터 복사본과 증거 파일은 보존했으며 운영 컨테이너는 기존 이미지로 healthy 상태임을 다시 확인했다.

## KISS/YAGNI 경계

다음은 의도적으로 구현하지 않았다.

- 일반 네트워크 retry 또는 provider retry 정책 변경
- 끊어진 답변의 새 LLM 호출이나 부분 답변 이어쓰기
- Redis, DB 또는 cross-device job persistence
- page reload, 브라우저 process kill, OS tab discard 이후 복구
- CPM 바이너리 패치
- 모델/effort UI 변경

CPM/RisuAI 상위 계층은 provider 실패 시 기존대로 3회 시도할 수 있다. 이번 패치는 그 정책을 늘리거나 바꾸지 않는다. 브라우저 연결 실패만으로 서버 작업을 취소하지는 않으며, 명시적 중지 이외에는 기존 timeout과 메모리 제한으로 수명을 제한한다.

## 공개 이슈와 시장 상태

RisuAI 공개 issue와 PR의 제목, 본문, 댓글을 검색했지만 2026-09-06 현재 이 정확한 “모바일에서 답변 도중 background로 가면 생성이 종료됨” 문제를 직접 다루는 등록 사례는 찾지 못했다. [PR #1308](https://github.com/kwaroran/Risuai/pull/1308)은 iOS Safari에서 plugin `ReadableStream`을 MessagePort로 전달하는 문제를 고친 것이며 page background 완료 보존과는 다르다. [PR #1229](https://github.com/kwaroran/Risuai/pull/1229)은 PWA 설치 지원이고, [issue #1414](https://github.com/kwaroran/Risuai/issues/1414)은 응답 중 tab hang으로 보고된 별도 문제다.

기능 개념 자체가 시장에 없는 것은 아니다. OpenAI Responses API는 서버측 background response와 상태를 제공하고, [공식 데이터 정책](https://platform.openai.com/docs/models/default-usage-policies-by-endpoint)은 background mode가 polling을 위해 약 10분간 응답 데이터를 유지한다고 설명한다. Google Gemini Interactions API도 [background execution](https://ai.google.dev/gemini-api/docs/background-execution?hl=en)에서 interaction ID로 polling, progress streaming, disconnected stream 재접속을 공식 지원한다. ChatGPT 소비자 앱의 명시적 background 문서는 현재 [Voice conversation](https://help.openai.com/en/articles/20001274/)에 한정되어 있다.

따라서 서버 job ID와 제한된 보존, 재부착이라는 구조는 2026년 기준 현대적인 패턴이다. 다만 RisuAI의 CPM 기반 일반 텍스트 채팅 경로에는 그 연결이 없었고, 이번 패치가 기존 RisuAI stream job을 활용해 그 간극만 메운다.

## 적용과 롤백

2026-09-08 운영 RisuAI 서비스만 동결 해제 수정 이미지로 교체했다. 현재 실행 이미지 ID는 `sha256:56978f981860ac4bd04dd27e97e959960260c172178f5bb1173710e28cb8a066`이다. 이미지 메타데이터 ID는 격리 QA 태그 `risuai-resume-fix:qa-20260907`와 다르지만 두 이미지의 RootFS 레이어 8개는 모두 동일하다. 운영 번들의 source map에서도 최종 수정 고유 코드가 확인됐다.

교체 후 컨테이너와 기존 `risuai-api-proxy`는 모두 healthy였고, 외부 운영 주소의 루트와 `manifest.json`은 HTTP 200을 반환했다. 기존 운영 save bind mount를 그대로 사용했으며 API proxy 이미지, CPM 데이터와 대화 데이터는 변경하지 않았다. 배포 시점에는 Galaxy의 무선 디버깅 연결이 종료된 상태여서 운영 주소에서 실기기 시나리오를 반복하지 않았다. 실제 Android 검증은 동일 RootFS 레이어의 QA 이미지로 수행한 위 결과를 근거로 한다.

교체 직전 이미지는 `risuai-self-hosted:rollback-pre-android-thaw-20260908` 태그로 보존했다. 이미지 ID는 `sha256:6b12a30eaa245c2bd0a86caf93742a56e064901d9e01b2f63303b00a88f238fa`다.

재배포할 때는 `risuai` 디렉터리에서 이미지를 build한 뒤 RisuAI 서비스만 교체하면 된다.

```bash
docker compose build risuai
docker compose up -d --no-deps risuai
```

즉시 롤백할 이전 이미지는 `risuai-self-hosted:rollback-143af4c966bf`로 보존했다. 장기적으로 패치를 제거할 때는 `patches/series`에서 `mobile-background-stream.patch`를 제거하고 `PROXY_STREAM_ALLOWED_HOSTS` 환경 변수를 제거한 뒤 이전 이미지를 다시 build/기동하면 된다. 서버 메모리 job 외에 migration이나 영속 데이터 변경이 없으므로 데이터 롤백은 필요 없다.
