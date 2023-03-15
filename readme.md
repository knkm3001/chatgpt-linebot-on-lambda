# chatGPT lineBot on AWS lambda

## 環境構築
1. apiゲートウェイ作成
1. ECRでレポジトリ作成
    1. このレポジトリのコンテナ化
    1. ECRにpush
1. lambdaでコンテナベースで関数作成
1. AuroraDB作成
1. lambdaの環境変数に値を入力