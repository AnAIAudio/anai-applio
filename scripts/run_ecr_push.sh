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

time(docker build -t dev/anai-applio . && docker tag dev/anai-applio:latest 339712720989.dkr.ecr.ap-northeast-1.amazonaws.com/dev/anai-applio:latest && docker push 339712720989.dkr.ecr.ap-northeast-1.amazonaws.com/dev/anai-applio:latest)

time(docker buildx build \
  --platform linux/amd64 \
  --cache-to type=registry,ref=339712720989.dkr.ecr.ap-northeast-1.amazonaws.com/dev/anai-applio:buildcache,mode=max \
  --cache-from type=registry,ref=339712720989.dkr.ecr.ap-northeast-1.amazonaws.com/dev/anai-applio:buildcache \
  --tag 339712720989.dkr.ecr.ap-northeast-1.amazonaws.com/dev/anai-applio:latest \
  --push \
  .)