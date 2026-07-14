# HeiTuzImgGen2

## 이미지는 만들고 끝내는 게 아닙니다. **쓸 수 있게 남겨야 합니다.**

[![Release](https://img.shields.io/github/v/release/HeiTuz/HeiTuzimgGen2?style=flat-square)](https://github.com/HeiTuz/HeiTuzimgGen2/releases/latest)
[![CI](https://img.shields.io/github/actions/workflow/status/HeiTuz/HeiTuzimgGen2/ci.yml?branch=main&style=flat-square&label=CI)](https://github.com/HeiTuz/HeiTuzimgGen2/actions)
[![License: MIT](https://img.shields.io/badge/license-MIT-black?style=flat-square)](LICENSE)

**HeiTuzImgGen2**는 ChatGPT 구독으로 이미지 작업을 더 단단하게 굴리기 위한 제작 스킬입니다.

한 장 만들고 결과가 어디서 나왔는지 놓치는 방식 대신, 제품 사진·캠페인 비주얼·편집 이미지·다량 제작을 **확인 가능한 결과물**로 남깁니다.

## 이런 이미지를 만듭니다

### 한 장을 제대로 만듭니다

텍스트로 새 이미지를 만들거나, 레퍼런스 이미지를 바탕으로 원하는 장면을 편집합니다.

제품의 핵심 디테일을 지키고 싶을 때, 인물의 정체성을 살리고 싶을 때, 장면의 분위기만 갈아끼우고 싶을 때. 요청의 중심을 놓치지 않게 제작 흐름을 잡습니다.

### 여러 장을 한 세트로 만듭니다

제품컷, 룩북, 카드뉴스, 광고 소재처럼 여러 장이 필요한 작업은 한 장씩 운에 맡기면 망가집니다.

HeiTuzImgGen2는 같은 목표를 공유하는 이미지들을 묶어 관리해, **세트 전체가 한 브랜드처럼 보이게** 만듭니다.

### 제품 사진을 더 믿을 수 있게 만듭니다

제품 사진에서 중요한 건 새 옷을 발명하는 게 아니라, 원래 제품을 알아볼 수 있게 지키는 겁니다.

앞·뒤·소재·디테일을 빠뜨리지 않고, 최종 폴더에는 **선택된 컷만 남기는** 흐름으로 제품 이미지 작업을 정리합니다.

### 결과가 이상하면 이유를 남깁니다

좋지 않은 이미지를 조용히 섞어두지 않습니다.

완성도, 제품 충실도, 구도, 일관성을 기준으로 결과를 점검하고, 실패한 부분만 다시 다룹니다. 그래서 무작정 다시 돌리는 비용과 시간을 줄일 수 있습니다.

## 이런 사람에게 맞습니다

- ChatGPT로 이미지 만들지만 결과 관리까지 제대로 하고 싶은 사람
- 제품 사진·패션 비주얼·브랜드 콘텐츠를 여러 장 제작하는 사람
- 레퍼런스를 쓰면서도 핵심 요소가 무너지는 게 싫은 사람
- 생성 이미지와 최종 납품 이미지를 깔끔하게 분리하고 싶은 사람
- “만들었다”가 아니라 “검수해서 쓸 수 있다”를 원하는 사람

## 30초 설치

**한 번 설치하면 Codex CLI + ImgGen2 + MPW가 같이 붙습니다.**

```bash
npx --yes --package github:HeiTuz/HeiTuzImgGen2 heituz-imggen2
# 또는
bunx --package github:HeiTuz/HeiTuzImgGen2 heituz-imggen2
```

설치기는 운영체제에 맞춰 공식 Codex 설치 경로를 사용합니다.

| 환경 | Codex 기본 경로 | `heituz` 명령 |
| --- | --- | --- |
| macOS / Linux | `~/.local/bin/codex` | `~/.local/bin/heituz` |
| Windows | `%LOCALAPPDATA%\Programs\OpenAI\Codex\bin\codex.exe` | `%LOCALAPPDATA%\HeiTuz\bin\heituz.cmd` |

macOS/Linux는 `~/.profile`과 `~/.zprofile`에 `~/.local/bin`을, Windows는 사용자 PATH에 `%LOCALAPPDATA%\HeiTuz\bin`을 중복 없이 추가합니다. 설치 뒤 새 Terminal을 열면 바로 `heituz update`가 됩니다.
## Vision-QC 설정

생성 후보는 최종 전달 전에 Vision-QC로 점검할 수 있습니다. 대화형 설치는 사용 가능한 Gemini 키와 Codex를 감지해 추천 경로를 보여주고, 비대화형 설치는 명시 옵션이 없으면 `off`로 닫힙니다. 설정은 설치 폴더의 `vision-qc.json`에 기록되며 자격 증명 값은 저장하지 않습니다.

```bash
heituz vision-qc setup
heituz vision-qc status
```
```bash
# 설치 또는 업데이트 시 모드 지정: auto, gemini-luna, gemini, luna, off
npx --yes --package github:HeiTuz/HeiTuzImgGen2 heituz-imggen2 -- --vision-qc gemini-luna

# 일회성 실행에서 설치 설정을 덮어쓰기
python scripts/gemini_image_qc.py output.png --brief "제품 검수" --qc-mode luna
```

`gemini-luna`는 Gemini를 먼저 쓰고 timeout/429/5xx에만 Luna를 한 번 사용합니다. `gemini`은 Luna로 fallback하지 않으며 현재 세션의 Google AI Studio 키가 필요합니다. `luna`는 Codex 구독 CLI로 직접 검수합니다. `off`는 QC 실행을 fail-closed로 막습니다. `auto`는 두 자격이 있으면 Gemini→Luna, 하나만 있으면 그 경로, 둘 다 없으면 `off`로 해석됩니다.

키는 이미지 생성에는 쓰이지 않고, 최대 1024px·300KiB 임시 JPEG 썸네일의 Gemini 검수에만 사용됩니다. 설정 도구는 키를 저장·출력·명령줄 인자로 전달하지 않습니다. 키 값은 URL, 보고서, 저장소 파일에 넣지 마세요.

Google AI Studio에서 키를 만든 뒤 안내된 명령을 **같은 터미널**에서 실행하고 QC를 시작하세요. 세션을 닫으면 키도 사라집니다.

## 업데이트도 한 줄

```bash
heituz update
```

이 명령은 **HeiTuzImgGen2와 HeiTuzMPW를 함께 갱신**합니다. Codex까지 강제로 갱신하려면:

```bash
heituz update --codex
```

무엇을 실행할지만 보고 싶다면:

```bash
heituz update --dry-run
```

특정 폴더에 ImgGen2만 따로 설치하는 기존 경로도 남아 있습니다.

```bash
npx --yes --package github:HeiTuz/HeiTuzImgGen2 heituz-imggen2 -- --target "$HOME/.hermes/skills/HeiTuzImgGen2" --skip-mpw --skip-codex
```

## Grok은 명시했을 때만

기본 이미지 생성은 계속 Codex 구독 경로를 사용합니다. Grok은 Hermes에 **xAI OAuth가 연결되어 있고**, 요청에 `Grok`, `그록`, 또는 `xAI로 생성`이 명시된 경우에만 선택됩니다.

```text
Grok으로 이 콘셉트 이미지를 20장 만들어줘.
```

20장은 한꺼번에 폭격하지 않습니다. 먼저 1장으로 생성·품질을 확인한 뒤 3개 작업으로 시작해 최대 5개까지 제한적으로 처리하고, 나머지는 큐에 남깁니다. 실패한 장만 다시 생성합니다.

OAuth가 없거나 현재 Hermes 세션에 xAI 이미지 도구가 없으면 Grok 경로는 비활성으로 끝납니다. API 키만으로 대신 실행하거나, Codex·Higgsfield로 조용히 바꾸지 않습니다. 자세한 계약은 [`references/grok-oauth-explicit-routing.md`](references/grok-oauth-explicit-routing.md)에 있습니다.

## 이렇게 시작하세요

```text
이 제품 사진을 정사각형 상세페이지 컷으로 정리해줘.
제품의 색·실루엣·소재·봉제 디테일은 바꾸지 말고, 배경만 자연스럽게 확장해.
```

```text
이 인물을 유지한 채, 비 오는 도쿄 골목의 패션 에디토리얼 한 컷으로 만들어줘.
```

```text
이 브랜드의 여름 캠페인용 이미지를 6장 만들어줘.
모든 컷이 같은 세계관과 색감으로 보이게 해.
```

```text
이 레퍼런스들을 합쳐 프리미엄 향수 광고 비주얼을 만들어줘.
제품 병의 형태와 라벨은 정확히 유지해.
```

## 제작은 과감하게, 결과 관리는 냉정하게

좋은 이미지는 한 번의 운으로 끝나지 않습니다.

**원하는 장면을 만들고, 필요한 기준으로 고르고, 실제로 쓸 수 있는 컷만 남깁니다.**

HeiTuzImgGen2는 그 흐름을 위해 만들어졌습니다.

## License

MIT © HeiTuz
