aws ecr get-login-password --region ap-northeast-1 | docker login --username AWS --password-stdin 339712720989.dkr.ecr.ap-northeast-1.amazonaws.com
#docker build -t dev/anai-applio .
#docker tag dev/anai-applio:latest 339712720989.dkr.ecr.ap-northeast-1.amazonaws.com/dev/anai-applio:latest
#docker push 339712720989.dkr.ecr.ap-northeast-1.amazonaws.com/dev/anai-applio:latest

docker buildx build \
  --platform linux/amd64 \
  --cache-to type=registry,ref=339712720989.dkr.ecr.ap-northeast-1.amazonaws.com/dev/anai-applio:buildcache,mode=max \
  --cache-from type=registry,ref=339712720989.dkr.ecr.ap-northeast-1.amazonaws.com/dev/anai-applio:buildcache \
  --tag 339712720989.dkr.ecr.ap-northeast-1.amazonaws.com/dev/anai-applio:latest \
  --push \
  .

#
#set -euo pipefail
#
#REGION="ap-northeast-1"
#REGISTRY="339712720989.dkr.ecr.${REGION}.amazonaws.com"
#REPO="dev/anai-applio"
#IMAGE="${REGISTRY}/${REPO}"
#
## 선택: 커밋 SHA가 있으면 고정 태그로도 푸시 (없으면 timestamp 등으로 대체 가능)
#TAG="${TAG:-latest}"
#GIT_SHA="${GIT_SHA:-}"
#
#aws ecr get-login-password --region "${REGION}" \
#  | docker login --username AWS --password-stdin "${REGISTRY}"
#
## buildx builder 보장(최초 1회 생성)
#if ! docker buildx inspect anai-builder >/dev/null 2>&1; then
#  docker buildx create --name anai-builder --use
#else
#  docker buildx use anai-builder
#fi
#
## 권장: 배포 대상이 리눅스 amd64라면 플랫폼 고정
#PLATFORM="${PLATFORM:-linux/amd64}"
#
## 캐시 ref는 고정 태그로 유지
#CACHE_REF="${IMAGE}:buildcache"
#
#BUILD_TAGS="--tag ${IMAGE}:${TAG}"
#if [ -n "${GIT_SHA}" ]; then
#  BUILD_TAGS="${BUILD_TAGS} --tag ${IMAGE}:${GIT_SHA}"
#fi
#
#docker buildx build \
#  --platform "${PLATFORM}" \
#  --cache-to "type=registry,ref=${CACHE_REF},mode=max" \
#  --cache-from "type=registry,ref=${CACHE_REF}" \
#  ${BUILD_TAGS} \
#  --push \
#  .

#time (docker build -t <이미지명>:<태그> . && docker push <이미지명>:<태그>)
time(docker build -t dev/anai-applio . && docker tag dev/anai-applio:latest 339712720989.dkr.ecr.ap-northeast-1.amazonaws.com/dev/anai-applio:latest && docker push 339712720989.dkr.ecr.ap-northeast-1.amazonaws.com/dev/anai-applio:latest)

time(docker buildx build \
  --platform linux/amd64 \
  --cache-to type=registry,ref=339712720989.dkr.ecr.ap-northeast-1.amazonaws.com/dev/anai-applio:buildcache,mode=max \
  --cache-from type=registry,ref=339712720989.dkr.ecr.ap-northeast-1.amazonaws.com/dev/anai-applio:buildcache \
  --tag 339712720989.dkr.ecr.ap-northeast-1.amazonaws.com/dev/anai-applio:latest \
  --push \
  .)