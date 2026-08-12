# Mini Redis 기술 명세

## 1. 목적과 범위

이 문서는 `docs/subject.md`의 필수 요구사항을 구현 가능한 계약으로 구체화한다. 결과물은 Python 3.8 이상에서 외부 패키지 없이 실행되는 단일 프로세스 CLI 기반 In-Memory Key-Value 저장소다.

구현 범위는 다음과 같다.

- 직접 구현한 이중 연결 리스트, 체이닝 해시맵, 최소 힙
- String 저장 명령 `SET`, `GET`, `DEL`, `EXISTS`, `DBSIZE`, `KEYS`
- 메모리 명령 `CONFIG SET maxmemory`, `INFO memory`
- TTL 명령 `EXPIRE`, `TTL`
- LRU 자동 제거와 힙 기반 만료 관리
- `mini-redis>` REPL

동적 배열, 트리, BST, Pub/Sub, 네트워크, 영속성, 복잡 자료형, 동시성은 구현하지 않는다.

## 2. 프로젝트 구조와 책임

```text
.
├── docs/
│   ├── subject.md
│   └── spec.md
├── main.py
├── mini_redis/
│   ├── __init__.py
│   ├── linked_list.py
│   ├── hash_map.py
│   ├── min_heap.py
│   ├── store.py
│   ├── commands.py
│   └── cli.py
└── tests/
```

- `linked_list.py`: 노드와 sentinel 기반 이중 연결 리스트
- `hash_map.py`: FNV-1a 해시와 연결 리스트 체이닝을 사용하는 해시맵
- `min_heap.py`: 배열 기반 최소 힙
- `store.py`: 데이터, LRU, TTL, 메모리 상태를 하나의 일관된 저장소로 관리
- `commands.py`: 명령 파싱, 인자 검증, Redis 스타일 문자열 포맷
- `cli.py`: 프롬프트와 반복 입출력
- `main.py`: CLI 실행 진입점

제품 코드에서는 `dict`, `set`, `collections`를 사용하지 않는다. Python `list`는 버킷 테이블과 힙의 배열 저장소, `shlex.split`이 반환하는 일시적인 토큰 시퀀스에만 사용한다. 명령 디스패치는 조건 분기로 구현한다.

## 3. 자료구조 계약

### 3.1 이중 연결 리스트

`Node`는 `prev`, `next`, `data` 필드와 소유 리스트를 확인하기 위한 내부 필드를 가진다. 리스트는 head/tail sentinel을 사용하며 sentinel은 사용자 데이터로 노출하지 않는다.

`DoublyLinkedList`의 공개 인터페이스는 다음과 같다.

| 인터페이스 | 반환 | 계약 |
| --- | --- | --- |
| `insert_front(data)` | 삽입된 `Node` | 첫 데이터 노드로 삽입 |
| `insert_back(data)` | 삽입된 `Node` | 마지막 데이터 노드로 삽입 |
| `remove_front()` | 데이터 또는 `None` | 비어 있으면 `None` |
| `remove_back()` | 데이터 또는 `None` | 비어 있으면 `None` |
| `remove_node(node)` | 제거된 데이터 | 다른 리스트/이미 제거된 노드는 `ValueError` |
| `move_to_front(node)` | 동일한 `Node` | 다른 리스트/이미 제거된 노드는 `ValueError` |
| `front_node` | 노드 또는 `None` | 첫 데이터 노드 조회 |
| `back_node` | 노드 또는 `None` | 마지막 데이터 노드 조회 |
| `size()` | 정수 | 데이터 노드 개수 |
| `iter_nodes()` | 노드 iterator | 앞에서 뒤 순서로 순회 |

삽입, 삭제, 이동은 노드 참조만 변경하므로 O(1)이다. 순회만 O(n)이다.

### 3.2 해시맵

키는 문자열만 허용하며 다른 타입은 `TypeError`다. 값으로 `None`은 사용하지 않는다. 버킷은 초기 8개이며 각 버킷은 필요할 때 생성하는 `DoublyLinkedList`다. 버킷 노드에는 `HashEntry(key, value)`를 저장한다.

