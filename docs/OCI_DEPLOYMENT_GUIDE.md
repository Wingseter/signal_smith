# OCI Ampere A1 서버 배포 가이드

## 작업 일시
- 2026년 1월 31일

## 1. OCI CLI 설정

### 1.1 API Key 생성
```bash
# Private key 생성
openssl genrsa -out ~/.oci/oci_api_key.pem 2048
chmod 600 ~/.oci/oci_api_key.pem

# Public key 생성
openssl rsa -pubout -in ~/.oci/oci_api_key.pem -out ~/.oci/oci_api_key_public.pem
```

### 1.2 Config 파일 설정
```ini
# ~/.oci/config
[DEFAULT]
user=ocid1.user.oc1..<your-user-ocid>
fingerprint=<your-api-key-fingerprint>
tenancy=ocid1.tenancy.oc1..<your-tenancy-ocid>
region=ap-chuncheon-1
key_file=~/.oci/oci_api_key.pem
```

### 1.3 Oracle Cloud Console에서 API Key 등록
1. Oracle Cloud Console 로그인
2. 우측 상단 프로필 → User Settings
3. API Keys → Add API Key → Paste Public Key
4. 공개 키 붙여넣기 후 Add

---

## 2. 네트워크 리소스 생성

### 2.1 VCN (Virtual Cloud Network)
```bash
COMPARTMENT="ocid1.tenancy.oc1..<your-tenancy-ocid>"

# VCN 생성
VCN_ID=$(oci network vcn create \
  --compartment-id $COMPARTMENT \
  --cidr-blocks '["10.0.0.0/16"]' \
  --display-name "arm-vcn" \
  --dns-label "armvcn" \
  --query 'data.id' --raw-output)
```

### 2.2 인터넷 게이트웨이
```bash
IG_ID=$(oci network internet-gateway create \
  --compartment-id $COMPARTMENT \
  --vcn-id $VCN_ID \
  --is-enabled true \
  --display-name "arm-igw" \
  --query 'data.id' --raw-output)
```

### 2.3 라우트 테이블 설정
```bash
RT_ID=$(oci network route-table list \
  --compartment-id $COMPARTMENT \
  --vcn-id $VCN_ID \
  --query 'data[0].id' --raw-output)

oci network route-table update \
  --rt-id $RT_ID \
  --route-rules "[{\"cidrBlock\":\"0.0.0.0/0\",\"networkEntityId\":\"$IG_ID\"}]" \
  --force
```

### 2.4 보안 목록 (Security List)
```bash
SL_ID=$(oci network security-list list \
  --compartment-id $COMPARTMENT \
  --vcn-id $VCN_ID \
  --query 'data[0].id' --raw-output)

# SSH(22), HTTP(80), HTTPS(443), Frontend(3000), Backend(8000) 포트 개방
oci network security-list update \
  --security-list-id $SL_ID \
  --ingress-security-rules '[
    {"protocol":"6","source":"0.0.0.0/0","tcpOptions":{"destinationPortRange":{"min":22,"max":22}}},
    {"protocol":"6","source":"0.0.0.0/0","tcpOptions":{"destinationPortRange":{"min":80,"max":80}}},
    {"protocol":"6","source":"0.0.0.0/0","tcpOptions":{"destinationPortRange":{"min":443,"max":443}}},
    {"protocol":"6","source":"0.0.0.0/0","tcpOptions":{"destinationPortRange":{"min":3000,"max":3000}}},
    {"protocol":"6","source":"0.0.0.0/0","tcpOptions":{"destinationPortRange":{"min":8000,"max":8000}}}
  ]' \
  --egress-security-rules '[{"protocol":"all","destination":"0.0.0.0/0"}]' \
  --force
```

### 2.5 서브넷 생성
```bash
SUBNET_ID=$(oci network subnet create \
  --compartment-id $COMPARTMENT \
  --vcn-id $VCN_ID \
  --cidr-block "10.0.0.0/24" \
  --display-name "arm-subnet" \
  --dns-label "armsubnet" \
  --query 'data.id' --raw-output)
```

---

## 3. Ampere A1 인스턴스 생성

### 3.1 무료 한도 (Always Free)
| 항목 | 한도 |
|------|------|
| OCPU | 4개 |
| Memory | 24GB |
| Boot Volume | 200GB |
| 인스턴스 수 | 최대 2개 |

### 3.2 Ubuntu ARM 이미지 조회
```bash
oci compute image list \
  --compartment-id $COMPARTMENT \
  --operating-system "Canonical Ubuntu" \
  --shape "VM.Standard.A1.Flex" \
  --sort-by TIMECREATED \
  --sort-order DESC \
  --query 'data[0:3].{Name:"display-name",ID:"id"}' \
  --output table
```

### 3.3 인스턴스 생성
```bash
IMAGE_ID="<your-image-ocid>"
SSH_KEY=$(cat /path/to/your/public_key.pub)

oci compute instance launch \
  --compartment-id $COMPARTMENT \
  --availability-domain "JGyv:AP-CHUNCHEON-1-AD-1" \
  --shape "VM.Standard.A1.Flex" \
  --shape-config '{"ocpus":4,"memoryInGBs":24}' \
  --subnet-id $SUBNET_ID \
  --image-id $IMAGE_ID \
  --boot-volume-size-in-gbs 200 \
  --assign-public-ip true \
  --display-name "arm-server" \
  --metadata "{\"ssh_authorized_keys\":\"$SSH_KEY\"}"
```

