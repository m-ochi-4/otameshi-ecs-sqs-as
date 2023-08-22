
## アーキテクチャ図

![architecture](./assets/architecture.drawio.svg)


## 使い方

./autoscaling-sqs-ecs/ に移動後, CFn テンプレートの package 及び depoly を実行してください.

各パラメタは環境にあわせてご変更ください.


### CFn パラメタ

|CFn パラメタ名|用途|
|-|-|
|SQSQueueName|キュー深度取得元 SQS キュー名|
|ECSClusterName|ECSServiceName で指定した ECS サービスが属する ECS クラスター名|
|ECSServiceName|Application Auto Scaling ターゲットになる ECS サービス名|
|MinCapacity|Auto Scaling に渡す最小タスク数|
|MaxCapacity|Auto Scaling に渡す最大タスク数|
|ExpectedMsgCapacityPerTask|ECS の 1 タスク当たりで許容できる SQS 未処理メッセージ数|


### 実行例

```bash
cd ./autoscaling-sqs-ecs/
mkdir .build/

aws cloudformation package \
    --template-file ./autoscaling-sqs-ecs.yml \
    --s3-bucket ${YOUR_S3_BUCKET_NAME_FOR_CFN} \
    --output-template-file ./.build/autoscaling-sqs-ecs.packed.yml \
    --region ${YOUR_AWS_REGION} \
    --profile ${YOUR_AWS_PROFILE}

aws cloudformation deploy \
    --template ./.build/autoscaling-sqs-ecs.packed.yml \
    --stack-name autoscaling-sqs-ecs-otameshi \
    --parameter-overrides \
        SQSQueueName=otameshi-as-sqs-ecs \
        ECSClusterName=otameshi_sqs_consumer_cluster \
        ECSServiceName=otameshi_sqs_consumer_service \
        MinCapacity=1 \
        MaxCapacity=4 \
        ExpectedMsgCapacityPerTask=10 \
    --capabilities CAPABILITY_IAM \
    --region ${YOUR_AWS_REGION} \
    --profile ${YOUR_AWS_PROFILE}
```


## 実行デモ環境構成

動作確認用途で, 読み取った SQS メッセージより DynamoDB へ書き込みを行うコンシューマーコンテナと, SQS メッセージ発行用のプロデューサースクリプトを用意しています.

下記手順に従って構成できます. YOUR_ で始まる変数は適切なものへ置き換えてください.


### 前提条件

- AWS CLI v2 のインストール
- Docker のインストールと Docker Buildx の有効化
- Python >= 3.11 環境の用意と boto3 インストール


### 1. CFn パラメタ設定

./config/template.json の SubnetIds に ECS タスク展開先の VPC サブネット ID と, SecurityGroupIds に ENI へアタッチするセキュリティグループ ID を CommaDelimitedList 形式で入力してください.


### 2. コンシューマーコンテナ用インフラ構成

./otameshi-sqs-consumer/cfn/otameshi-sqs-consumer=infra.yml より CFn スタックを作成してください. SQS キュー, DynamoDB テーブル, ECR レジストリが作成されます.

```bash
aws cloudformation deploy \
    --template ./otameshi-sqs-consumer/cfn/otameshi-sqs-consumer-infra.yml \
    --stack-name otameshi-sqs-consumer-infra \
    --parameter-overrides file://./config/template.json \
    --region ${YOUR_AWS_REGION} \
    --profile ${YOUR_AWS_PROFILE}
```


### 3. コンシューマーコンテナ ビルドとレポジトリ登録

```bash
aws ecr get-login-password --region ${YOUR_AWS_REGION} --profile ${YOUR_AWS_PROFILE} | docker login --username AWS --password-stdin ${YOUR_AWS_ACCOUNT_ID}.dkr.ecr.${YOUR_AWS_REGION}.amazonaws.com

ECR_REPO_URI=`aws cloudformation describe-stacks --stack-name otameshi-sqs-consumer-infra --query 'Stacks[0].Outputs[?OutputKey==\`ECRRepositoryUri\`] | [0].OutputValue' --output text --region ${YOUR_AWS_REGION} --profile ${YOUR_AWS_PROFILE}`

(cd ./otameshi-sqs-consumer/ && docker buildx build --platform linux/amd64,linux/arm64/v8 -f ./Dockerfile -t ${ECR_REPO_URI}:latest --push .)
```


### 4. コンシューマーコンテナ 実行環境構成

./otameshi-sqs-consumer/cfn/otameshi-sqs-consumer-role.yml より
CFn スタックを作成してください. ECS タスクロール, タスク実行ロール, インスタンスロールが作成されます.

```bash
aws cloudformation deploy \
    --template ./otameshi-sqs-consumer/cfn/otameshi-sqs-consumer-role.yml \
    --stack-name otameshi-sqs-consumer-role \
    --parameter-overrides file://./config/template.json \
    --capabilities CAPABILITY_NAMED_IAM \
    --region ${YOUR_AWS_REGION} \
    --profile ${YOUR_AWS_PROFILE}
```

データプレーンに Fargete を使用したい場合は ./otameshi-sqs-consumer/cfn/otameshi-sqs-consumer-ecs-fargate.yml より,
EC2 を使用したい場合は ./otameshi-sqs-consumer/cfn/otameshi-sqs-consumer-ecs-ec2.yml より CFn スタックを作成してください. ECS 実行環境が作成されます.

```bash
aws cloudformation deploy \
    --template ./otameshi-sqs-consumer/cfn/otameshi-sqs-consumer-ecs-fargate.yml \
    --stack-name otameshi-sqs-consumer-ecs-fargate \
    --parameter-overrides file://./config/template.json \
    --region ${YOUR_AWS_REGION} \
    --profile ${YOUR_AWS_PROFILE}
```

OR

```bash
aws cloudformation deploy \
    --template ./otameshi-sqs-consumer/cfn/otameshi-sqs-consumer-ecs-ec2.yml \
    --stack-name otameshi-sqs-consumer-ecs-ec2 \
    --parameter-overrides file://./config/template.json \
    --region ${YOUR_AWS_REGION} \
    --profile ${YOUR_AWS_PROFILE}
```

以降, [使い方](#使い方) [実行例](#実行例) を参考に Auto Scaling 構成用の CFn スタックを作成してください. この際の --parameter-overrides には当手順で編集した ./config/template.json を参照することができます.


### 5. プロデューサースクリプト 実行


```bash
export SQS_QUEUE_URL=`aws cloudformation describe-stacks --stack-name otameshi-sqs-consumer-infra --query 'Stacks[0].Outputs[?OutputKey==\`SQSQueueUrl\`] | [0].OutputValue' --output text --region ${YOUR_AWS_REGION} --profile ${YOUR_AWS_PROFILE}`
export AWS_DEFAULT_REGION=${YOUR_AWS_REGION}
export AWS_PROFILE=${YOUR_AWS_PROFILE}

python ./script/producer.py
```


### 6. クリーンアップ

ECS タスクと EC2 インスタンスの停止, ECR レポジトリのコンテナイメージを削除後, 各 CFn スタックを削除してください.

不要な料金を発生させないため, 次の出力を削除してください。

- CloudWatch Logs ロググループ
  - /ecs/otameshi_sqs_consumer/otameshi_sqs_consumer
  - /aws/lambda/otameshi-sqs-consumer-as-FunctionCalcBacklog- で始まる ロググループ
- S3 オブジェクト
  - cloudformation package でアップロードしたオブジェクト