해시 함수는 UTF-8 바이트를 입력으로 하는 64-bit FNV-1a를 사용한다.

```text
offset basis = 14695981039346656037
prime        = 1099511628211
각 byte마다 hash = (hash XOR byte) * prime mod 2^64
bucket index = hash mod bucket_count
```

`HashMap`의 공개 인터페이스는 다음과 같다.

| 인터페이스 | 반환 | 계약 |
| --- | --- | --- |
| `put(key, value)` | 이전 값 또는 `None` | 기존 키는 값만 교체, 새 키만 크기 증가 |
| `get(key)` | 값 또는 `None` | 없는 키는 `None` |
| `remove(key)` | 제거된 값 또는 `None` | 없는 키는 `None` |
| `contains(key)` | `bool` | 키 존재 여부 |
| `keys()` | 문자열 iterator | 버킷 순서, 정렬 보장 없음 |
| `size()` | 정수 | 엔트리 수 |
| `capacity` | 정수 | 현재 버킷 수 |

새 키를 넣었을 때 예상 로드 팩터 `(size + 1) / capacity`가 0.75를 초과하면 삽입 전에 버킷을 2배로 확장하고 모든 엔트리를 재해시한다. 평균 조회/삽입/삭제는 O(1), 최악은 O(n), 확장은 O(n)이다.

### 3.3 최소 힙

`MinHeap`은 비교 연산 `<`을 지원하는 요소를 저장한다.

| 인터페이스 | 반환 | 계약 |
| --- | --- | --- |
| `push(item)` | `None` | 끝에 추가 후 `_heapify_up` |
| `pop()` | 최솟값 또는 `None` | 비어 있으면 `None`, 루트 제거 후 `_heapify_down` |
| `peek()` | 최솟값 또는 `None` | 힙을 변경하지 않음 |
| `size()` | 정수 | 요소 수 |

`push`/`pop`은 O(log n), `peek`/`size`는 O(1)이다. `heapq`는 사용하지 않는다.

## 4. 저장소 모델과 불변식

### 4.1 엔트리와 TTL 레코드

`CacheEntry`는 다음 필드를 가진다.

- `key: str`
- `value: str`
- `lru_node: Node`
- `expire_at: float | None`
- `ttl_version: int`

`ExpiryRecord`는 `expire_at`, `ttl_version`, `key`를 가지며 이 순서로 비교한다. `ttl_version`은 TTL 설정, 초기화 또는 논리적 삭제 때 증가한다.

`MiniRedis`는 다음 상태를 소유한다.

- 커스텀 `HashMap`: 키에서 `CacheEntry` 조회
- `DoublyLinkedList`: 앞은 MRU, 뒤는 LRU
- `MinHeap`: 가장 이른 `ExpiryRecord`가 루트
- `used_memory`, `maxmemory`, `evicted_keys`
- 기본값이 `time.monotonic`인 주입 가능 시계

### 4.2 항상 유지할 불변식

1. 해시맵의 모든 엔트리는 LRU 리스트에 정확히 한 노드를 가진다.
2. LRU 노드의 데이터는 동일한 `CacheEntry` 객체다.
3. `used_memory`는 현재 해시맵 엔트리의 UTF-8 키/값 바이트 합과 같다.
4. `maxmemory == 0`이면 메모리는 무제한이다.
5. `evicted_keys`는 LRU 자동 제거에만 증가한다.
6. 현재 엔트리의 `expire_at`과 버전이 일치하는 힙 레코드만 유효하다.
7. 만료, `DEL`, 덮어쓰기로 남은 힙 레코드는 lazy deletion 대상으로 취급한다.

### 4.3 만료 정리

모든 저장소 공개 명령은 동작 전에 현재 시간을 한 번 읽고 `_purge_expired(now)`를 실행한다. 힙 루트의 `expire_at <= now`인 동안 레코드를 꺼내 다음 조건을 모두 만족할 때만 키를 삭제한다.

