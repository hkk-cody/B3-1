# AWS에서 직접 수행하는 B3-1 실습 가이드

작성·공식 문서 확인: 2026-09-10 · 기준: [과제 요구사항](../subject.md)

함께 읽기: [AWS·네트워크·서버 지식 노트](aws-background-knowledge.md) — 용어, 설정 이유, 명령어 해설, 장애 분석, 이해도 점검 문제를 따로 정리했다.

이 가이드는 **본인이 AWS 콘솔에서 직접 구축하고, Mac의 터미널로 서버에 접속하는 방식**이다. AWS 계정에 접속하거나 리소스를 대신 생성하지 않았다. 그림은 이해를 위한 설명도이며, 실제 콘솔 화면이나 완료 증빙이 아니다. 콘솔 언어·개편에 따라 메뉴 위치가 조금 달라질 수 있으므로 한글과 영문 메뉴명을 함께 적었다.

실습 결과는 Ubuntu 서버의 Nginx가 웹페이지를 제공하고, 내 Mac에서 `http://서버의퍼블릭IP/health`를 요청하면 HTTP 200과 `OK`가 나오는 상태다. 제출 자료를 확보한 후 리소스를 삭제하는 것까지 수행한다.

## 이 순서로 진행하기

| 순서 | 할 일 | 다음 단계로 넘어가는 기준 |
| --- | --- | --- |
| 0 | 비용·계정·권한 확인 | 프리 티어 조건과 실습 IAM 로그인 확인 |
| 1 | VPC 생성 | `b3-1-vpc` 생성 |
| 2 | Subnet 생성 | `b3-1-public` 생성 |
| 3 | Internet Gateway 연결 | `b3-1-igw`가 VPC에 Attached |
| 4 | Route Table 구성 | 기본 경로 추가 + Subnet 연결 |
| 5 | Security Group 구성 | HTTP 전체 공개, SSH 내 IP 제한 |
| 6 | EC2 생성 | Running, 상태 검사 통과, 퍼블릭 IP 확보 |
| 7 | SSH 접속 | 터미널에서 Ubuntu 명령 실행 가능 |
| 8 | Nginx 배포 | EC2 안에서 localhost 200 |
| 9 | 외부 검증·캡처 | 내 Mac에서 `/health` 200·OK |
| 10 | 오류 분석 | 원인·검증·복구 근거 확보 |
| 11 | 제출 자료 완성 | 요구하는 4종 결과물 준비 |
| 12 | 리소스 정리 | 종료·삭제 또는 미생성 근거 확보 |

처음 진행한다면 계정 준비 시간을 제외하고 3~5시간 정도를 확보한다. 막히면 그 단계의 확인 항목을 먼저 점검하고, 성공하지 않은 상태로 다음 단계까지 설정을 쌓지 않는다.

## 먼저 구조 이해하기

![인터넷에서 Nginx까지의 요청 경로](assets/01-architecture.png)

| 용어 | 이번 실습에서 하는 일 |
| --- | --- |
| VPC | 내 AWS 리소스가 사용할 전용 가상 네트워크 |
| Subnet | VPC 안에서 서버를 배치할 작은 주소 구역 |
| Internet Gateway, IGW | VPC와 인터넷을 연결하는 구성 요소 |
| Route Table | 목적지별로 어디로 통신을 보낼지 정하는 경로표 |
| EC2 | Ubuntu를 설치해 사용할 가상 컴퓨터 |
| Security Group, SG | 서버에 들어오고 나가는 통신을 허용하는 규칙 |
| IAM | AWS 리소스를 만들거나 수정할 수 있는 사용자·Role의 권한 |
| EBS | EC2의 운영체제와 파일이 저장되는 디스크 |

`10.0.0.0/16`은 VPC의 내부 주소 범위, `10.0.1.0/24`는 그 안의 Subnet 범위다. 브라우저에서는 이 사설 주소 대신 EC2의 **퍼블릭 IPv4 주소**를 사용한다. 라우팅의 `0.0.0.0/0`은 모든 IPv4 목적지에 적용되는 기본 경로를 뜻한다. SG 소스에 쓰면 모든 IPv4 출발지를 뜻하고, `내 IP/32`는 그 IP 하나를 지정한다.

## 0. AWS 계정·비용·권한 준비

### 0-1. 프리 티어를 먼저 확인하기

1. AWS 콘솔에서 **Billing and Cost Management**를 검색한다.
2. **Free Tier**, **Credits**, 계정 플랜·만료일·사용량을 확인한다. 조회 권한이 없으면 계정 담당자가 확인한다.
3. EC2 micro급, EBS 8GiB, 퍼블릭 IPv4에 적용되는 혜택과 남은 한도를 확인한다.
4. 적용 조건이 불분명하거나 무료 범위가 끝났다면 인스턴스를 생성하기 전에 교육 담당자와 비용 조건을 해결한다.

AWS는 **2025-07-15 전후 계정 생성 시점에 따라 프리 티어 체계가 다르다**. 새 체계의 무료 플랜은 최대 6개월 또는 크레딧 소진 시점까지다. 2026-09-10 현재, 2025-07-15 이전 생성 계정의 기존 12개월 EC2 혜택 기간은 이미 지났으므로 오래된 계정에서 `micro`라는 이름만 보고 무료라고 판단하면 안 된다. 계정의 실제 플랜과 크레딧을 기준으로 진행한다. [AWS EC2 프리 티어 안내](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html)

