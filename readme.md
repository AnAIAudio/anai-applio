# AnAI 에서 사용하는 음색 모델 합성/추론 서비스

## 훈련

특이사항: 훈련 작업 후 훈련 시작 - 출력 정보에 나오는 아이디 값을 가지고 로그를 모니터링 할 수 있음.

export를 통해서 훈련한 내용들을 압축, 내보낼 수 있음.

### 실행 방법
docker swarm 환경 혹은 docker compose를 사용하여 실행할 수 있음.
run_stack.sh 혹은 run_dev/run_prod.sh 파일의 명령어를 이용하여 실행

### 주의 사항
swarm의 경우 AWS ECR에 있는 이미지를 가지고 실행하게 되므로, 코드 업데이트 시 docker build - image push

과정을 거친 후 실행 시켜야 함 