- 키가 현재 해시맵에 존재한다.
- 엔트리의 `expire_at`이 레코드와 같다.
- 엔트리의 `ttl_version`이 레코드와 같다.

불일치하는 레코드는 stale 상태이므로 버린다. 만료 삭제는 데이터, LRU, 메모리 카운터를 함께 갱신하지만 `evicted_keys`는 증가시키지 않는다. k개의 만료/오래된 레코드 정리는 O(k log n)이다.

## 5. 저장소 공개 인터페이스

| 인터페이스 | 반환/오류 |
| --- | --- |
| `set(key, value)` | 성공 시 `None`, 단일 엔트리 OOM이면 `OutOfMemoryError` |
| `get(key)` | 문자열 또는 `None` |
| `delete(key)` | 삭제하면 1, 없으면 0 |
| `exists(key)` | 존재하면 1, 없으면 0 |
| `dbsize()` | 현재 키 수 |
| `keys()` | 현재 키 iterator |
| `expire(key, seconds)` | 설정/즉시 삭제하면 1, 없으면 0 |
| `ttl(key)` | 없는 키 -2, TTL 없음 -1, 그 외 내림한 남은 초 |
| `config_set_maxmemory(bytes)` | 성공 시 `None`, 음수면 `ValueError` |
| `info_memory()` | `MemoryInfo(used_memory, maxmemory, evicted_keys)` |

### 5.1 SET와 LRU 제거

1. 먼저 만료 키를 정리한다.
2. 새 엔트리 크기 `len(key.encode("utf-8")) + len(value.encode("utf-8"))`를 계산한다.
3. `maxmemory > 0`이고 단일 엔트리 크기가 제한보다 크면 어떤 상태도 변경하지 않고 OOM을 발생시킨다.
4. 기존 키는 이전 크기를 빼고 값을 교체하며 TTL을 초기화한다. 신규 키는 해시맵과 LRU 앞에 추가한다.
5. 성공한 신규/덮어쓰기 키를 MRU로 이동한다.
6. 제한을 초과하면 LRU 뒤에서부터 제거해 제한 이하로 만들고, 제거마다 `evicted_keys`를 1 증가시킨다.

단일 엔트리가 제한 이하면 다른 모든 키를 제거했을 때 반드시 저장할 수 있으므로 방금 설정한 MRU 키는 제거되지 않는다. `CONFIG SET`으로 제한을 현재 사용량 아래로 낮춰도 즉시 제거하지 않으며 다음 성공 가능한 `SET`에서 정리한다.

### 5.2 LRU 접근 규칙

- 성공한 `SET`: MRU로 이동
- 성공한 `GET`: MRU로 이동
- 실패한 `GET`, 만료 키 접근: 이동 없음
- `DEL`, `EXISTS`, `DBSIZE`, `KEYS`, `EXPIRE`, `TTL`, `CONFIG`, `INFO`: 이동 없음

### 5.3 TTL 규칙

- `EXPIRE`의 seconds는 정수다.
- 없는 키는 0이다.
- seconds가 0 이하면 즉시 삭제하고 1이다.
- 양수면 `expire_at = now + seconds`, 버전을 증가시키고 힙에 레코드를 추가한다.
- `TTL`은 먼저 만료를 정리한다. 없는 키는 -2, TTL이 없으면 -1이다.
- 남은 양수 시간은 `int(expire_at - now)`로 내림하며 1초 미만이면 0이다.
- 성공한 `SET` 덮어쓰기는 TTL을 제거하고 버전을 증가시킨다.
- `DEL`은 엔트리를 제거하고 버전을 증가시켜 남은 힙 레코드를 무효화한다.

## 6. 명령 및 출력 계약

`CommandProcessor.execute(line)`은 `(output, should_exit)` tuple을 반환한다. 출력이 없는 빈 입력/종료 명령의 `output`은 `None`이다.

