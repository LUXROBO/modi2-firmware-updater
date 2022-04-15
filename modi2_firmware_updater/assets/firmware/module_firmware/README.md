# MODI+ Module Binary

## Module Firmware Version

### OS
| | |
|:---|:---|
| e103 | **v1.1.1** |
| e230 | **v1.1.1** |

### Bootloader
| | |
|:---|:---|
| e103 | v1.0.0 |
| e230 | v1.0.0 |

### Module
| | |
|:---|:---|
| Battery | **v1.0.2** |
| Button | v1.0.0 |
| Dial | v1.0.3 |
| Display | **v1.1.4** |
| Environment | v1.0.2 |
| Imu | **v1.1.0** |
| Joystick | v1.1.1 |
| Led | v1.0.0 |
| Motor | **v1.0.3** |
| Speaker | v1.1.2 |
| Tof | v1.1.2 |
| Network | v1.1.1 |
| Network app | **v4.2.0** |
| Network ota | v1.0.0 |

## Feature

### Network app
1. 네트워크 모듈 기능 추가
* 커스터마이징 버튼, 스위치, 조이스틱, 슬라이드 지원

## Hotfix

### OS e230
1. PnP 동작 시, 첫 동작이 정상작동 하지 않는 오류 수정

### Battery
1. 완충 시, 상태 LED가 초록색으로 출력되는 오류 수정

### Display
1. 초기화 명령어가 올바른 타이밍에 작동하지 않는 오류 수정
2. 화면 오프셋을 특정한 값으로 설정 시, 텍스트가 밀려서 출력되는 오류 수정

### Motor
1. 목표 각도 모니터링 시, 싱글턴 값이 아닌 멀티턴 값을 출력하는 오류 수정

### Network app
1. BLE를 통해서 imu 모듈 데이터 모니터링 시, Z축 데이터를 못 받는 오류 수정

## Patch

### OS e103
1. 기본 상태 LED를 파란색에서 하늘색으로 변경

### OS e230
1. 기본 상태 LED를 파란색에서 하늘색으로 변경

### Imu
1. 좌표계 축 변경