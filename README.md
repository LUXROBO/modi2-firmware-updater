# MODI2 Multi Uploader

실행 준비
--
1. `python3`(파이썬3.6 혹은 그 이상의 버전)를 컴퓨터에 설치
2. `python3 -m pip install -r requirements.txt`로 의존성 패키지들을 설치

실행 방법 (개발)
--
`python3 main.py --debug True`로 GUI 프로그램을 실행한다.

실행 방법 (일반)
--
`python3 main.py`로 GUI 프로그램을 실행한다.

실행파일 생성
--
1. `python3 bootstrap.py` 커맨드를 실행하여 정의한 `spec` 파일을 기반으로 실행파일을 생성
2. `dist` 폴더 내 `modi2_multi_upploader.exe` 혹은 `modi2_multi_upploader.app` 실행파일이 생성된것을 확인