자동 할당 퍼블릭 IPv4도 비용 확인 대상이다. Elastic IP를 만들지 않는 것만으로 IPv4 비용이 사라지지는 않는다. [AWS VPC 요금 안내](https://aws.amazon.com/vpc/pricing/)

선택적으로 **Budgets → Create budget → Zero spend budget** 등의 템플릿으로 내 이메일에 비용 알림을 설정한다. 일반적인 예산 알림은 지출을 즉시 막거나 EC2를 자동 삭제하는 기능이 아니며, 비용 데이터에 지연이 있을 수 있다. [AWS Budgets 안내](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html)

### 0-2. 실습용 IAM 사용자 또는 Role 준비하기

과제에서는 루트 계정으로 실습하지 않는다. 이미 교육용 IAM 사용자 또는 Role을 받았다면 그것을 사용한다. 없는 경우 **사용자·정책 생성 권한을 가진 기존 계정 담당자**가 아래 준비를 하고, 이후 실습은 제한된 사용자로 수행한다.

1. **IAM → Policies(정책) → Create policy(정책 생성) → JSON**으로 이동한다.
2. [실습 정책 예시](examples/lab-policy.json)를 열어 JSON 전체를 붙여 넣는다.
3. 정책 편집기의 검증 결과를 확인하고 `B3-1-LabPolicy`라는 이름으로 저장한다.
4. **IAM → Users(사용자) → Create user(사용자 생성)**에서 `b3-1-learner`를 만든다. 콘솔 로그인이 필요한 경우 콘솔 접근을 설정한다. 이미 받은 Role을 쓴다면 담당자가 그 Role에 정책을 연결한다.
5. 생성한 정책을 사용자 또는 Role에 연결한다. 그룹·다른 정책에서 관리자 권한을 상속받고 있지 않은지도 확인한다.
6. 별도의 브라우저 프로필이나 시크릿 창에서 전달받은 IAM 로그인 URL과 계정 정보로 접속한다. 사용자 생성·로그인 설정은 계정 정책에 따라 담당자가 안내한다.
7. 오른쪽 위 계정 메뉴에서 실습 사용자 또는 Role임을 확인한다. 이 실습에는 프로그램용 Access Key 발급이 필요하지 않다.

정책 생성 절차는 [IAM 정책 생성 안내](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_create-console.html), 사용자 준비는 [IAM 사용자 생성 안내](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_users_create.html)를 참고한다.

**예시 정책의 범위와 한계:** 서울 리전의 EC2/VPC 조회와 실습에 필요한 생성·연결·수정·종료·삭제 작업만 나열했다. `RunInstances`는 micro급으로 제한했고, S3·RDS·IAM 변경·관리자 권한은 부여하지 않는다. VPC 관련 작업도 IAM에서는 `ec2:` 이름을 사용한다.

다만 이 예시는 `Resource: "*"`를 사용하므로 **동일 계정·서울 리전의 다른 EC2/VPC 리소스까지 작업 범위에 들어갈 수 있다**. `Project=B3-1` 태그는 추적용이며 이 정책의 권한 격리를 강제하지 않는다. 따라서 교육 전용 계정의 출발점으로 사용하고, 다른 서비스가 운영되는 공유 계정에서는 담당자가 리소스 ARN과 작업별 태그 조건으로 범위를 더 좁힌 정책을 준비한다. 이 예시는 계정에 실제 적용·검증한 최종 정책이 아니다. [EC2 콘솔 정책 예시](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-policies-ec2-console.html), [EC2 작업별 권한 참고](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ec2.html)

`AccessDenied`가 나오면 오류의 작업 이름, 리전, 대상 리소스를 기록하고 담당자가 필요한 권한만 검토한다. 콘솔에서 안 쓰는 기능 패널이 권한 오류를 표시하는 경우까지 해결하려고 관리자 권한을 붙이지 않는다. 생성만 허용하고 삭제를 막은 정책이면 정리를 완료할 수 없으므로 삭제 권한도 처음부터 확인한다.

### 0-3. 리전과 이름 통일하기

AWS 콘솔 오른쪽 위 리전을 **Asia Pacific (Seoul), 아시아 태평양(서울), `ap-northeast-2`**로 선택한다. IAM은 전역 서비스이므로 리전 표시가 다를 수 있지만 VPC와 EC2 작업은 서울에서 진행한다.

| 리소스 | Name |
| --- | --- |
| VPC | `b3-1-vpc` |
| Public Subnet | `b3-1-public` |
| Internet Gateway | `b3-1-igw` |
| Route Table | `b3-1-public-rt` |
| Security Group | `b3-1-web-sg` |
| EC2 | `b3-1-web` |
| 키페어 | `b3-1-key` |

가능한 리소스에 `Project=B3-1` 태그를 추가한다. 생성할 때마다 ID와 시간을 메모한다. 과제 폴더의 `docs/resource-inventory.md`에 다음 표를 만들어 기록하면 된다.

```markdown
| 종류 | Name | 실제 ID | 생성 시각 | 정리 상태 | 확인 근거 |
| --- | --- | --- | --- | --- | --- |
| VPC | b3-1-vpc | 작성 | 작성 | 미정리 | 작성 |
| Subnet | b3-1-public | 작성 | 작성 | 미정리 | 작성 |
| IGW | b3-1-igw | 작성 | 작성 | 미정리 | 작성 |
| Route Table | b3-1-public-rt | 작성 | 작성 | 미정리 | 작성 |
| SG | b3-1-web-sg | 작성 | 작성 | 미정리 | 작성 |
| EC2 | b3-1-web | 작성 | 작성 | 미정리 | 작성 |
| EBS | 루트 볼륨 | 작성 | 작성 | 미정리 | 작성 |
| 키페어 | b3-1-key | 작성 | 작성 | 미정리 | 작성 |
```

## 1. VPC 생성

**위치: AWS 콘솔 → VPC → Your VPCs(사용자 VPC) → Create VPC(VPC 생성)**

| 입력 항목 | 값 |
| --- | --- |
| Resources to create | **VPC only(VPC만)** |
| Name tag | `b3-1-vpc` |
| IPv4 CIDR | 수동 입력, `10.0.0.0/16` |
| IPv6 CIDR | 없음 |
| Tenancy | Default(기본) |
| 추가 태그 | `Project` = `B3-1` |

생성 후 `vpc-...` ID를 기록한다. 선택한 VPC의 **Actions → Edit VPC settings**에서 DNS resolution이 활성화되어 있는지 확인한다. 이번에는 퍼블릭 IP로 접속하므로 DNS hostnames는 필수는 아니다.

**확인:** 상태 Available, CIDR `10.0.0.0/16`. 이 과정에서 만들어지는 기본 Route Table·SG·Network ACL은 정상이다. 별도 VPC가 더 생긴 것이 아니다. 단계별 학습을 위해 다른 리소스는 뒤에서 직접 만든다. [AWS VPC 생성 안내](https://docs.aws.amazon.com/vpc/latest/userguide/create-vpc.html)

## 2. Public Subnet 생성

**위치: VPC → Subnets(서브넷) → Create subnet(서브넷 생성)**

| 입력 항목 | 값 |
| --- | --- |
| VPC ID | `b3-1-vpc` |
| Subnet name | `b3-1-public` |
| Availability Zone | 서울 리전에서 선택 가능한 AZ 1개, 예: `ap-northeast-2a` |
| VPC IPv4 CIDR | `10.0.0.0/16` |
| Subnet IPv4 CIDR | `10.0.1.0/24` |

생성 후 해당 Subnet을 선택하고 **Actions → Edit subnet settings → Enable auto-assign public IPv4 address**를 켠 뒤 저장한다. EC2를 만들 때도 퍼블릭 IP 설정을 다시 확인한다. [퍼블릭 IP 자동 할당 설정](https://docs.aws.amazon.com/vpc/latest/userguide/subnet-public-ip.html)

**확인:** 소속 VPC가 `b3-1-vpc`, CIDR이 `10.0.1.0/24`. 이름에 Public이 들어간 것만으로 인터넷이 연결되지는 않는다. 다음 두 단계가 필요하다.

## 3. Internet Gateway 생성·연결

**위치: VPC → Internet gateways(인터넷 게이트웨이) → Create internet gateway**

1. 이름을 `b3-1-igw`로 입력하고 생성한다.
2. 생성한 IGW를 선택한다.
3. **Actions(작업) → Attach to VPC(VPC에 연결)**를 누른다.
4. `b3-1-vpc`를 선택하고 연결한다.

**확인:** IGW 상태가 `Attached`, 연결된 VPC ID가 기록한 ID와 같다. IGW를 생성만 하고 연결하지 않으면 사용할 수 없다. [AWS IGW 연결 안내](https://docs.aws.amazon.com/vpc/latest/userguide/working-with-igw.html)

## 4. Route Table 만들고 Subnet에 연결

**위치: VPC → Route tables(라우팅 테이블) → Create route table**

1. 이름은 `b3-1-public-rt`, VPC는 `b3-1-vpc`로 생성한다.
2. 생성한 테이블을 선택하고 **Routes(라우팅) → Edit routes(라우팅 편집) → Add route**로 이동한다.
3. 아래 두 번째 경로를 추가한다. 첫 번째 `local` 경로는 원래 있으므로 유지한다.

| Destination(대상 주소) | Target(전달 대상) |
| --- | --- |
| `10.0.0.0/16` | `local` |
| **`0.0.0.0/0`** | **Internet Gateway → `b3-1-igw`** |

4. **Save changes**를 누른다.
5. 같은 테이블의 **Subnet associations(서브넷 연결) → Edit subnet associations**로 이동한다.
6. `b3-1-public`을 체크하고 저장한다.

**확인:** 기본 경로 상태가 Active이고, **Explicit subnet associations(명시적 서브넷 연결)**에 `b3-1-public`이 표시된다. 경로만 만들고 Subnet 연결을 빠뜨리는 실수가 많다. [AWS 인터넷 경로 구성 안내](https://docs.aws.amazon.com/vpc/latest/userguide/working-with-igw.html)

**캡처:** 경로 탭과 서브넷 연결 탭을 각각 저장한다. `network-routes.png`, `network-association.png`처럼 이름을 붙인다.

## 5. Security Group 설정

![HTTP와 SSH에 적용할 접근 규칙](assets/02-access-rules.png)

**위치: EC2 → Network & Security → Security Groups(보안 그룹) → Create security group**

| 항목 | 값 |
| --- | --- |
| Security group name | `b3-1-web-sg` |
| Description | `B3-1 HTTP and restricted SSH` |
| VPC | **`b3-1-vpc` 선택** |

설명은 위와 같이 영문을 사용한다. 인바운드 규칙은 다음 두 개만 추가한다.

| Type | Protocol | Port | Source |
| --- | --- | --- | --- |
| HTTP | TCP | 80 | Anywhere-IPv4, `0.0.0.0/0` |
| SSH | TCP | 22 | **My IP(내 IP)**, 실제 공인 IPv4 `/32` |

아웃바운드는 기본 허용 규칙을 유지한다. 인바운드에서 `All traffic + 0.0.0.0/0`을 추가하지 않는다. 이번에는 HTTPS를 구성하지 않으므로 443 규칙도 필요 없다. SG는 허용한 요청의 응답을 추적하므로 응답용 임의 포트를 인바운드에 추가할 필요가 없다. [AWS Security Group 동작](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-security-groups.html)

VPN이나 네트워크 변경으로 My IP가 달라질 수 있다. SSH가 막히면 내 Mac 터미널에서 다음 명령으로 현재 IPv4를 확인하고 SSH 소스를 갱신한다.

```bash
curl -4 --max-time 10 https://checkip.amazonaws.com
```

출력 주소에 `/32`를 붙인다. 집 안에서 쓰는 `192.168.x.x` 주소가 아닌 **인터넷에서 보이는 공인 IP**를 입력해야 한다. 브라우저와 터미널이 서로 다른 VPN 경로를 쓰면 콘솔의 My IP 결과와 다를 수 있다.

**확인·캡처:** `b3-1-web-sg`의 인바운드 두 규칙과 VPC ID를 확인하고 `security-group.png`를 저장한다.

## 6. EC2 생성

**위치: EC2 → Instances(인스턴스) → Launch instances(인스턴스 시작)**

| 항목 | 선택 값 |
| --- | --- |
| Name | `b3-1-web` |
| OS / AMI | Canonical의 **Ubuntu Server 24.04 LTS, 64-bit x86** 일반 이미지 |
| 인스턴스 유형 | **`t3.micro`**, 해당 계정의 프리 티어 적용 확인 |
| 키페어 | 아래 설명대로 `b3-1-key` 생성 |
| VPC | `b3-1-vpc` |
| Subnet | `b3-1-public` |
| Auto-assign public IP | **Enable(활성화)** |
| Firewall | Select existing security group → **`b3-1-web-sg`** |
| EBS | 루트 디스크 **8GiB, gp3**, 기본 IOPS·처리량 유지 |
| Delete on termination | 루트 볼륨 **활성화** 확인 |
| Number of instances | **1** |

Ubuntu Pro나 유료 Marketplace 이미지를 선택하지 않는다. AMI와 유형에서 프리 티어 표시·계정 혜택을 확인하고, 해당 조합을 사용할 수 없으면 비용 조건을 확인한 다른 micro급으로 조정한다. 이 가이드의 서버 명령어는 Ubuntu 기준이다.

**키페어 생성:** Create new key pair → 이름 `b3-1-key` → RSA → `.pem` → Create. 다운로드한 개인 키는 SSH에 필요하다. 저장소에 넣거나 다른 사람에게 보내지 않는다.

**Network settings는 Edit를 눌러 직접 확인한다.** 화면에 보이는 기본 VPC·기본 Subnet을 그대로 사용하지 않도록 한다. 연결한 SG가 여러 개면 허용 규칙이 합쳐지므로 이 실습에서는 지정한 SG 한 개만 연결한다.

Advanced details에서 IAM instance profile은 선택하지 않는다. 웹 서버가 AWS API를 호출하는 구성이 아니기 때문이다. User data도 비워 두고 직접 SSH로 설치한다. T3의 **Credit specification** 항목이 있으면 `Standard`로 선택한다. `Unlimited`는 CPU 사용에 따라 추가 크레딧 비용이 발생할 수 있다. [T 계열 크레딧 모드 설정](https://docs.aws.amazon.com/en_uk/AWSEC2/latest/UserGuide/burstable-performance-instances-how-to.html)

최종 Summary에서 한 대인지 확인하고 **Launch instance**를 누른다. `Running` 및 표시되는 상태 검사 통과까지 기다린다. 상세 화면에서 다음을 메모한다.

- Instance ID: `i-...`
- Public IPv4 address: 이후 SSH와 HTTP에 사용할 주소
- Private IPv4 address: `10.0.1.x` 형태의 내부 주소
- VPC, Subnet, Security Group ID
- Storage 탭의 루트 EBS Volume ID: `vol-...`

인스턴스 생성과 구성 요소는 [AWS EC2 시작 안내](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EC2_GetStarted.html)를 참고한다. 고객 관리 KMS 키 사용을 강제하는 교육 계정이라면 암호화 정책에 필요한 권한은 담당자와 확인한다.

**확인:** 퍼블릭 IPv4가 비어 있으면 다음 단계로 넘어가지 않는다. 아직 설치 전인 새 실습 인스턴스라면 잘못 만든 인스턴스를 종료하고 퍼블릭 IP 활성화 설정으로 다시 생성하는 방법이 단순하다. 두 대를 동시에 남기지 않는다.

## 7. Mac 터미널에서 SSH 접속

여기부터 터미널을 두 개 사용하면 편하다. **터미널 A는 EC2 접속**, **터미널 B는 Mac에서 외부 HTTP 검증**에 사용한다. AWS CloudShell이나 브라우저의 EC2 Instance Connect는 접속 출발지·권한 조건이 달라질 수 있으므로 이 안내에서는 Mac 기본 터미널을 사용한다.

### 7-1. 개인 키 정리 — 내 Mac에서 실행

다운로드 파일명이 `b3-1-key.pem`인지 Finder에서 확인한 뒤 실행한다. 같은 이름의 기존 키가 있다면 덮어쓰지 말고 별도 이름을 사용한다.

```bash
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
mv "$HOME/Downloads/b3-1-key.pem" "$HOME/.ssh/b3-1-key.pem"
chmod 400 "$HOME/.ssh/b3-1-key.pem"
```

`chmod 400`은 본인만 개인 키를 읽을 수 있도록 권한을 제한한다.

### 7-2. 서버 접속 — 내 Mac에서 실행

`YOUR_EC2_PUBLIC_IP` 부분을 콘솔에서 복사한 **실제 퍼블릭 IPv4**로 바꾼다. 아래 문자열을 그대로 사용하면 접속되지 않는다.

```bash
ssh -i "$HOME/.ssh/b3-1-key.pem" ubuntu@YOUR_EC2_PUBLIC_IP
```

첫 접속에서 호스트 지문 확인 메시지가 나올 수 있다. 대상 IP가 본인 인스턴스인지 확인한다. 지문을 대조하려면 **EC2 → 인스턴스 → Actions → Monitor and troubleshoot → Get system log**의 SSH 호스트 키 지문과 비교한다. 일치하면 `yes`를 입력한다. 지문이 다르면 접속을 진행하지 말고 대상 서버를 확인한다. [AWS SSH 접속 안내](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/connect-linux-inst-ssh.html)

접속에 성공하면 프롬프트가 `ubuntu@ip-10-0-1-...`와 비슷하게 바뀐다. 다음 명령으로 확인한다.

```bash
whoami
hostname
cat /etc/os-release
```

`whoami`는 `ubuntu`, OS 정보는 선택한 Ubuntu여야 한다. 이제 터미널 A에서 실행하는 명령은 서버에서 실행된다. 연결을 끝낼 때는 `exit`를 입력한다.

## 8. Nginx 설치와 웹 서비스 설정

**이 절의 명령은 모두 SSH 접속한 EC2의 터미널 A에서 실행한다.** 새 실습 서버 기준이며 기존 서비스를 운영하는 서버에 덮어쓰지 않는다. 명령 블록을 하나씩 실행하고 오류가 없는지 확인한다.

### 8-1. 인터넷 통신 확인과 설치

```bash
curl -I --max-time 10 https://example.com
sudo apt update
sudo apt install -y nginx
sudo systemctl enable --now nginx
systemctl is-active nginx
curl -i --max-time 10 http://localhost/
```

`curl`로 외부 사이트의 응답을 확인하고, `systemctl is-active nginx`가 `active`, localhost 요청이 HTTP 200을 반환하는지 확인한다. `apt update`는 설치 가능한 패키지 목록을 갱신하고 `apt install`이 Nginx를 설치한다. [Ubuntu Nginx 설치 안내](https://ubuntu.com/server/docs/how-to/web-services/install-nginx/)

### 8-2. 간단한 웹페이지 작성

아래 블록을 첫 줄부터 마지막 `HTML`까지 통째로 붙여 넣는다. 마지막 `HTML`은 공백 없이 단독 줄에 둔다. 기존 웹사이트가 있다면 다음 예제 HTML 대신 본인의 정적 파일을 같은 디렉터리에 배치해도 된다.

```bash
sudo mkdir -p /var/www/b3-1
sudo tee /var/www/b3-1/index.html > /dev/null <<'HTML'
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>B3-1 | Hello Cloud</title>
  <style>
    body { margin: 0; padding: 64px 24px; background: #f1f5f9;
           color: #17253b; font-family: system-ui, sans-serif; }
    main { max-width: 720px; margin: auto; padding: 36px;
           background: white; border-radius: 20px; }
    h1 { font-size: 40px; margin-top: 0; }
    p { line-height: 1.8; }
    a { color: #245cce; }
  </style>
</head>
<body>
  <main>
    <h1>Hello Cloud</h1>
    <p>AWS에 직접 배포한 B3-1 웹사이트입니다.</p>
    <p>서울 리전의 VPC와 Public Subnet 안에서 Ubuntu와 Nginx를 사용합니다.</p>
    <p><a href="/health">서비스 상태 확인하기</a></p>
  </main>
</body>
</html>
HTML
sudo chmod 755 /var/www/b3-1
sudo chmod 644 /var/www/b3-1/index.html
```

### 8-3. `/health` 엔드포인트 설정

```bash
sudo tee /etc/nginx/sites-available/b3-1 > /dev/null <<'NGINX'
server {
    listen 80 default_server;
    server_name _;
    root /var/www/b3-1;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }

    location = /health {
        default_type text/plain;
        return 200 "OK\n";
    }
}
NGINX

sudo ln -sfn /etc/nginx/sites-available/b3-1 /etc/nginx/sites-enabled/b3-1
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
```

`sites-available`은 설정을 보관하고, `sites-enabled`의 링크는 활성화할 사이트를 지정한다. 마지막 삭제 명령은 새로 설치한 Nginx의 **기본 사이트 활성화 링크**를 제거하는 것이다. `<<'NGINX'`의 작은따옴표는 `$uri`가 셸 변수로 바뀌지 않게 하므로 유지한다.

`nginx -t` 결과가 `syntax is ok`와 `test is successful`이면 적용한다. 실패하면 표시된 파일·줄을 고친 뒤 검사부터 다시 한다.

```bash
sudo systemctl reload nginx
systemctl is-active nginx
systemctl is-enabled nginx
curl -i --max-time 10 http://localhost/
curl -i --max-time 10 http://localhost/health
```

`location = /health`는 정확히 그 경로의 요청을 처리한다. `return 200`은 성공 코드와 고정 본문을 반환한다. 여기의 `/health`는 Nginx가 응답하는지 확인하는 단순 상태 확인이다. [Nginx return 지시어](https://nginx.org/en/docs/http/ngx_http_rewrite_module.html#return)

예상 응답 모양은 다음과 같다. 버전·헤더는 환경에 따라 달라지며 **아래 예시를 실제 실행 결과로 제출하면 안 된다.**

```text
HTTP/1.1 200 OK
Content-Type: text/plain
...

OK
```

**캡처:** 서버 프롬프트, localhost 호출, 200·OK가 보이도록 `internal-health.png`를 저장한다.

## 9. 내 Mac에서 외부 접속 검증

![내 Mac과 EC2에서의 검증 위치 구분](assets/03-verification.png)

**새 터미널 B를 연다. SSH로 들어가지 않은 Mac 터미널에서 실행한다.** 아래 IP를 실제 값으로 바꾼다.

```bash
date '+%Y-%m-%d %H:%M:%S %Z'
curl -i --connect-timeout 5 --max-time 10 http://YOUR_EC2_PUBLIC_IP/health
```

명령은 GET 요청을 보낸다. `-i`는 응답 헤더도 보여주므로 상태 코드와 본문을 한 화면에서 확인할 수 있다. `HTTP/1.1 200 OK`와 본문 `OK`가 나오면 외부 접속 검증에 성공한 것이다.

브라우저에서도 `http://실제퍼블릭IP/`를 열어 `Hello Cloud` 페이지를 확인한다. 이 실습은 HTTP이므로 `https://`로 바뀌면 주소를 다시 확인한다. 브라우저의 ‘안전하지 않음’ 표시는 HTTPS를 적용하지 않았기 때문이며, HTTP 접속 증빙 자체의 실패를 뜻하지 않는다.

**제출 기준은 B로 통일한다.** Mac에서 호출한 `/health`의 URL, 200, OK, 검증 시각을 캡처한다. 브라우저 화면은 추가 증빙으로 활용한다. Mac에서는 `Shift + Command + 4`로 영역을 선택해 촬영할 수 있다.

`docs/screenshots/`에 다음 자료를 모은다.

| 파일명 예시 | 화면에 보여야 할 것 |
| --- | --- |
| `external-health.png` | Mac에서의 실제 URL, GET 결과 200·OK, 검증 시각 |
| `internal-health.png` | EC2의 localhost 요청과 200·OK |
| `web-page.png` | 브라우저 주소창의 실제 IP와 웹페이지 |
| `network-routes.png` | Route Table ID, `0.0.0.0/0 → igw-...` |
| `network-association.png` | 실제 Subnet과 Route Table의 연결 |
| `security-group.png` | HTTP·SSH 규칙 및 소스 제한 |
| `instance.png` | EC2 이름·상태·퍼블릭 IP |

캡처에 개인 키·비밀번호·Access Key가 나오지 않게 한다. 제출에 필요한 접속 URL과 포트·규칙은 확인 가능하게 남긴다.

## 10. 오류 해결과 트러블슈팅 보고서

### 증상별 확인 순서

| 증상 | 먼저 확인할 내용 |
| --- | --- |
| SSH 타임아웃 | Running·상태 검사 → 퍼블릭 IP → SG의 SSH 소스 → Subnet의 경로 → IGW 연결 |
| `Permission denied (publickey)` | Ubuntu 사용자명 `ubuntu`, 해당 인스턴스에 지정한 키페어, `.pem` 경로·권한 |
| `UNPROTECTED PRIVATE KEY FILE` | Mac에서 개인 키에 `chmod 400` 적용 |
| `apt update` 통신 실패 | DNS resolution, IGW·라우팅, 퍼블릭 IP, SG 아웃바운드 |
| localhost부터 실패 | Nginx 실행 여부, 설정 검사, 포트 리스닝 |
| 내부 성공·외부 타임아웃 | 퍼블릭 IP, EC2에 실제 연결된 SG, HTTP 규칙, 경로, OS 방화벽 |
| `/` 성공·`/health` 404 | 설정 파일의 활성화 링크, 정확한 `/health` 경로, reload 여부 |
| 브라우저만 실패 | `http://`인지, 프록시·VPN 설정, Mac curl 결과 |
| `AccessDenied` | 거부된 AWS 작업·리전·리소스, 정책·권한 경계·조직 정책 |
| 삭제 시 `DependencyViolation` | 남은 ENI, Subnet 연결, SG 참조, 연결된 IGW 등 |

EC2에 접속 가능한 상황이면 다음을 조사한다.

```bash
sudo nginx -t
systemctl status nginx --no-pager
sudo ss -lntp
curl -i --max-time 10 http://localhost/health
sudo tail -n 30 /var/log/nginx/access.log
sudo tail -n 30 /var/log/nginx/error.log
sudo journalctl -u nginx -n 30 --no-pager
sudo ufw status
```

`ss`에서 TCP 80 리스닝을 찾는다. UFW가 비활성 상태라면 그것 자체가 문제는 아니다. 활성화한 환경에서는 SSH를 유지한 채 TCP 80 규칙을 확인한다. 기본 Network ACL은 이번 실습에서 수정하지 않는다. 다른 사람이 바꾼 ACL이 있다면 요청과 응답 양방향 규칙도 점검한다.

### 문제가 없었을 때 재현할 사례

자연스럽게 발생한 오류가 있으면 그 사례를 작성한다. 오류가 없으면 본인 실습 서버에서 **HTTP 80 인바운드 규칙 제거**로 장애를 재현한다.

1. 정상 상태의 외부·내부 응답과 기존 HTTP 규칙을 먼저 기록한다.
2. **EC2 → Security Groups → 실제 연결된 `b3-1-web-sg` → Edit inbound rules**에서 HTTP 규칙만 제거하고 저장한다. SSH 규칙은 유지한다.
3. Mac 터미널 B에서 새 `curl -i --connect-timeout 5 --max-time 10 http://실제IP/health` 요청을 실행한다.
4. EC2 터미널 A에서는 `curl -i http://localhost/health`와 `systemctl is-active nginx`가 여전히 정상인지 확인한다.
5. SG 규칙과 Nginx 로그를 비교해 네트워크 접근 차단 가설을 검증한다.
6. HTTP TCP 80, `0.0.0.0/0` 규칙을 복구한다.
7. Mac에서 새 요청으로 200·OK 복구를 확인하고 캡처한다.

규칙 변경 후 이미 추적 중인 연결은 즉시 끊기지 않을 수 있으므로 새 curl 프로세스로 확인한다. 여전히 성공하면 EC2에 다른 SG가 함께 연결되어 80을 허용하는지도 조사한다. 타임아웃이 관측되지 않았다면 실패가 발생했다고 쓰지 않는다.

보고서에 계획적으로 재현한 실험임을 명시한다. 로그에 기록이 없다는 사실만으로 SG가 원인이라고 단정하지 않는다. **내부 성공 + 외부 실패 + 실제 규칙 변경 + 복구 후 성공**을 함께 근거로 삼는다.

`docs/troubleshooting.md`에 아래 틀을 복사하고 실제 관찰 결과로 채운다.

```markdown
# 트러블슈팅 보고서

- 수행 일시:
- 대상 EC2 / SG ID:
- 사례 구분: 실제 발생 오류 / 계획적 재현

| 항목 | 실제 수행 내용 |
| --- | --- |
| 증상 | 실패한 요청, 오류 메시지, 시각 |
| 가설 | 가능한 원인과 그렇게 생각한 이유 |
| 검증 | 실행한 명령, 설정 화면, 로그와 결과 |
| 조치 | 실제 변경한 설정과 값 |
| 결과 | 조치 후 동일한 검증의 결과 |
| 재발 방지 | 다음 배포에서 확인할 구체적 항목 |

## 증빙

실제 캡처와 명령 출력을 첨부한다.
```

## 11. 제출 자료 만들기

리소스를 삭제하기 전에 실제 아키텍처 정보와 접속 증빙을 모두 확보한다.

### 11-1. 아키텍처 이미지 한 장

가이드의 첫 그림은 설계 설명용이다. 본인의 실제 구성과 대조하고, 사용한 VPC·Subnet·IGW·EC2·SG 이름과 라우팅 및 요청 흐름을 반영한 최종 그림을 `docs/architecture.png`로 저장한다. PowerPoint, Keynote, diagrams.net 등 익숙한 도구로 같은 구조를 그려도 된다.

그림에는 최소한 다음을 넣는다.

- 서울 리전과 VPC 경계, Public Subnet 경계
- IGW와 VPC의 연결
- Subnet에 연결된 Route Table의 `0.0.0.0/0 → IGW`
- EC2, Nginx, 실제 퍼블릭 IP 또는 이를 식별할 표기
- EC2에 적용한 SG: HTTP 80 전체, SSH 22 내 IP
- 외부 → IGW → EC2/Nginx로 도달하는 요청 화살표

### 11-2. README

프로젝트 최상위 `README.md`에 다음 틀을 사용한다. 실제 값과 검증 결과를 직접 채운다.

```markdown
# B3-1 AWS 웹 서비스 배포

## 환경

- 리전: ap-northeast-2
- OS / 인스턴스 유형: 실제 값 작성
- 웹 서버: Nginx
- VPC / Subnet: 실제 이름과 CIDR 작성

## 외부 접속 검증

- 선택 방식: B — GET /health
- 실제 접속 URL: http://실제퍼블릭IP/health
- 실행 위치: EC2 밖의 개인 Mac
- 검증 일시 및 시간대: 작성
- 실제 결과: 작성

![외부 접속 결과](docs/screenshots/external-health.png)

## 재현 방법

실제 수행한 네트워크 설정, SSH 접속 및 Nginx 설치·설정 명령을 기록한다.
SG 규칙과 실제 적용한 IAM 정책의 범위도 설명한다.

## 제출 문서

- [아키텍처](docs/architecture.png)
- [트러블슈팅](docs/troubleshooting.md)
- [리소스 정리](docs/cleanup-checklist.md)

## 서비스 종료

- 현재 상태: 작성
- 리소스 정리 완료 일시: 완료 후 작성
- 삭제 후에는 해당 URL로 서비스에 접속할 수 없다.
```

실제 배포한 HTML과 Nginx 설정도 남기고 싶다면 **Mac 터미널 B**에서 프로젝트 폴더로 이동한 후 복사한다. 서버가 실행 중일 때 수행하고 IP는 바꾼다.

```bash
mkdir -p web infra
scp -i "$HOME/.ssh/b3-1-key.pem" ubuntu@YOUR_EC2_PUBLIC_IP:/var/www/b3-1/index.html web/index.html
scp -i "$HOME/.ssh/b3-1-key.pem" ubuntu@YOUR_EC2_PUBLIC_IP:/etc/nginx/sites-available/b3-1 infra/nginx.conf
```

IAM 정책은 예시 파일을 그대로 ‘적용 완료’라고 기록하지 말고, **실제 적용한 최종 JSON**을 담당자에게 확인해 `infra/iam-policy.json`으로 보관한다.

## 12. 실습 리소스 정리

**모든 증빙을 확보한 다음 진행한다.** 제출 후 실시간 접속 평가가 따로 정해져 있다면 평가 시점과 정리 시점을 먼저 맞춘다. 장시간 무작정 켜 두지 않는다.

### 12-1. EC2 종료

**EC2 → Instances → `b3-1-web` → Instance state → Terminate instance**를 선택한다. 대상 ID를 확인하고 종료한다. `Terminated`가 될 때까지 기다린다. **Stop은 실습 정리 완료가 아니다.** 종료 시 루트 EBS 삭제는 해당 볼륨의 DeleteOnTermination 설정에 달려 있다. [EC2 종료와 볼륨 처리](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/terminating-instances.html)

종료된 인스턴스가 한동안 목록에 보이는 것은 정상이다. 상태와 ID가 보이는 화면을 캡처한다.

### 12-2. 디스크와 주소 확인

1. **EC2 → Elastic Block Store → Volumes**에서 기록한 `vol-...`이 삭제됐는지 확인한다. 남아 있고 실습용 미사용 볼륨이라면 Delete volume으로 삭제한다.
2. **Snapshots**에서 실습 중 생성한 스냅샷이 있다면 삭제한다. 이 가이드대로만 진행했다면 직접 생성한 스냅샷은 없다.
3. **EC2 → Elastic IP addresses**에서 실습용 할당 주소가 있는지 확인한다. 기본 절차에서는 만들지 않으므로 `미생성 확인`으로 기록한다. 실습 중 만들었다면 연결 해제 후 **Release Elastic IP addresses**까지 수행한다.

자동 할당 퍼블릭 IP는 EC2 종료 시 반환되며 별도 Elastic IP 해제 작업을 하지 않는다. 계획 밖에서 생성한 EIP·스냅샷 등의 삭제 권한은 제공한 기본 정책에 없으므로, 그런 리소스가 있으면 담당자가 필요한 정리를 수행한다.

### 12-3. 네트워크 삭제

1. EC2 종료 후 해당 인스턴스의 네트워크 인터페이스가 정리됐는지 확인한다.
2. VPC의 **Route tables → `b3-1-public-rt` → Subnet associations → Edit subnet associations**에서 `b3-1-public` 연결을 해제한다.
3. **Subnets → `b3-1-public` → Delete subnet**을 수행한다.
4. 사용자 생성 Route Table `b3-1-public-rt`를 삭제한다. main Route Table을 직접 지우려고 하지 않는다.
5. **Security Groups → `b3-1-web-sg` → Delete security group**을 수행한다.
6. **Internet gateways → `b3-1-igw` → Actions → Detach from VPC**, 이어서 Delete internet gateway를 수행한다.
7. **Your VPCs → `b3-1-vpc` → Actions → Delete VPC**를 수행한다. VPC의 기본 SG·기본 Route Table·기본 ACL은 VPC 삭제 과정에서 정리된다.

삭제 순서는 연결 관계에 따라 조정할 수 있다. `DependencyViolation`은 사용 중인 연결이 남아 있다는 의미이므로 해당 VPC의 남은 리소스부터 조사한다. 다른 프로젝트나 기본 VPC를 삭제하지 않는다. [AWS VPC 삭제 안내](https://docs.aws.amazon.com/vpc/latest/userguide/delete-vpc.html)

### 12-4. 나머지와 Billing 확인

- **EC2 → Key Pairs**에서 실습용 `b3-1-key`를 삭제한다. 다시 쓰지 않을 로컬 개인 키도 정리한다.
- NAT Gateway·ELB/ALB·RDS는 생성하지 않았다면 `해당 없음 — 미생성 확인`으로 기록한다. 실습 중 별도로 만들었다면 담당자 권한으로 정리한다.
- 실습용으로만 만든 임시 IAM 사용자·정책은 네트워크 정리 이후 담당자가 삭제한다. 계속 쓰는 교육용 사용자·Role은 임의로 삭제하지 않는다.
- Billing 조회 권한이 있는 주체가 비용·크레딧 내역을 확인한다. 다른 리전에서 잘못 생성한 리소스가 있는지도 확인한다.
- 비용 정보의 반영 지연이 있으므로 확인 시각을 기록하고 다음 날에도 한 번 확인한다. 이미 발생한 사용료는 삭제로 취소되지 않으며, 화면의 현재 0원만으로 모든 리소스가 삭제됐다고 판단하지 않는다.

`docs/cleanup-checklist.md`에는 아래 틀을 사용한다. 아직 수행하지 않은 항목을 완료 처리하지 않는다.

```markdown
# 리소스 정리 체크리스트

- 계정 식별 정보: 필요한 범위만 작성
- 리전: ap-northeast-2
- 확인 일시:

| 항목 | 실제 ID / 이름 | 결과 | 완료 시각 | 근거 |
| --- | --- | --- | --- | --- |
| EC2 | 작성 | Terminated 확인 후 작성 | 작성 | 캡처 |
| EBS | 작성 | 삭제 확인 후 작성 | 작성 | 목록 |
| Elastic IP | 작성 | 해제 / 미생성 확인 | 작성 | 목록 |
| Subnet | 작성 | 삭제 확인 후 작성 | 작성 | 목록 |
| 사용자 Route Table | 작성 | 삭제 확인 후 작성 | 작성 | 목록 |
| 사용자 SG | 작성 | 삭제 확인 후 작성 | 작성 | 목록 |
| IGW | 작성 | Detach 및 삭제 확인 | 작성 | 목록 |
| VPC | 작성 | 삭제 확인 후 작성 | 작성 | 목록 |
| 키페어 | 작성 | 삭제 확인 후 작성 | 작성 | 목록 |
| NAT Gateway | 작성 | 삭제 / 미생성 확인 | 작성 | 근거 |
| ELB/ALB | 작성 | 삭제 / 미생성 확인 | 작성 | 근거 |
| RDS | 작성 | 삭제 / 미생성 확인 | 작성 | 근거 |
| 스냅샷 | 작성 | 삭제 / 미생성 확인 | 작성 | 근거 |

- Billing 확인 결과 및 조회 시각:
- 이후 재확인 결과:
- 남은 항목이 있다면 이유와 조치:
```

## 제출 직전 마지막 점검

- [ ] `docs/architecture.png` 또는 PDF에 실제 구성과 트래픽 흐름이 있다.
- [ ] README에 **방식 B, 실제 URL, 검증 일시**가 있다.
- [ ] 외부 PC에서 받은 **200·OK 스크린샷**이 한 장 이상 있다.
- [ ] EC2 내부 localhost 응답과 인터넷 아웃바운드 통신을 확인했다.
- [ ] HTTP 80은 전체 공개, SSH 22는 개인 IP로 제한했다.
- [ ] 실제 IAM 권한 범위를 설명할 수 있고 관리자 권한을 부여하지 않았다.
- [ ] 트러블슈팅 보고서에 증상·가설·검증·조치·결과·재발 방지가 있다.
- [ ] 정리 체크리스트에 삭제 또는 미생성의 실제 근거가 있다.
- [ ] 서비스 정리 후 README의 현재 상태와 종료 일시를 갱신했다.

HTTPS와 Docker 보너스는 기본 과정을 마친 뒤 별도 확장으로 진행한다. 이번 안내만 따라도 필수 과제의 구현·검증·문서화·정리 과정을 수행할 수 있다.