### 3.4 생성된 서버 정보
| 항목 | 값 |
|------|-----|
| 이름 | arm-server |
| OS | Ubuntu 24.04 LTS (ARM) |
| Shape | VM.Standard.A1.Flex |
| OCPU | 4 |
| Memory | 24GB |
| Boot Volume | 200GB |
| Public IP | <your-server-public-ip> |
| Region | ap-chuncheon-1 (춘천) |

---

## 4. 서버 초기 설정

### 4.1 SSH 접속
```bash
ssh -i /path/to/your/private_key ubuntu@<your-server-public-ip>
```

### 4.2 Docker 설치
```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2
sudo usermod -aG docker ubuntu
sudo systemctl enable docker
sudo systemctl start docker
```

### 4.3 iptables 포트 개방
```bash
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 3000 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 8000 -j ACCEPT
```

---

## 5. 애플리케이션 배포

### 5.1 프로젝트 파일 전송
```bash
rsync -avz --progress \
  --exclude '.git' \
  --exclude 'node_modules' \
  --exclude '__pycache__' \
  --exclude '.claude' \
  --exclude '.serena' \
  -e "ssh -i /path/to/your/private_key" \
  /path/to/local/signal_smith/ \
  ubuntu@<your-server-public-ip>:~/signal_smith/
```

### 5.2 파일 권한 설정
```bash
sudo chmod -R 755 backend/
sudo chmod -R 755 frontend/
sudo chown -R 1000:1000 backend/
sudo chown -R 1000:1000 frontend/
```

### 5.3 Docker Compose 실행
```bash
cd ~/signal_smith
sudo docker compose up -d --build
```

### 5.4 컨테이너 상태
| 컨테이너 | 이미지 | 포트 |
|---------|--------|------|
| signal_smith_frontend | signal_smith-frontend | 3000 |
| signal_smith_backend | signal_smith-backend | 8000 |
| signal_smith_db | postgres:16-alpine | 5432 |
| signal_smith_redis | redis:7-alpine | 6379 |
| signal_smith_celery | signal_smith-celery_worker | - |
| signal_smith_celery_beat | signal_smith-celery_beat | - |

---

## 6. HTTPS 설정 (Let's Encrypt)

### 6.1 DuckDNS 도메인 설정
```bash
# DuckDNS IP 업데이트
curl "https://www.duckdns.org/update?domains=<your-domain>&token=<your-duckdns-token>&ip=<your-server-public-ip>"
```

- 도메인: `emolgalab.duckdns.org`
- Token: `<your-duckdns-token>`

### 6.2 Nginx & Certbot 설치
```bash
sudo apt-get install -y nginx certbot python3-certbot-nginx
```

### 6.3 Nginx 설정
```nginx
# /etc/nginx/sites-available/signal_smith
server {
    server_name emolgalab.duckdns.org;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host localhost:3000;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /docs {
        proxy_pass http://127.0.0.1:8000/docs;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    location /openapi.json {
        proxy_pass http://127.0.0.1:8000/openapi.json;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/emolgalab.duckdns.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/emolgalab.duckdns.org/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}

server {
    listen 80;
    server_name emolgalab.duckdns.org;
    return 301 https://$host$request_uri;
}
```

### 6.4 SSL 인증서 발급
```bash
sudo certbot --nginx -d emolgalab.duckdns.org --non-interactive --agree-tos --email your-email@example.com --redirect
```

### 6.5 docker-compose.yml API URL 수정
```yaml
environment:
  - VITE_API_URL=https://emolgalab.duckdns.org
  - VITE_WS_URL=wss://emolgalab.duckdns.org
```

---

## 7. 최종 접속 정보

| 서비스 | URL |
|--------|-----|
| Frontend | https://emolgalab.duckdns.org |
| API Docs | https://emolgalab.duckdns.org/docs |
| API | https://emolgalab.duckdns.org/api/ |

---

## 8. 유지보수 명령어

### 서비스 상태 확인
```bash
ssh -i /path/to/your/private_key ubuntu@<your-server-public-ip> \
  "cd ~/signal_smith && sudo docker compose ps"
```

### 로그 확인
```bash
ssh -i /path/to/your/private_key ubuntu@<your-server-public-ip> \
  "cd ~/signal_smith && sudo docker compose logs -f backend"
```

### 서비스 재시작
```bash
ssh -i /path/to/your/private_key ubuntu@<your-server-public-ip> \
  "cd ~/signal_smith && sudo docker compose restart"
```

### 전체 재빌드
```bash
ssh -i /path/to/your/private_key ubuntu@<your-server-public-ip> \
  "cd ~/signal_smith && sudo docker compose up -d --build"
```

### SSL 인증서 갱신 (자동)
- Certbot이 자동으로 인증서를 갱신 (90일마다)
- 수동 갱신: `sudo certbot renew`

---

## 9. 비용

| 항목 | 비용 |
|------|------|
| Ampere A1 (4 OCPU, 24GB) | **무료** (Always Free) |
| Boot Volume 200GB | **무료** (Always Free 한도 내) |
| Public IP | **무료** |
| 네트워크 | **무료** (50 Mbps) |
| SSL 인증서 | **무료** (Let's Encrypt) |
| 도메인 | **무료** (DuckDNS) |

**총 비용: $0/월**