- `shlex.split(..., posix=True)`로 큰따옴표 값을 파싱한다.
- 명령과 `CONFIG`/`INFO` 하위 키워드는 대소문자를 구분하지 않는다.
- 키와 값은 대소문자와 내용을 보존한다.
- 닫히지 않은 따옴표는 `(error) ERR syntax error`다.
- 인자 수가 다르면 `(error) ERR wrong number of arguments for '<입력 명령>' command`다.
- 알 수 없는 최상위 명령은 `(error) ERR unknown command '<입력 명령>'`이다.
- 지원하지 않는 `CONFIG`/`INFO` 하위 명령은 `(error) ERR syntax error`다.
- 정수 파싱 실패와 음수 maxmemory는 `(error) ERR value is not an integer or out of range`다.
- OOM은 `(error) OOM command not allowed when used_memory > 'maxmemory'`다.

문자열은 역슬래시를 `\\`, 큰따옴표를 `\"`로 이스케이프하고 큰따옴표로 감싼다.

| 입력 | 출력 |
| --- | --- |
| `SET key value` | `OK` 또는 OOM |
| `GET key` | `"value"` 또는 `(nil)` |
| `DEL key` | `(integer) 1` 또는 `(integer) 0` |
| `EXISTS key` | `(integer) 1` 또는 `(integer) 0` |
| `DBSIZE` | `(integer) N` |
| `KEYS` | `1. "key"` 형식의 줄 목록, 없으면 `(empty array)` |
| `CONFIG SET maxmemory bytes` | `OK` 또는 정수 오류 |
| `INFO memory` | 아래 3줄 |
| `EXPIRE key seconds` | `(integer) 1` 또는 `(integer) 0` |
| `TTL key` | `(integer) N` |
| `exit`, `quit` | 출력 없이 종료 |

`INFO memory` 형식은 정확히 다음과 같다.

```text
used_memory:<number>
maxmemory:<number>
evicted_keys:<number>
```

`KEYS` 순서는 해시맵 버킷 순서이며 보장하지 않는다. `exit`/`quit`에 추가 인자가 있으면 인자 수 오류다. 빈 입력은 아무 출력 없이 다음 프롬프트로 진행한다.

## 7. CLI 계약

`python3 main.py`로 실행한다. REPL은 매 입력 전에 `mini-redis> `를 출력하고, 명령 결과가 있으면 한 줄 이상의 결과를 출력한다. EOF, `KeyboardInterrupt`, `exit`, `quit`은 traceback 없이 종료한다. `KeyboardInterrupt` 때는 현재 줄을 끝내기 위해 빈 줄 하나를 출력한다.

## 8. 테스트와 완료 기준

표준 `unittest`만 사용한다.

- 연결 리스트: 양끝 삽입/삭제, 중간 삭제, 이동, 빈 상태, 잘못된 노드
- 해시맵: CRUD, 강제 충돌, UTF-8 해시 안정성, 0.75 확장 경계
- 최소 힙: 빈 상태, 정렬 순서, 중복 우선순위
- 저장소: UTF-8 메모리, 덮어쓰기 차이 계산, SET/GET LRU, 연속 제거, OOM 원자성
- TTL: 없음/양수/0/음수, 만료, 재설정, 덮어쓰기 초기화, stale 레코드, 전체 명령 전 정리
- 명령: 정상 출력, 대소문자, 따옴표/공백, 모든 표준 오류
- CLI: 파이프 입력에 대한 프롬프트/출력/종료
- 제약: AST로 제품 코드의 dict/set literal, `dict()`/`set()` 호출, `collections` import를 거부

완료 시 아래 명령이 모두 성공해야 한다.

```bash
python3 -m compileall -q mini_redis main.py
python3 -m unittest discover -s tests -v
git diff --check
```

또한 과제 예시와 오류 예시를 파이프로 `main.py`에 전달해 실제 출력이 이 명세와 일치하는지 확인한다. 필수 TODO나 알려진 필수 기능 결함이 남아 있으면 완료로 간주하지 않는다.
